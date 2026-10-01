# -*- coding: utf-8 -*-
"""EPUB 精排核心库 v2：自定义目录正则、多级目录、文字样式引擎、头图边缘样式、
插图页/正文内插图、注释样式、字体子集化、EPUB 组装"""
import os, re, io, json, html as htmlmod, random, subprocess, sys, zipfile

# ================= 默认配置 =================

DEFAULT_TOC_REGEX = r"^\s*(?:\d{1,4}、\s*)?(?:简介|内容简介|序|楔子|尾声|后记|番外[一二三四五六七八九十百千零两\d]*|第?[0-9一二三四五六七八九十百千零两]{1,6}[章节回部])[一-龥· ]{0,12}(?:[(（][0-9一二三四五六七八九十百千零两]{1,5}[)）])?(?:\s+.*)?$"

# 文字样式预设（scope: inline=行内span, block=整段）
STYLE_PRESETS = [
    {"key": "dlg_cn",  "name": "中文双引号“…”", "scope": "inline", "regex": "“[^”]*”"},
    {"key": "dlg_sq",  "name": "单引号‘…’",     "scope": "inline", "regex": "‘[^’]*’"},
    {"key": "dlg_jp1", "name": "直角引号「…」", "scope": "inline", "regex": "「[^」]*」"},
    {"key": "dlg_jp2", "name": "双直角引号『…』", "scope": "inline", "regex": "『[^』]*』"},
    {"key": "paren",   "name": "括号文字（…）",  "scope": "inline", "regex": "（[^（）]*）"},
    {"key": "author",  "name": "作者有话说（整段）", "scope": "block",
     "regex": "【?(?:📢)?(?:作者有话要说|作者有话说|作家有话说|作家想说的话|作者想说的话|作者的话)(?::|：)?】?[\\s\\S]*?(?=\\r?\\n\\s*(?:[（(]?全书完[）)]?)|\\r?\\n\\s*\\r?\\n|$)"},
]

AD_PRESETS = {
    "站点推广": ["欢迎访问", "请访问", "本书首发", "最新章节.{0,12}更新", "最新最全的小说", "更多好看的(文章|小说)",
                "(?i)www\\.\\w+\\.(com|net|cc|org|me)", "(?i)https?://", "在线阅读全文", "全本TXT下载",
                "手机阅读", "[A-Za-zＡ-Ｚａ-ｚ]{2,}[.．点](com|COM|ＣＯＭ|net|cc)", "想看更多.{0,20}(小说|访问)"],
    "作者拉票": ["求月票", "求推荐票", "求收藏", "求订阅", "求打赏", "求鲜花", "求评价票"],
    "联系方式": ["QQ群", "微信群", "公众号", "微信号", "书友群"],
    "盗版站名": ["笔力阅读网", "(?i)biliyd", "阅笔小说网", "(?i)yoabc", "润文网", "笔趣阁"],
}

# 头图边缘样式（两字简洁命名）
EDGE_STYLES = [
    ("plain",      "方正"),
    ("cloud",      "云边"),
    ("mist",       "雾边"),
    ("brush",      "拖墨"),
    ("roughoval",  "糙圆"),
    ("watercolor", "晕染"),
    ("film",       "胶片"),
    ("tornside",   "撕边"),
    ("tornframe",  "撕框"),
    ("brushframe", "笔刷"),
    ("deckle",     "毛边"),
]

DEFAULT_SETTINGS = {
    "toc_regex": DEFAULT_TOC_REGEX,
    "toc_page": True, "panel_alpha": 0.6, "toc_bg_rotate": 1,
    "title_size": 0.92, "title_bold": True, "output_dir": "",
    # 边距单位为页面宽度/高度的百分比（%），不随阅读器字号膨胀，0=交给阅读器自己控制
    "layout": {"margin_t": 0.0, "margin_r": 4.0, "margin_b": 0.0, "margin_l": 4.0,
               "para_spacing": 0.35, "line_height": 1.8, "indent_em": 2.0,
               "drop_cap": False, "drop_size": 2.8, "drop_font": "", "drop_color": "#000000",
               "custom_css": ""},
    # text_fonts：选中文字指定字体 {chapter(0基), text(精确文字), font(字体key)}
    "text_fonts": [],
    "notes": {"font": "", "color": "#000000", "size": 0.85, "bold": False, "italic": False,
              "icon": ""},   # icon: 注释标记小图标（icons/ 下的文件名，空=默认 [注N] 文字标记）
    "styles": [dict(STYLE_PRESETS[0], enabled=True, font="dlg", color="#000000",
                    size=1.0, bold=False, italic=False)],   # 默认启用中文双引号→dlg字体，可在界面增删
    # {key,name,scope,regex,enabled,font,color,size,bold,italic}
    "ads_patterns": sum(AD_PRESETS.values(), []),
    "fonts": {"body": "", "dlg": "", "title": "", "toc": ""},
    "cover": "", "cover_w": 1200, "toc_bgs": [], "toc_bg_w": 880, "toc_bg_size": "100% auto",
    # header.assign：每张头图可指定章号（1开始，如 "1,4,9"），命中章固定用该图，其余章按 rotate 规则
    "header": {"enabled": True, "rotate": True, "images": [], "assign": [], "width": 1080, "height": 500,
               "margin_t": 0, "margin_r": 0, "margin_b": 0, "margin_l": 0, "edge": "cloud"},
    # illust/illust2：全屏插图页。"mode": every_n 每 N 章 / after 指定章后 / anchor 按文字或章节定位
    #   anchor: {chapters:[章索引], text:"定位文字", pos:"after|before"}  pos=文字位置，章节前后由 pos 决定
    "illust": {"images": [], "mode": "every_n", "every_n": 25, "after": [], "rotate": True,
               "width_pct": 100, "anchors": []},
    # inline_images：{path, chapter, para, where(before/after), width_pct, wrap}
    #   也支持 {path, anchor_chapter, anchor_text, anchor_pos(before/after), ...} 按正文文字定位
    "inline_images": [],
    "image_quality": 100,  # 30/50/70/100
    "meta": {"intro": "", "publisher": "", "isbn": "", "pubdate": "", "language": "zh-CN", "tags": []},
}

def deep_fill(d, defaults):
    """用默认值补齐缺失键"""
    for k, v in defaults.items():
        if k not in d:
            d[k] = json.loads(json.dumps(v))
        elif isinstance(v, dict) and isinstance(d.get(k), dict):
            deep_fill(d[k], v)
    return d

# ================= 解析 =================

TITLE_RE = re.compile(r"^第.{1,12}章")
TERMINAL = "。！？”…』」"

def _cn_num(n):
    units = "零一二三四五六七八九"
    if n <= 10:
        return "十" if n == 10 else units[n]
    if n < 20:
        return "十" + (units[n % 10] if n % 10 else "")
    if n < 100:
        s = units[n // 10] + "十"
        return s + (units[n % 10] if n % 10 else "")
    s = units[n // 100] + "百"
    r = n % 100
    if r == 0:
        return s
    if r < 10:
        return s + "零" + units[r]
    return s + _cn_num(r)

def normalize_numeric_titles(chapters):
    for ch in chapters:
        m = re.match(r"^(\d{1,4})[、,，.：: ]+\s*(.*)$", ch["title"])
        if m:
            ch["title"] = f"第{_cn_num(int(m.group(1)))}章" + (" " + m.group(2) if m.group(2) else "")
    return chapters

def merge_duplicate_chapters(chapters):
    merged = []
    for ch in chapters:
        if merged and merged[-1]["title"] == ch["title"]:
            prev, seg = merged[-1]["paras"], ch["paras"]
            if prev and seg and prev[-1] and prev[-1][-1] not in TERMINAL:
                prev[-1] += seg[0]
                prev.extend(seg[1:])
            else:
                prev.extend(seg)
        else:
            merged.append({"title": ch["title"], "paras": list(ch["paras"]),
                           "volume": ch.get("volume")})
    return merged

def parse_txt(text, pattern=None):
    rx = None
    if pattern:
        try:
            rx = re.compile(pattern)
        except re.error:
            rx = None
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    chapters, cur_title, cur_paras = [], None, []
    def is_title(s):
        if rx:
            return bool(rx.match(s))
        return bool(TITLE_RE.match(s))
    for ln in lines:
        s = ln.strip()
        if s and is_title(s):
            if cur_title is not None:
                chapters.append({"title": cur_title, "paras": cur_paras})
            cur_title, cur_paras = s, []
        elif cur_title is not None and s:
            cur_paras.append(ln.rstrip())
    if cur_title is not None:
        chapters.append({"title": cur_title, "paras": cur_paras})
    if not chapters:
        chapters = [{"title": "正文", "paras": [l for l in lines if l.strip()]}]
    return chapters

def read_txt_file(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8", "gbk", "utf-16", "big5"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")

P_RE = re.compile(r"<p[^>]*>.*?</p>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")

def _clean_html(s):
    return htmlmod.unescape(TAG_RE.sub("", s)).strip()

def parse_epub(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    toc_list = []
    ncx_name = next((n for n in names if n.lower().endswith(".ncx")), None)
    if ncx_name:
        s = z.read(ncx_name).decode("utf-8", errors="ignore")
        for t, src in re.findall(r"<navPoint[^>]*>.*?<text>(.*?)</text>.*?<content src=\"(.*?)\"/>", s, re.S):
            t = _clean_html(t)
            if "#" in src:
                f, a = src.split("#", 1)
            else:
                f, a = src, ""
            toc_list.append((t, f, a))
    toc_list = [x for x in toc_list if x[0] not in ("封面", "目录")]
    chapters = []
    if toc_list and any(a for _, _, a in toc_list):
        id_re = re.compile(r'id="(calibre_toc_\d+)"')
        anchor2ch = {a: i for i, (_, _, a) in enumerate(toc_list) if a}
        titles = [t for t, _, _ in toc_list]
        files = []
        for _, f, _ in toc_list:
            if f not in files:
                files.append(f)
        bufs = [[] for _ in toc_list]
        pre, started, cur = [], False, -1
        for f in files:
            try:
                doc = z.read(f).decode("utf-8", errors="ignore")
            except KeyError:
                continue
            m = re.search(r"<body[^>]*>(.*)</body>", doc, re.S | re.I)
            if not m:
                continue
            for pm in P_RE.finditer(m.group(1)):
                ids = id_re.findall(pm.group(0))
                text = _clean_html(pm.group(0))
                if not text:
                    continue
                if ids and ids[0] in anchor2ch:
                    cur = anchor2ch[ids[0]]
                    started = True
                    if text != titles[cur]:  # 锚点段即标题，跳过防重复
                        bufs[cur].append(text)
                elif started:
                    bufs[cur].append(text)
                else:
                    pre.append(text)
        if bufs:
            bufs[0] = pre + bufs[0]
        chapters = [{"title": t, "paras": p} for (t, _, _), p in zip(toc_list, bufs) if p]
    else:
        opf = next((n for n in names if n.lower().endswith(".opf")), None)
        files = []
        if opf:
            base = os.path.dirname(opf)
            s = z.read(opf).decode("utf-8", errors="ignore")
            idref = re.findall(r'<itemref[^>]*idref="([^"]+)"', s)
            hrefs = dict(re.findall(r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"', s))
            hrefs.update(dict((i, h) for h, i in re.findall(r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"', s)))
            files = [os.path.join(base, hrefs[i]).replace("\\", "/") for i in idref
                     if i in hrefs and hrefs[i].lower().endswith((".html", ".xhtml", ".htm"))]
        else:
            files = [n for n in names if n.lower().endswith((".html", ".xhtml")) and "nav" not in n.lower()]
        for i, f in enumerate(files):
            try:
                doc = z.read(f).decode("utf-8", errors="utf-8" if False else "ignore")
            except KeyError:
                continue
            m = re.search(r"<body[^>]*>(.*)</body>", doc, re.S | re.I)
            if not m:
                continue
            hm = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", m.group(1), re.S | re.I)
            title = _clean_html(hm.group(1)) if hm else f"第{_cn_num(i+1)}章"
            paras = [t for t in (_clean_html(x) for x in P_RE.findall(m.group(1))) if t and t != title]
            if paras:
                chapters.append({"title": title or f"第{_cn_num(i+1)}章", "paras": paras})
    if not chapters:
        raise ValueError("未能从 EPUB 中解析出章节")
    return chapters

# ================= 边缘样式蒙版 =================

def _pil():
    from PIL import Image, ImageDraw, ImageFilter, ImageChops
    return Image, ImageDraw, ImageFilter, ImageChops

def _rot_ellipse(w, h, cx, cy, rw, rh, angle):
    """生成旋转椭圆透明层"""
    Image, ImageDraw, _, _ = _pil()
    layer = Image.new("L", (w, h), 0)
    e = Image.new("L", (int(rw*2)+4, int(rh*2)+4), 0)
    ImageDraw.Draw(e).ellipse([2, 2, int(rw*2)+2, int(rh*2)+2], fill=255)
    e = e.rotate(angle, expand=True, resample=Image.BICUBIC)
    layer.paste(e, (int(cx - e.width/2), int(cy - e.height/2)), e)
    return layer

def mask_plain(w, h, seed):
    Image, *_ = _pil()
    return Image.new("L", (w, h), 255)

def mask_cloud(w, h, seed):
    """底部云雾边：底部约 1/4 高度呈云朵状渐隐到全透明（尺寸随图缩放）"""
    Image, ImageDraw, ImageFilter, ImageChops = _pil()
    rnd = random.Random(seed)
    zone = int(h * 0.26)                 # 云雾区高度
    edge = h - zone                      # 实体区下沿
    rmax = max(18, int(zone * 0.75))
    # 云朵形状：实体矩形 + 下沿一排交错重叠的圆（高低错落）
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([0, 0, w, edge], fill=255)
    x = -rmax
    while x < w + rmax:
        r = rnd.randint(int(rmax * 0.45), rmax)
        cy = edge + rnd.randint(0, int(zone * 0.55))
        md.ellipse([x - r, cy - r, x + r, cy + r], fill=255)
        x += int(r * rnd.uniform(0.9, 1.4))
    # 少量下垂的小雾团
    for _ in range(10):
        r = rnd.randint(int(rmax * 0.2), int(rmax * 0.45))
        cx = rnd.randint(0, w)
        cy = edge + rnd.randint(int(zone * 0.4), int(zone * 0.9))
        md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(8, h // 45)))
    # 垂直渐隐渐变：edge 处 255 → 底部 0，保证渐隐到全透明
    grad = Image.new("L", (1, h), 255)
    gd = ImageDraw.Draw(grad)
    for y in range(edge, h):
        t = (y - edge) / max(1, h - 1 - edge)
        gd.point((0, y), fill=int(255 * (1 - t) ** 1.3))
    grad = grad.resize((w, h))
    return ImageChops.multiply(mask, grad)

def mask_mist(w, h, seed):
    """四边雾化"""
    Image, ImageDraw, ImageFilter, ImageChops = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([55, 45, w-55, h-45], fill=255)
    for _ in range(70):
        side = rnd.choice("tblr")
        if side == "t":   cx, cy = rnd.randint(0, w), rnd.randint(0, 70)
        elif side == "b": cx, cy = rnd.randint(0, w), rnd.randint(h-70, h)
        elif side == "l": cx, cy = rnd.randint(0, 70), rnd.randint(0, h)
        else:             cx, cy = rnd.randint(w-70, w), rnd.randint(0, h)
        r = rnd.randint(18, 55)
        md.ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(22))

def mask_splash(w, h, seed):
    """核心矩形 + 四周飞溅墨点"""
    Image, ImageDraw, ImageFilter, _ = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([60, 50, w-60, h-50], fill=255)
    for _ in range(260):
        side = rnd.choice("tblr")
        if side == "t":   cx, cy = rnd.randint(0, w), int(50 + rnd.gauss(0, 28))
        elif side == "b": cx, cy = rnd.randint(0, w), int(h-50 + rnd.gauss(0, 28))
        elif side == "l": cx, cy = int(60 + rnd.gauss(0, 28)), rnd.randint(0, h)
        else:             cx, cy = int(w-60 + rnd.gauss(0, 28)), rnd.randint(0, h)
        r = max(2, int(rnd.gauss(8, 6)))
        md.ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(3))

def mask_diag(w, h, seed):
    """斜向大笔刷（右上→左下削角）"""
    Image, ImageDraw, ImageFilter, ImageChops = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 255)
    cut = Image.new("L", (w, h), 0)
    for i in range(7):
        cx = w * (0.45 + 0.09 * i) + rnd.randint(-20, 20)
        cy = h * 0.78 + rnd.randint(-25, 25)
        layer = _rot_ellipse(w, h, cx, cy, rnd.randint(180, 320), rnd.randint(14, 30), -18 + rnd.randint(-4, 4))
        cut = ImageChops.lighter(cut, layer)
    cut = cut.filter(ImageFilter.GaussianBlur(9))
    return ImageChops.subtract(mask, cut)

def mask_brush(w, h, seed):
    """底部横向拖墨"""
    Image, ImageDraw, ImageFilter, ImageChops = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([0, 0, w, h-55], fill=255)
    for i in range(5):
        cx = w * 0.35 + i * w * 0.14 + rnd.randint(-15, 15)
        layer = _rot_ellipse(w, h, cx, h-40 + rnd.randint(-12, 12), rnd.randint(140, 260), rnd.randint(10, 22), -6 + rnd.randint(-3, 3))
        mask = ImageChops.lighter(mask, layer)
    return mask.filter(ImageFilter.GaussianBlur(8))

def mask_splatter_oval(w, h, seed):
    """椭圆主体 + 周围迸溅"""
    Image, ImageDraw, ImageFilter, _ = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([w*0.08, h*0.10, w*0.92, h*0.90], fill=255)
    for _ in range(120):
        cx = w/2 + (w*0.44) * rnd.gauss(0, 0.55)
        cy = h/2 + (h*0.42) * rnd.gauss(0, 0.55)
        r = max(2, int(rnd.gauss(6, 5)))
        md.ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(4))

def mask_rough_oval(w, h, seed):
    """粗糙边缘大椭圆"""
    import math
    Image, ImageDraw, ImageFilter, _ = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([w*0.06, h*0.08, w*0.94, h*0.92], fill=255)
    for _ in range(50):
        ang = rnd.uniform(0, 6.283)
        cx = w/2 + (w*0.44) * math.cos(ang) * rnd.uniform(0.92, 1.08)
        cy = h/2 + (h*0.42) * math.sin(ang) * rnd.uniform(0.92, 1.08)
        r = rnd.randint(8, 26)
        md.ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(10))

def mask_watercolor(w, h, seed):
    """多层柔和椭圆晕染"""
    Image, ImageDraw, ImageFilter, ImageChops = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    for _ in range(6):
        cx = w/2 + rnd.randint(-int(w*0.12), int(w*0.12))
        cy = h/2 + rnd.randint(-int(h*0.14), int(h*0.14))
        rw = rnd.randint(int(w*0.30), int(w*0.46))
        rh = rnd.randint(int(h*0.28), int(h*0.44))
        layer = _rot_ellipse(w, h, cx, cy, rw, rh, rnd.randint(-25, 25))
        mask = ImageChops.lighter(mask, layer)
    return mask.filter(ImageFilter.GaussianBlur(18))

# ---- 撕纸类边缘 ----

def mask_tornside(w, h, seed):
    """撕边：左右两端撕毛，上下平直（纸条撕断效果）"""
    import math
    Image, ImageDraw, ImageFilter, _ = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    inx = int(w * 0.055)
    depth = int(w * 0.04)
    # 主体
    md.rectangle([inx, 0, w - inx, h], fill=255)
    # 左右撕口：随机竖向锯齿向外补
    for side, base, out in (("l", inx, 0), ("r", w - inx, w)):
        pts = []
        n = 46
        for k in range(n + 1):
            y = int(h * k / n)
            d = base - int(rnd.uniform(0, depth)) if side == "l" else base + int(rnd.uniform(0, depth))
            pts.append((d, y))
        tail = [(0, h), (0, 0)] if side == "l" else [(w, h), (w, 0)]
        md.polygon(pts + tail, fill=255)
    # 撕口细纸纤维（密一点，柔化锯齿感）
    for _ in range(160):
        side = rnd.choice("lr")
        y = rnd.randint(0, h)
        ln = rnd.randint(4, 18)
        d = (inx + rnd.randint(-depth, 2)) if side == "l" else (w - inx - rnd.randint(-2, depth))
        md.line([(d, y), (d - ln if side == "l" else d + ln, y + rnd.randint(-4, 4))],
                fill=255, width=rnd.randint(1, 3))
    return mask.filter(ImageFilter.GaussianBlur(3))

def mask_tornframe(w, h, seed):
    """撕框：四边撕纸相框（照片撕出白边贴纸效果）"""
    import math
    Image, ImageDraw, ImageFilter, _ = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    inx, iny = int(w * 0.05), int(h * 0.08)
    md.rectangle([inx, iny, w - inx, h - iny], fill=255)
    dmax = int(min(w, h) * 0.045)
    for _ in range(130):
        side = rnd.choice("tblr")
        t = rnd.uniform(0.03, 0.97)
        depth = int(rnd.uniform(dmax * 0.3, dmax))
        half = max(3, int(dmax * rnd.uniform(0.6, 1.6)))
        outward = rnd.random() < 0.5
        if side == "t":
            cx, y = int(w * t), iny + rnd.randint(-8, 8)
            peak = y - depth if outward else y + depth
            md.polygon([(cx - half, y), (cx + half, y), (cx, peak)], fill=255 if outward else 0)
        elif side == "b":
            cx, y = int(w * t), h - iny + rnd.randint(-8, 8)
            peak = y + depth if outward else y - depth
            md.polygon([(cx - half, y), (cx + half, y), (cx, peak)], fill=255 if outward else 0)
        elif side == "l":
            cy, x = int(h * t), inx + rnd.randint(-8, 8)
            peak = x - depth if outward else x + depth
            md.polygon([(x, cy - half), (x, cy + half), (peak, cy)], fill=255 if outward else 0)
        else:
            cy, x = int(h * t), w - inx + rnd.randint(-8, 8)
            peak = x + depth if outward else x - depth
            md.polygon([(x, cy - half), (x, cy + half), (peak, cy)], fill=255 if outward else 0)
    # 四边细纤维
    for _ in range(150):
        side = rnd.choice("tblr")
        t = rnd.uniform(0, 1)
        ln = rnd.randint(3, 10)
        if side == "t":
            x, y = int(w * t), iny + rnd.randint(-4, 4)
            md.line([(x, y), (x + rnd.randint(-4, 4), y - ln)], fill=255, width=1)
        elif side == "b":
            x, y = int(w * t), h - iny + rnd.randint(-4, 4)
            md.line([(x, y), (x + rnd.randint(-4, 4), y + ln)], fill=255, width=1)
        elif side == "l":
            x, y = inx + rnd.randint(-4, 4), int(h * t)
            md.line([(x, y), (x - ln, y + rnd.randint(-4, 4))], fill=255, width=1)
        else:
            x, y = w - inx + rnd.randint(-4, 4), int(h * t)
            md.line([(x, y), (x + ln, y + rnd.randint(-4, 4))], fill=255, width=1)
    return mask.filter(ImageFilter.GaussianBlur(3))

def mask_deckle(w, h, seed):
    """毛边：底边细密纸纤维毛边（明信片裁切效果），其余三边平直"""
    Image, ImageDraw, ImageFilter, _ = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    cut = int(h * 0.035)
    md.rectangle([0, 0, w, h - cut], fill=255)
    # 底边纤维：密集细竖线向下伸
    x = 0
    while x < w:
        ln = rnd.randint(2, cut + int(h * 0.012))
        md.line([(x, h - cut), (x + rnd.randint(-2, 2), h - cut + ln)], fill=255,
                width=rnd.randint(1, 3))
        x += rnd.randint(2, 6)
    # 底边随机啃咬
    for _ in range(60):
        x = rnd.randint(0, w)
        up = rnd.randint(2, cut)
        md.polygon([(x - rnd.randint(2, 6), h - cut), (x + rnd.randint(2, 6), h - cut),
                    (x, h - cut + up)], fill=0)
    # 重新补纤维（啃咬可能吃掉部分）
    x = 0
    while x < w:
        if rnd.random() < 0.5:
            ln = rnd.randint(2, int(cut * 0.8))
            md.line([(x, h - cut - rnd.randint(0, 4)), (x, h - cut + ln)], fill=255, width=1)
        x += rnd.randint(3, 8)
    return mask.filter(ImageFilter.GaussianBlur(1))

def mask_brushframe(w, h, seed):
    """笔刷：干笔扫出的描边框（边缘切向笔触+飞白）"""
    Image, ImageDraw, ImageFilter, ImageChops = _pil()
    rnd = random.Random(seed)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    x0, y0, x1, y1 = int(w * 0.045), int(h * 0.10), int(w * 0.955), int(h * 0.90)
    md.rounded_rectangle([x0, y0, x1, y1], radius=int(min(w, h) * 0.05), fill=255)
    # 边缘补笔：切向长条干笔明显出血
    for _ in range(140):
        side = rnd.choice("tblr")
        t = rnd.uniform(0.02, 0.98)
        th = max(2, int(min(w, h) * rnd.uniform(0.004, 0.014)))
        ln = min(w, h) * rnd.uniform(0.04, 0.16)
        bleed = int(min(w, h) * rnd.uniform(0.005, 0.028))
        if side == "t":
            cx, cy = w * t, y0 + rnd.randint(-5, 5) - bleed
            layer = _rot_ellipse(w, h, cx, cy, ln / 2, th, rnd.uniform(-4, 4))
        elif side == "b":
            cx, cy = w * t, y1 + rnd.randint(-5, 5) + bleed
            layer = _rot_ellipse(w, h, cx, cy, ln / 2, th, rnd.uniform(-4, 4))
        elif side == "l":
            cx, cy = x0 + rnd.randint(-5, 5) - bleed, h * t
            layer = _rot_ellipse(w, h, cx, cy, th, ln / 2, rnd.uniform(-4, 4))
        else:
            cx, cy = x1 + rnd.randint(-5, 5) + bleed, h * t
            layer = _rot_ellipse(w, h, cx, cy, th, ln / 2, rnd.uniform(-4, 4))
        mask = ImageChops.lighter(mask, layer)
    # 飞白：边缘内侧减去细长条
    for _ in range(30):
        side = rnd.choice("tblr")
        t = rnd.uniform(0.05, 0.95)
        if side == "t":
            cy = y0 + rnd.randint(2, 10)
            md.line([(w * t - rnd.randint(20, 60), cy), (w * t + rnd.randint(20, 60), cy)], fill=0, width=rnd.randint(1, 3))
        elif side == "b":
            cy = y1 - rnd.randint(2, 10)
            md.line([(w * t - rnd.randint(20, 60), cy), (w * t + rnd.randint(20, 60), cy)], fill=0, width=rnd.randint(1, 3))
        elif side == "l":
            cx = x0 + rnd.randint(2, 10)
            md.line([(cx, h * t - rnd.randint(15, 45)), (cx, h * t + rnd.randint(15, 45))], fill=0, width=rnd.randint(1, 2))
        else:
            cx = x1 - rnd.randint(2, 10)
            md.line([(cx, h * t - rnd.randint(15, 45)), (cx, h * t + rnd.randint(15, 45))], fill=0, width=rnd.randint(1, 2))
    return mask.filter(ImageFilter.GaussianBlur(1.5))

MASK_FUNCS = {
    "plain": mask_plain, "cloud": mask_cloud, "mist": mask_mist, "splash": mask_splash,
    "diag": mask_diag, "brush": mask_brush, "splatter": mask_splatter_oval,
    "roughoval": mask_rough_oval, "watercolor": mask_watercolor,
    "tornside": mask_tornside, "tornframe": mask_tornframe,
    "deckle": mask_deckle, "brushframe": mask_brushframe,
}

def apply_film_frame(im):
    """胶片齿孔框：黑边 + 上下打孔"""
    Image, ImageDraw, *_ = _pil()
    w, h = im.size
    border = max(14, h // 14)
    canvas = Image.new("RGB", (w + border*2, h + border*2 + border), (15, 15, 15))
    canvas.paste(im, (border, border + border//2))
    d = ImageDraw.Draw(canvas)
    hole_w, hole_h = max(10, border//2), max(6, border//3)
    for y0 in (border//4, canvas.height - border + border//4):
        x = border
        while x < canvas.width - border:
            d.rounded_rectangle([x, y0, x+hole_w, y0+hole_h], radius=3, fill=(245, 245, 245))
            x += hole_w * 2
    return canvas

def make_edge_preview(key, out, w=360, h=180):
    """生成某种边缘样式的示意图：演示底图 + 对应边缘效果，白底 PNG。"""
    Image, ImageDraw, *_ = _pil()
    # 演示底图：青绿山水渐变 + 太阳 + 远山，能看清任何边缘裁切效果
    demo = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(demo)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(210 - 60 * t); g = int(235 - 45 * t); b = int(225 - 20 * t)
        d.line([(0, y), (w, y)], fill=(r, g, b))
    d.ellipse([int(w*0.68), int(h*0.10), int(w*0.84), int(h*0.10)+int(w*0.16)], fill=(244, 196, 110))  # 日
    d.polygon([(0, int(h*0.78)), (int(w*0.28), int(h*0.42)), (int(w*0.55), int(h*0.78))], fill=(96, 148, 128))   # 远山
    d.polygon([(int(w*0.4), int(h*0.82)), (int(w*0.72), int(h*0.50)), (w, int(h*0.82))], fill=(70, 122, 104))    # 近山
    d.rectangle([0, int(h*0.80), w, h], fill=(52, 102, 88))  # 地面
    if key == "film":
        demo = apply_film_frame(demo)
        demo.save(out)
        return out
    if key == "plain":
        demo.save(out)
        return out
    fn = MASK_FUNCS.get(key, mask_cloud)
    rgba = demo.convert("RGBA")
    rgba.putalpha(fn(w, h, 7))
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    bg.paste(rgba, (0, 0), rgba)
    bg.convert("RGB").save(out)
    return out

# ================= 图片处理 =================

def crop_cover_ratio(im, ratio, anchor=0.5):
    w, h = im.size
    if w / h > ratio:
        nw = int(h * ratio); left = int((w - nw) * 0.5)
        return im.crop((left, 0, left + nw, h))
    nh = int(w / ratio); top = int((h - nh) * anchor)
    return im.crop((0, top, w, top + nh))

def save_compressed(im, out_jpg, quality):
    """按质量保存为 JPEG（quality>=100 用 90 上限）"""
    Image, *_ = _pil()
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        im2 = im.convert("RGBA")
        bg.paste(im2, (0, 0), im2)
        im = bg
    else:
        im = im.convert("RGB")
    im.save(out_jpg, quality=max(10, min(95, quality if quality < 100 else 90)))
    return out_jpg

def make_header(src, out_base, cfg, quality=100, seed=7):
    """返回生成文件名。plain/film 或 quality<100 → jpg；其余透明边缘 → png"""
    Image, *_ = _pil()
    tw, th = int(cfg.get("width", 1080)), int(cfg.get("height", 500))
    edge = cfg.get("edge", "cloud")
    im = Image.open(src).convert("RGB")
    im = crop_cover_ratio(im, tw / th, 0.5).resize((tw, th), Image.LANCZOS)
    if edge == "film":
        im2 = apply_film_frame(im)
        save_compressed(im2, out_base + ".jpg", quality)
        return os.path.basename(out_base + ".jpg")
    if edge == "plain":
        save_compressed(im, out_base + ".jpg", quality)
        return os.path.basename(out_base + ".jpg")
    fn = MASK_FUNCS.get(edge, mask_cloud)
    rgba = im.convert("RGBA")
    rgba.putalpha(fn(tw, th, seed))
    rgba.save(out_base + ".png")
    return os.path.basename(out_base + ".png")

def make_tocbg(src, out, maxw=880, quality=100):
    Image, *_ = _pil()
    im = Image.open(src).convert("RGB")
    if maxw and maxw > 0 and im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    save_compressed(im, out, quality)
    return os.path.basename(out)

def make_illust(src, out, maxw=1024, maxh=2048, quality=100):
    Image, *_ = _pil()
    im = Image.open(src).convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    if im.height > maxh:
        im = im.crop((0, 0, im.width, maxh))
    save_compressed(im, out, quality)
    return os.path.basename(out)

def make_cover(src, out, maxw=1200, quality=100):
    """maxw<=0 表示不缩放，保持原图尺寸"""
    Image, *_ = _pil()
    im = Image.open(src).convert("RGB")
    if maxw and maxw > 0 and im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    save_compressed(im, out, quality)
    return os.path.basename(out)

def make_inline(src, out_base, quality=100, maxw=1080):
    Image, *_ = _pil()
    im = Image.open(src)
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
    has_alpha = im.mode in ("RGBA", "LA") and min(im.convert("RGBA").getchannel("A").getextrema()) < 250
    if has_alpha and quality >= 100:
        im.save(out_base + ".png")
        return os.path.basename(out_base + ".png")
    save_compressed(im, out_base + ".jpg", quality)
    return os.path.basename(out_base + ".jpg")

# ================= 文字样式 & 注释 =================

NOTE_RE = re.compile(r"\{\{注:(.*?)\}\}", re.S)

# 内置注释标记小图标目录（epub-studio/icons/*.png）
ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

def list_note_icons():
    """返回内置注释图标 [{"key": 文件名去扩展名, "name": key}]"""
    if not os.path.isdir(ICONS_DIR):
        return []
    return [{"key": os.path.splitext(f)[0], "name": os.path.splitext(f)[0]}
            for f in sorted(os.listdir(ICONS_DIR)) if f.lower().endswith(".png")]

def para_to_html(p, styles, tf_rules=None, note_icon=False):
    """返回 (段落html, [注释...], block_style_keys)
    tf_rules: 选中文字字体规则 [{"text":精确文字, "font":字体key}]，命中第一条包裹 span
    note_icon: True 时注释标记渲染为小图标（images/noteicon.png）"""
    notes = []
    def _note_sub(m):
        notes.append(m.group(1))
        return f"\x00NOTE{len(notes)-1}\x00"
    txt = NOTE_RE.sub(_note_sub, p)
    block_keys = [s["key"] for s in styles
                  if s.get("enabled") and s.get("scope") == "block" and s["_rx"] and s["_rx"].match(txt.strip())]
    esc = htmlmod.escape(txt, quote=False)
    # 选中文字自定义字体（先于样式规则包裹，保证精确命中原文）
    for tf in (tf_rules or []):
        needle = htmlmod.escape(tf["text"], quote=False)
        pos = esc.find(needle)
        if pos >= 0:
            esc = (esc[:pos] + f'<span class="tf_{tf["font"]}">' + needle
                   + "</span>" + esc[pos + len(needle):])
    for s in styles:
        if s.get("enabled") and s.get("scope") != "block" and s["_rx"]:
            esc = s["_rx"].sub(lambda m: f'<span class="sty_{s["key"]}">{m.group(0)}</span>', esc)
    if note_icon:
        esc = re.sub(r"\x00NOTE(\d+)\x00",
                     lambda m: (f'<a epub:type="noteref" href="#NOTE_HREF_{m.group(1)}" class="note-ref" '
                                f'id="NOTE_REF_{m.group(1)}"><img class="note-ico" src="../images/noteicon.png" '
                                f'alt="注{int(m.group(1))+1}"/></a>'),
                     esc)
    else:
        esc = re.sub(r"\x00NOTE(\d+)\x00",
                     lambda m: f'<a epub:type="noteref" href="#NOTE_HREF_{m.group(1)}" class="note-ref" id="NOTE_REF_{m.group(1)}">[注{int(m.group(1))+1}]</a>',
                     esc)
    return esc, notes, block_keys

def compile_styles(styles):
    out = []
    for s in styles:
        s = dict(s)
        try:
            s["_rx"] = re.compile(s["regex"])
        except (re.error, KeyError):
            s["enabled"] = False
            s["_rx"] = None
        out.append(s)
    return out

def style_css(s):
    parts = []
    if s.get("font"):   parts.append(f'font-family: "{s["font"]}"')
    if s.get("color"):  parts.append(f'color: {s["color"]}')
    if s.get("size") and float(s.get("size", 1) or 1) != 1.0:
        parts.append(f'font-size: {s["size"]}em')
    if s.get("bold"):   parts.append("font-weight: bold")
    if s.get("italic"): parts.append("font-style: italic")
    return "; ".join(parts) + (";" if parts else "")

# ================= EPUB 组装 =================

def subset_font(src, chars_file, out, pylibs):
    env = dict(os.environ)
    env["PYTHONPATH"] = pylibs
    r = subprocess.run(
        [sys.executable, "-m", "fontTools.subset", src,
         "--text-file=" + chars_file, "--output-file=" + out,
         "--layout-features=*", "--no-hinting",
         "--drop-tables+=SVG,sbix"],
        capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError("字体子集化失败: " + (r.stderr or r.stdout)[-500:])
    return out

def build_epub(book, work_dir, out_path, pylibs, log=print):
    st = deep_fill(book["settings"], DEFAULT_SETTINGS)
    title, author = book["title"], book.get("author", "")
    meta = st["meta"]
    chapters = book["chapters"]
    lay = st["layout"]
    quality = int(st.get("image_quality", 100))
    assets_dir = os.path.join(work_dir, "build_assets")
    os.makedirs(assets_dir, exist_ok=True)
    styles = compile_styles(st.get("styles", []))
    if not styles and st.get("dlg_enabled"):
        styles = compile_styles([{"key": "dlg_cn", "name": "中文双引号", "scope": "inline",
                                  "regex": "“[^”]*”", "enabled": True,
                                  "font": "dlg", "color": st.get("dlg_color", "#000000"),
                                  "size": 1.0, "bold": False, "italic": False}])

    # ---- 字符集 + 字体子集化 ----
    note_texts = "".join("".join(NOTE_RE.findall(p)) for c in chapters for p in c["paras"])
    all_text = (title + author + meta.get("intro", "") + note_texts
                + "".join((c.get("volume") or "") + c["title"] + "".join(c["paras"]) for c in chapters))
    extra = ("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
             "，。、：；！？（）《》“”‘’—…·【】〈〉〔〕「」『』～％￥＋－＝×÷°©®™↩注[] "
             + title + author + "目录封面插图卷")
    chars = "".join(sorted(set(all_text + extra)))
    chars_file = os.path.join(assets_dir, "chars.txt")
    open(chars_file, "w", encoding="utf-8").write(chars)
    log(f"字符集 {len(set(all_text + extra))} 字")

    fonts = {}   # key -> epub内文件名
    for key, src in st["fonts"].items():
        if src and os.path.isfile(src):
            out = os.path.join(assets_dir, f"f_{key}.ttf")
            subset_font(src, chars_file, out, pylibs)
            fonts[key] = f"f_{key}.ttf"
            log(f"子集 {key}: {os.path.getsize(out)/1048576:.2f} MB")
    body_font = "body" if "body" in fonts else (next(iter(fonts)) if fonts else "")

    # ---- 图片素材 ----
    images = {}
    cover_fn = None
    if st.get("cover") and os.path.isfile(st["cover"]):
        out = os.path.join(assets_dir, "cover.jpg")
        cover_fn = make_cover(st["cover"], out, maxw=int(st.get("cover_w") or 0), quality=quality)
        images["images/" + cover_fn] = os.path.join(assets_dir, cover_fn)

    hcfg = st["header"]
    headers = []          # 轮换用图片列表
    header_fixed = {}     # 章索引(0基) -> 固定头图文件名（assign 指定）
    src_imgs = hcfg.get("images", [])
    if hcfg.get("enabled") and src_imgs:
        # 先处理全部图（指定章号可能引用任意一张），再取轮换子集
        img_files = {}
        for i, h in enumerate(src_imgs):
            if os.path.isfile(h):
                fn = make_header(h, os.path.join(assets_dir, f"head{i}"), hcfg, quality, seed=7 + i)
                img_files[i] = fn
                images["images/" + fn] = os.path.join(assets_dir, fn)
        use = src_imgs if hcfg.get("rotate", True) else src_imgs[:1]
        for i, h in enumerate(use):
            if os.path.isfile(h):
                headers.append(img_files[i])
        for a in hcfg.get("assign", []):
            try:
                img_i = int(a.get("img", 0))
            except (TypeError, ValueError):
                continue
            if img_i not in img_files:
                continue
            for cs in re.split(r"[,，、;；\s]+", str(a.get("chapters") or "")):
                if cs.strip().isdigit():
                    cn = int(cs)
                    if cn >= 1:
                        header_fixed[cn - 1] = img_files[img_i]

    icfg = st["illust"]
    illusts = []
    for i, g in enumerate(icfg.get("images", [])):
        if os.path.isfile(g):
            out = os.path.join(assets_dir, f"ill{i}.jpg")
            fn = make_illust(g, out, quality=quality)
            illusts.append(fn)
            images["images/" + fn] = os.path.join(assets_dir, fn)

    toc_bgs = []
    toc_bg_maxw = int(st.get("toc_bg_w") or 0)   # 0 = 不缩放
    for i, g in enumerate(st.get("toc_bgs", [])):
        if os.path.isfile(g):
            out = os.path.join(assets_dir, f"tocbg{i}.jpg")
            fn = make_tocbg(g, out, maxw=toc_bg_maxw, quality=quality)
            toc_bgs.append(fn)
            images["images/" + fn] = os.path.join(assets_dir, fn)

    # 注释标记小图标（替代 [注N] 文字标记）
    note_icon_on = False
    if st["notes"].get("icon"):
        icon_src = os.path.join(ICONS_DIR, st["notes"]["icon"] + ".png")
        if os.path.isfile(icon_src):
            with open(icon_src, "rb") as fh:
                data = fh.read()
            with open(os.path.join(assets_dir, "noteicon.png"), "wb") as fh:
                fh.write(data)
            images["images/noteicon.png"] = os.path.join(assets_dir, "noteicon.png")
            note_icon_on = True

    # 选中文字自定义字体：按章分组
    tf_by_ch = {}
    for tf in st.get("text_fonts", []):
        if tf.get("text") and tf.get("font"):
            try:
                tf_by_ch.setdefault(int(tf.get("chapter") or 0), []).append(tf)
            except (TypeError, ValueError):
                pass

    def find_para(ci, text, pos="after"):
        """在章 ci 的段落里找第一条包含 text 的段落，返回 (段索引, 段前/段后)。
        pos: after=该段之后插入；before=该段之前插入。找不到返回 None。"""
        if ci < 0 or ci >= len(chapters) or not text:
            return None
        for j, p in enumerate(chapters[ci]["paras"]):
            if text in p:
                return (j, "after" if pos == "after" else "before")
        return None

    inline_map = {}   # chapter -> {para -> [(where, html)]}
    for iid, im_cfg in enumerate(st.get("inline_images", [])):
        src = im_cfg.get("path", "")
        if not os.path.isfile(src):
            continue
        out_base = os.path.join(assets_dir, f"inline{iid}")
        fn = make_inline(src, out_base, quality=quality)
        images["images/" + fn] = os.path.join(assets_dir, fn)
        wp = int(im_cfg.get("width_pct", 60))
        wrap = im_cfg.get("wrap", "block")
        if wrap == "float_left":
            h_html = f'<img class="fig fl" src="../images/{fn}" style="width:{wp}%" alt="插图"/>'
        elif wrap == "float_right":
            h_html = f'<img class="fig fr" src="../images/{fn}" style="width:{wp}%" alt="插图"/>'
        else:
            h_html = f'<div class="fig block"><img src="../images/{fn}" style="width:{wp}%" alt="插图"/></div>'
        # 优先按锚定文字定位（正文编辑里选中文字插入）
        hit = None
        if im_cfg.get("anchor_text"):
            hit = find_para(int(im_cfg.get("anchor_chapter") or 0), im_cfg["anchor_text"],
                            im_cfg.get("anchor_pos", "after"))
        if hit:
            ci, (pi, where) = int(im_cfg.get("anchor_chapter") or 0), hit
        else:
            ci, pi = int(im_cfg.get("chapter", 0)), int(im_cfg.get("para", 0))
            where = im_cfg.get("where", "after")
        inline_map.setdefault(ci, {}).setdefault(pi, []).append((where, h_html))

    # ---- CSS ----
    css = []
    for key, fn in fonts.items():
        css.append(f'@font-face {{ font-family: "{key}"; src: url("fonts/{fn}"); }}')
    css.append(f'body {{ font-family: "{body_font}", serif; margin: 0; padding: 0; color: #000; }}')
    # 边距用百分比：em 会随阅读器字号放大，手机上大字号时会把正文挤成一条窄竖条
    mt, mr, mb, ml = (float(lay.get(k, 0) or 0) for k in ("margin_t", "margin_r", "margin_b", "margin_l"))
    if max(mt, mr, mb, ml) > 0:
        css.append(".content { margin: %g%% %g%% %g%% %g%%; }" % (mt, mr, mb, ml))
    else:
        css.append(".content { margin: 0; }")
    indent = f"text-indent: {lay['indent_em']}em;" if float(lay.get("indent_em", 2)) > 0 else ""
    lh = float(lay.get("line_height") or 1.8)
    css.append(f"p {{ {indent} line-height: {lh}; margin: {lay['para_spacing']}em 0; text-align: justify; }}")
    css.append("p.noind { text-indent: 0; }")
    for s in styles:
        if s.get("enabled"):
            css.append(f".sty_{s['key']} {{ {style_css(s)} }}")
    # 选中文字自定义字体
    for k in sorted({tf["font"] for rules in tf_by_ch.values() for tf in rules if tf.get("font") in fonts}):
        css.append(f'.tf_{k} {{ font-family: "{k}"; }}')
    bold = "bold" if st.get("title_bold", True) else "normal"
    tfont = 'font-family: "title";' if "title" in fonts else ""
    css.append(f"h1 {{ {tfont} text-align: center; font-weight: {bold}; font-size: {st['title_size']}em; margin: 0.5em 0 1.2em 0; }}")
    css.append(".chapter-img { margin: %spx %spx %spx %spx; text-align: center; }" % (
        hcfg.get("margin_t", 0), hcfg.get("margin_r", 0), hcfg.get("margin_b", 0), hcfg.get("margin_l", 0)))
    css.append(".chapter-img img { width: 100%; display: block; }")
    ncfg = st["notes"]
    nfont = f'font-family: "{ncfg["font"]}";' if ncfg.get("font") and ncfg["font"] in fonts else ""
    css.append("a.note-ref { font-size: 0.75em; vertical-align: super; text-decoration: none; color: inherit; }")
    css.append("a.note-ref img.note-ico { height: 1.6em; width: auto; vertical-align: -0.3em; border: 0; }")
    css.append(f"aside.footnote {{ {nfont} color: {ncfg.get('color','#000')}; font-size: {ncfg.get('size',0.85)}em;"
               f"{'font-weight: bold;' if ncfg.get('bold') else ''}{'font-style: italic;' if ncfg.get('italic') else ''}"
               " margin-top: 1.5em; border-top: 1px solid #999; padding-top: 0.5em; }")
    css.append("aside.footnote p { text-indent: 0; margin: 0.2em 0; }")
    if lay.get("drop_cap"):
        dfont = f'font-family: "{lay["drop_font"]}";' if lay.get("drop_font") and lay["drop_font"] in fonts else ""
        css.append(f".dropcap {{ float: left; {dfont} font-size: {lay.get('drop_size',2.8)}em; line-height: 0.85;"
                   f" padding: 0.05em 0.12em 0 0; color: {lay.get('drop_color','#000')}; }}")
    css.append(".fig.block { text-align: center; margin: 0.6em 0; clear: both; }")
    css.append("img.fig.fl { float: left; margin: 0.2em 1em 0.6em 0; }")
    css.append("img.fig.fr { float: right; margin: 0.2em 0 0.6em 1em; }")
    css.append(".coverpage, .fullpage { margin: 0; padding: 0; text-align: center; }")
    css.append(".coverpage img { width: 100%; display: block; }")
    # 目录背景：toc_bg_size 可为 cover / contain / 100% auto / 具体宽度百分比
    tbg_size = (st.get("toc_bg_size") or "100% auto")
    css.append(f"body.tocpage {{ background-size: {tbg_size}; background-repeat: repeat-y;"
               " background-position: top center; margin: 0; padding: 0; }")
    toc_font = 'font-family: "toc";' if "toc" in fonts else ""
    css.append(f".toc-inner {{ width: 70%; margin: 8% auto; background: rgba(255,255,255,{st['panel_alpha']});"
               f" border-radius: 12px; padding: 1.5em 1.2em; {toc_font} font-weight: bold; }}")
    css.append(".toc-head { text-align: center; font-size: 1.3em; margin-bottom: 1em; letter-spacing: 0.5em; }")
    css.append(".tv { font-size: 1.05em; margin: 1em 0 0.3em; border-bottom: 1px solid #999; padding-bottom: 0.2em; }")
    css.append(".titem { margin: 0.55em 0; font-size: 0.95em; line-height: 1.5; }")
    css.append(".titem a { text-decoration: none; color: #000; }")
    if lay.get("custom_css"):
        css.append(lay["custom_css"])
    files = {"styles.css": "\n".join(css).encode("utf-8")}

    for key, fn in fonts.items():
        files["fonts/" + fn] = open(os.path.join(assets_dir, fn), "rb").read()
    for ep, local in images.items():
        files[ep] = open(local, "rb").read()

    # ---- 页面骨架 ----
    spine_ids, manifest = [], []
    def add_page(pid, fn, html_str):
        files[fn] = html_str.encode("utf-8")
        spine_ids.append(pid)
        manifest.append(f'<item id="{pid}" href="{fn}" media-type="application/xhtml+xml"/>')

    PAGE = '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><meta charset="utf-8"/><title>%s</title>
<link rel="stylesheet" type="text/css" href="%sstyles.css"/></head>
%s
</html>'''

    if cover_fn:
        add_page("coverpage", "cover.xhtml", PAGE % ("封面", "",
            f'<body><div class="coverpage"><img src="images/{cover_fn}" alt="封面"/></div></body>'))

    # ---- 章节 ----
    style_hits = note_total = tf_hits = 0
    ch_files = []   # (index, title, fn, volume)
    for i, ch in enumerate(chapters):
        paras_html, ch_notes = [], []
        ch_tf = tf_by_ch.get(i, [])
        for j, p in enumerate(ch["paras"]):
            for where, h_html in inline_map.get(i, {}).get(j, []):
                if where == "before":
                    paras_html.append(h_html)
            htxt, notes, block_keys = para_to_html(p, styles, ch_tf, note_icon_on)
            tf_hits += htxt.count('class="tf_')
            for k, _ in enumerate(notes):
                htxt = htxt.replace(f"NOTE_HREF_{k}", f"fn_{i}_{len(ch_notes)+k}").replace(f"NOTE_REF_{k}", f"fnref_{i}_{len(ch_notes)+k}")
            ch_notes.extend(notes)
            classes = []
            if p.startswith(("　", " ")):
                classes.append("noind")
            classes += ["sty_" + k for k in block_keys]
            if lay.get("drop_cap") and not paras_html and htxt:
                plain = re.sub(r"<[^>]+>", "", htxt)
                if plain:
                    first = plain[0]
                    pos = htxt.find(first)
                    htxt = htxt[:pos] + f'<span class="dropcap">{first}</span>' + htxt[pos+1:]
                    if "noind" not in classes:
                        classes.append("noind")
            cls = f' class="{" ".join(classes)}"' if classes else ""
            paras_html.append(f"<p{cls}>{htxt}</p>")
            style_hits += htxt.count('class="sty_')
            for where, h_html in inline_map.get(i, {}).get(j, []):
                if where != "before":
                    paras_html.append(h_html)
        note_total += len(ch_notes)
        foot = "".join(
            f'<aside epub:type="footnote" id="fn_{i}_{k}" class="footnote"><p>[注{k+1}] {htmlmod.escape(n)}'
            f' <a href="#fnref_{i}_{k}">↩</a></p></aside>'
            for k, n in enumerate(ch_notes))
        head_html = ""
        fn_h = header_fixed.get(i) or (headers[i % len(headers)] if headers else None)
        if fn_h:
            head_html = f'<div class="chapter-img"><img src="../images/{fn_h}" alt=""/></div>\n'
        fn = f"chapters/ch{i:03d}.xhtml"
        add_page(f"ch{i}", fn, PAGE % (htmlmod.escape(ch["title"]), "../",
            f"<body>\n{head_html}<div class=\"content\">\n<h1>{htmlmod.escape(ch['title'])}</h1>\n"
            + "\n".join(paras_html) + f"\n{foot}\n</div>\n</body>"))
        ch_files.append((i, ch["title"], fn, ch.get("volume")))

        # 插图页
        if illusts:
            mode = icfg.get("mode", "every_n")
            insert_after = False
            gi = 0
            if mode == "every_n":
                every = int(icfg.get("every_n", 0) or 0)
                insert_after = every > 0 and (i + 1) % every == 0 and i + 1 < len(chapters)
                gi = (i + 1) // max(1, every) - 1
            elif mode == "after":
                after_list = [int(x) for x in icfg.get("after", [])]
                insert_after = i in after_list
                gi = after_list.index(i) if insert_after else 0
            else:   # anchor：按正文文字/章节定位（每章检查是否命中）
                hits = [(k, a) for k, a in enumerate(icfg.get("anchors", []))
                        if int(a.get("chapter") or 0) == i and a.get("text")]
                for k, a in hits:
                    if find_para(i, a["text"], a.get("pos", "after")):
                        add_page(f"ill{i}_{k}", f"illust_{i}_{k}.xhtml", PAGE % ("插图", "",
                            f'<body><div class="fullpage"><img src="images/{illusts[k % len(illusts)] if icfg.get("rotate", True) else illusts[0]}"'
                            f' style="width:{int(icfg.get("width_pct", 100))}%" alt="插图"/></div></body>'))
            if insert_after:
                g = illusts[gi % len(illusts)] if icfg.get("rotate", True) else illusts[0]
                wp = int(icfg.get("width_pct", 100))
                add_page(f"ill{i}", f"illust_{i}.xhtml", PAGE % ("插图", "",
                    f'<body><div class="fullpage"><img src="images/{g}" style="width:{wp}%" alt="插图"/></div></body>'))

    # ---- 目录页（分页 + 多背景轮换 + 分卷） ----
    if st.get("toc_page", True):
        per_page = 20
        rotate_n = max(1, int(st.get("toc_bg_rotate", 1)))
        pages = [ch_files[k:k+per_page] for k in range(0, len(ch_files), per_page)]
        for pi, page_items in enumerate(pages):
            style_attr = ""
            if toc_bgs:
                bg = toc_bgs[(pi // rotate_n) % len(toc_bgs)]
                style_attr = f' style="background-image:url(\'images/{bg}\')"'
            items_html = []
            last_vol = None
            for ci, t, fn, vol in page_items:
                if vol and vol != last_vol:
                    items_html.append(f'<div class="tv">{htmlmod.escape(vol)}</div>')
                    last_vol = vol
                items_html.append(f'<div class="titem"><a href="{fn}">{htmlmod.escape(t)}</a></div>')
            add_page(f"tocpage{pi}", f"tocpage{pi}.xhtml", PAGE % ("目录", "",
                f"<body class=\"tocpage\"{style_attr}>\n<div class=\"toc-inner\">\n"
                f"<div class=\"toc-head\">目 录</div>\n" + "\n".join(items_html) + "\n</div>\n</body>"))

    # ---- NAV / NCX（卷→章两级） ----
    entries = [("封面", "cover.xhtml", 1)] if cover_fn else []
    vol_seen = set()
    for i, t, fn, vol in ch_files:
        if vol:
            if vol not in vol_seen:
                vol_seen.add(vol)
                entries.append((vol, fn, 1))
            entries.append((t, fn, 2))
        else:
            entries.append((t, fn, 1))

    nav_html, depth = "", 0
    for t, fn, lv in entries:
        if lv == 2 and depth == 0:
            nav_html += "<ol>"; depth = 1
        if lv == 1 and depth == 1:
            nav_html += "</ol>"; depth = 0
        nav_html += f'<li><a href="{fn}">{htmlmod.escape(t)}</a></li>'
    if depth == 1:
        nav_html += "</ol>"
    add_page("nav", "nav.xhtml", PAGE % ("目录", "",
        f'<body><nav epub:type="toc"><h1>目录</h1><ol>{nav_html}</ol></nav></body>'))
    manifest[-1] = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'

    ncx_xml, open_vol, order = "", False, 0
    for idx, (t, fn, lv) in enumerate(entries):
        order += 1
        if lv == 1 and open_vol:
            ncx_xml += "</navPoint>"
            open_vol = False
        ncx_xml += (f'<navPoint id="np{order}" playOrder="{order}"><navLabel><text>{htmlmod.escape(t)}</text></navLabel>'
                    f'<content src="{fn}"/>')
        if lv == 1:
            has_children = idx + 1 < len(entries) and entries[idx+1][2] == 2
            if has_children:
                open_vol = True
            else:
                ncx_xml += "</navPoint>"
        else:
            ncx_xml += "</navPoint>"
    if open_vol:
        ncx_xml += "</navPoint>"
    files["toc.ncx"] = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="urn:epubstudio:{htmlmod.escape(title)}"/></head>
<docTitle><text>{htmlmod.escape(title)}</text></docTitle>
<navMap>{ncx_xml}</navMap>
</ncx>'''.encode("utf-8")
    manifest.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')

    manifest.append('<item id="css" href="styles.css" media-type="text/css"/>')
    for key, fn in fonts.items():
        manifest.append(f'<item id="font_{key}" href="fonts/{fn}" media-type="font/ttf"/>')
    for ep in images:
        ext = ep.rsplit(".", 1)[-1].lower()
        mt = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext)
        if not mt:
            continue
        iid = "img_" + ep.replace("/", "_").replace(".", "_")
        if cover_fn and ep == "images/" + cover_fn:
            manifest.append(f'<item id="cover-image" href="{ep}" media-type="{mt}" properties="cover-image"/>')
        else:
            manifest.append(f'<item id="{iid}" href="{ep}" media-type="{mt}"/>')

    isbn = meta.get("isbn", "").strip()
    isbn_xml = f'<dc:identifier id="isbn">urn:isbn:{htmlmod.escape(isbn)}</dc:identifier>' if isbn else ""
    pub = f'<dc:publisher>{htmlmod.escape(meta["publisher"])}</dc:publisher>' if meta.get("publisher") else ""
    date = f'<dc:date>{htmlmod.escape(meta["pubdate"])}</dc:date>' if meta.get("pubdate") else ""
    desc = f'<dc:description>{htmlmod.escape(meta["intro"])}</dc:description>' if meta.get("intro") else ""
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t for t in re.split(r"[,，、;；\s]+", tags) if t]
    tags_xml = "".join(f"<dc:subject>{htmlmod.escape(t)}</dc:subject>" for t in tags)
    lang = meta.get("language", "zh-CN") or "zh-CN"
    # spine 顺序：封面 → 目录页 → 章节与插图（目录页是在章节循环后才生成的，此处重排）
    front = [i for i in spine_ids if i == "coverpage"]
    tocs = [i for i in spine_ids if i.startswith("tocpage")]
    rest = [i for i in spine_ids if i != "coverpage" and not i.startswith("tocpage")]
    spine_ids = front + tocs + rest
    spine = "".join(f'<itemref idref="{i}"/>' for i in spine_ids)
    files["content.opf"] = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bid">urn:epubstudio:{htmlmod.escape(title)}</dc:identifier>
{isbn_xml}
<dc:title>{htmlmod.escape(title)}</dc:title>
<dc:creator>{htmlmod.escape(author)}</dc:creator>
<dc:language>{htmlmod.escape(lang)}</dc:language>
{pub}{date}{desc}{tags_xml}
<meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
</metadata>
<manifest>{"".join(manifest)}</manifest>
<spine toc="ncx">{spine}</spine>
</package>'''.encode("utf-8")
    files["META-INF/container.xml"] = b'''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for n, d in files.items():
            z.writestr(n, d, compress_type=zipfile.ZIP_DEFLATED)
    size = os.path.getsize(out_path) / 1048576
    log(f"已生成 {out_path}（{size:.1f} MB），{len(chapters)} 章，样式命中 {style_hits} 处，"
        f"选字命中 {tf_hits} 处，注释 {note_total} 条")
    return {"path": out_path, "size_mb": round(size, 1), "chapters": len(chapters),
            "dialogues": style_hits, "notes": note_total, "tf_hits": tf_hits}
