"""EPUB 体积压缩模块

原则：内容零改动，只降像素与压缩质量。
  · 图片：等比缩到上限尺寸 + 重新编码（有透明通道的走 PNG 量化，其余走 JPEG）
  · 字体：TTF/OTF 转 WOFF2（同字形，体积约减半），同步改写 CSS / OPF 引用
  · 结构：mimetype 保持首项且不压缩，其余 DEFLATE 重打包
  · 目标体积：未达标时逐级降质重试，绝不删除任何图片、字体或章节
"""

import io
import os
import re
import zipfile

IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
FONT_EXT = (".ttf", ".otf")
TEXT_EXT = (".css", ".xhtml", ".html", ".htm", ".opf", ".ncx", ".xml")

MEDIA_BY_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}


def _pil():
    from PIL import Image
    return Image


def _has_alpha(im):
    try:
        if im.mode in ("RGBA", "LA"):
            return im.getchannel("A").getextrema()[0] < 250
        if im.mode == "P" and "transparency" in im.info:
            return True
    except Exception:
        pass
    return False


def _alpha_is_smooth(im):
    """透明通道是否有渐变（决定能否安全量化成 PNG8）"""
    try:
        a = im.convert("RGBA").getchannel("A")
        hist = a.histogram()
        levels = sum(1 for v in hist if v > im.width * im.height * 0.0005)
        return levels > 3
    except Exception:
        return True


def _encode_image(data, max_edge, quality, colors):
    """返回 (新字节, 后缀)；失败或无收益由调用方判断"""
    Image = _pil()
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None

    max_edge = int(max_edge or 0)
    if max_edge > 0 and max(im.size) > max_edge:
        r = max_edge / float(max(im.size))
        im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)

    buf = io.BytesIO()
    try:
        if _has_alpha(im):
            rgba = im.convert("RGBA")
            if _alpha_is_smooth(rgba):
                # 渐变透明（章头图云雾边）：必须保留逐像素 alpha，
                # 量化成调色板会把渐变压成硬边，图上会出现一条白线
                rgba.save(buf, "PNG", optimize=True, compress_level=9)
            else:
                q = rgba.quantize(colors=max(16, min(256, int(colors))),
                                  method=Image.FASTOCTREE)
                q.save(buf, "PNG", optimize=True, compress_level=9)
            return buf.getvalue(), ".png"
        im.convert("RGB").save(buf, "JPEG", quality=max(20, min(95, int(quality))),
                               optimize=True, progressive=True)
        return buf.getvalue(), ".jpg"
    except Exception:
        return None


def _font_to_woff2(data):
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(io.BytesIO(data))
        f.flavor = "woff2"
        buf = io.BytesIO()
        f.save(buf)
        return buf.getvalue()
    except Exception:
        return None


def _rewrite_refs(files, rename, img_rename):
    """改写文本文件里的引用：字体/图片文件名、格式声明、OPF media-type"""
    if not rename:
        return
    for name, data in list(files.items()):
        if not name.lower().endswith(TEXT_EXT):
            continue
        try:
            txt = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        new = txt
        for old, repl in rename.items():
            new = new.replace(old, repl)
        new = new.replace("format('truetype')", "format('woff2')")
        new = new.replace('format("truetype")', 'format("woff2")')
        new = new.replace("format('opentype')", "format('woff2')")
        new = new.replace('format("opentype")', 'format("woff2")')
        for bad in ('font/ttf', 'font/otf', 'application/vnd.ms-opentype',
                    'application/x-font-ttf', 'application/font-sfnt'):
            new = new.replace('media-type="%s"' % bad, 'media-type="font/woff2"')
        # 图片改了扩展名 → 同步 OPF 的 media-type
        for old, repl in img_rename.items():
            ob, nb = os.path.basename(old), os.path.basename(repl)
            mt = MEDIA_BY_EXT.get(os.path.splitext(nb)[1].lower())
            if not mt:
                continue
            pat = re.compile(r'href="([^"]*%s)"(\s+)media-type="[^"]*"' % re.escape(ob))
            new = pat.sub(lambda m, mt=mt: 'href="%s"%smedia-type="%s"' % (m.group(1), m.group(2), mt), new)
        if new != txt:
            files[name] = new.encode("utf-8")


def _write_zip(path, files, order):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), b"application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        seen = {"mimetype"}
        for n in order:
            if n in seen or n not in files:
                continue
            seen.add(n)
            z.writestr(n, files[n], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        for n, d in files.items():          # 兜底：顺序表里漏掉的条目
            if n in seen:
                continue
            z.writestr(n, d, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(tmp, path)


def compress_epub_file(path, target_mb=10, img_max=1440, quality=80, colors=256,
                       woff2=True, log=print):
    """就地压缩 EPUB，返回统计信息。target_mb<=0 表示只压一轮、不追体积。"""
    with zipfile.ZipFile(path) as z:
        order = [i.filename for i in z.infolist()]
        original = {n: z.read(n) for n in order}

    size0 = os.path.getsize(path)
    img_names = [n for n in order if n.lower().endswith(IMG_EXT)]
    font_names = [n for n in order if n.lower().endswith(FONT_EXT)]

    # 档位表：先按用户设定，未达标再逐级降质
    tiers = [(int(img_max or 0), int(quality), int(colors))]
    e, q, c = int(img_max or 0), int(quality), int(colors)
    for _ in range(5):
        e = int(e * 0.85) if e else 0
        q = max(45, q - 10)
        c = max(32, c // 2)
        tiers.append((e, q, c))

    want_target = bool(target_mb and target_mb > 0)
    rounds = len(tiers) if want_target else 1
    size = size0
    for idx, (edge, qq, cc) in enumerate(tiers[:rounds]):
        files = dict(original)
        rename, img_rename = {}, {}
        for n in img_names:
            got = _encode_image(original[n], edge, qq, cc)
            if not got:
                continue
            data, ext = got
            newn = os.path.splitext(n)[0] + ext
            if len(data) < len(original[n]):
                files.pop(n, None)
                files[newn] = data
                if newn != n:
                    rename[n] = newn
                    img_rename[n] = newn
        if woff2:
            for n in font_names:
                got = _font_to_woff2(original[n])
                if got and len(got) < len(original[n]):
                    newn = os.path.splitext(n)[0] + ".woff2"
                    files.pop(n, None)
                    files[newn] = got
                    rename[n] = newn
        if rename:
            _rewrite_refs(files, rename, img_rename)

        new_order = [rename.get(n, n) for n in order]
        _write_zip(path, files, new_order)
        size = os.path.getsize(path)
        log(f"  压缩档位{idx + 1}：边长≤{edge or '原图'} px，质量 {qq}，色数 {cc} → {size / 1048576:.2f} MB")
        if not want_target or size <= target_mb * 1048576:
            break

    log(f"压缩完成：{size0 / 1048576:.2f} MB → {size / 1048576:.2f} MB"
        f"（省 {(1 - size / max(1, size0)) * 100:.0f}%）")
    return {"size_before_mb": round(size0 / 1048576, 2),
            "size_after_mb": round(size / 1048576, 2),
            "images": len(img_names), "fonts": len(font_names)}
