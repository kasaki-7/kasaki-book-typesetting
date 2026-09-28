# -*- coding: utf-8 -*-
"""EPUB 精排工坊 v2 - 本地后端服务"""
import os, sys, json, re, threading

BASE = os.path.dirname(os.path.abspath(__file__))

# 依赖搜索路径：正常情况下直接 pip install -r requirements.txt 即可，无需此处。
# 以下为免安装场景的兜底探测（按优先级）：环境变量 > 项目内 pylibs > 上级目录 pylibs
PYLIBS = ""
for _p in (os.environ.get("EPUB_STUDIO_PYLIBS", ""),
           os.path.join(BASE, "pylibs"),
           os.path.join(os.path.dirname(BASE), "pylibs")):
    if _p and os.path.isdir(_p):
        PYLIBS = _p
        if _p not in sys.path:
            sys.path.insert(0, _p)
        break

from flask import Flask, request, jsonify, send_file, send_from_directory
import epub_core as core

WORK = os.path.join(BASE, "work")
ASSETS = os.path.join(WORK, "assets")
FONTS = os.path.join(WORK, "fonts")
OUTDIR = os.path.join(WORK, "output")
for d in (WORK, ASSETS, FONTS, OUTDIR):
    os.makedirs(d, exist_ok=True)

BOOK_FILE = os.path.join(WORK, "book.json")
PROFILE_FILE = os.path.join(WORK, "profile.json")
app = Flask(__name__, static_folder="static")

# ---------- 状态 ----------
def load_book():
    if os.path.isfile(BOOK_FILE):
        b = json.load(open(BOOK_FILE, encoding="utf-8"))
        core.deep_fill(b["settings"], core.DEFAULT_SETTINGS)
        return b
    return None

def save_book(book):
    json.dump(book, open(BOOK_FILE, "w", encoding="utf-8"), ensure_ascii=False)

def book_or_404():
    b = load_book()
    if not b:
        return None, (jsonify({"error": "尚未导入书籍"}), 400)
    return b, None

# ---------- 配置档案（字体/文字样式/注释样式，跨书籍继承，图片不继承） ----------
PROFILE_KEYS = ("fonts", "styles", "notes")

def save_profile(settings):
    """把当前书籍的字体与文字样式规则写入档案"""
    prof = {}
    for k in PROFILE_KEYS:
        if k in settings:
            prof[k] = settings[k]
    json.dump(prof, open(PROFILE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def apply_profile(settings):
    """导入新书时，把档案里的字体/样式规则继承过来（字体文件需仍存在）"""
    if not os.path.isfile(PROFILE_FILE):
        return
    try:
        prof = json.load(open(PROFILE_FILE, encoding="utf-8"))
    except Exception:
        return
    fonts = prof.get("fonts") or {}
    fonts = {k: v for k, v in fonts.items() if v and os.path.isfile(v)}
    if fonts:
        settings["fonts"].update(fonts)
    styles = prof.get("styles")
    if isinstance(styles, list) and styles:
        settings["styles"] = styles
    notes = prof.get("notes")
    if isinstance(notes, dict) and notes:
        settings["notes"].update(notes)

# ---------- 页面 ----------
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# ---------- 导入 ----------
def do_import(path, toc_regex=None):
    if not os.path.isfile(path):
        return {"error": f"文件不存在: {path}"}, 400
    try:
        if path.lower().endswith(".txt"):
            chapters = core.parse_txt(core.read_txt_file(path), toc_regex)
            src_type = "txt"
        elif path.lower().endswith(".epub"):
            chapters = core.parse_epub(path)
            src_type = "epub"
        else:
            return {"error": "仅支持 .txt / .epub"}, 400
    except Exception as e:
        return {"error": f"解析失败: {e}"}, 500
    title = os.path.splitext(os.path.basename(path))[0]
    for pat in ("_润文网", " - "):
        if pat in title:
            title = title.split(pat)[0]
    book = {"title": title, "author": "", "source": path, "source_type": src_type,
            "chapters": chapters,
            "settings": json.loads(json.dumps(core.DEFAULT_SETTINGS))}
    if toc_regex:
        book["settings"]["toc_regex"] = toc_regex
    # 档案不存在时先用当前书籍的字体/样式播种，再继承到新书（图片不继承）
    if not os.path.isfile(PROFILE_FILE):
        old = load_book()
        if old:
            save_profile(old["settings"])
    apply_profile(book["settings"])
    save_book(book)
    return {"ok": True, "title": title, "chapters": len(chapters),
            "paras": sum(len(c["paras"]) for c in chapters),
            "chars": sum(len(p) for c in chapters for p in c["paras"])}, 200

@app.route("/api/import_path", methods=["POST"])
def import_path():
    d = request.json
    res, code = do_import(d.get("path", "").strip().strip('"'), d.get("toc_regex"))
    return jsonify(res), code

@app.route("/api/import_upload", methods=["POST"])
def import_upload():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "未选择文件"}), 400
    dst = os.path.join(WORK, "upload_" + f.filename)
    f.save(dst)
    res, code = do_import(dst, request.form.get("toc_regex"))
    return jsonify(res), code

@app.route("/api/resplit", methods=["POST"])
def resplit():
    """按新正则重新切章（TXT 源）"""
    b, err = book_or_404()
    if err: return err
    if b.get("source_type") != "txt" or not os.path.isfile(b.get("source", "")):
        return jsonify({"error": "仅 TXT 源支持重新切章"}), 400
    rx = request.json.get("regex", "").strip()
    b["settings"]["toc_regex"] = rx or core.DEFAULT_TOC_REGEX
    try:
        re.compile(b["settings"]["toc_regex"])
    except re.error as e:
        return jsonify({"error": f"正则无效: {e}"}), 400
    vol_map = {c["title"]: c.get("volume") for c in b["chapters"] if c.get("volume")}
    b["chapters"] = core.parse_txt(core.read_txt_file(b["source"]), b["settings"]["toc_regex"])
    for c in b["chapters"]:
        if c["title"] in vol_map:
            c["volume"] = vol_map[c["title"]]
    save_book(b)
    return jsonify({"ok": True, "chapters": len(b["chapters"])})

# ---------- 书籍信息 / 元数据 ----------
@app.route("/api/book")
def get_book():
    b = load_book()
    if not b:
        return jsonify({"loaded": False})
    return jsonify({"loaded": True, "title": b["title"], "author": b.get("author", ""),
                    "source": b.get("source", ""), "source_type": b.get("source_type", ""),
                    "chapters": len(b["chapters"]),
                    "paras": sum(len(c["paras"]) for c in b["chapters"]),
                    "chars": sum(len(p) for c in b["chapters"] for p in c["paras"]),
                    "settings": b["settings"]})

@app.route("/api/meta", methods=["POST"])
def set_meta():
    b, err = book_or_404()
    if err: return err
    d = request.json
    b["title"] = d.get("title", b["title"])
    b["author"] = d.get("author", b.get("author", ""))
    meta = b["settings"]["meta"]
    for k in ("intro", "publisher", "isbn", "pubdate", "language"):
        if k in d:
            meta[k] = d[k]
    if "tags" in d:
        raw = d["tags"]
        if isinstance(raw, str):
            meta["tags"] = [t for t in re.split(r"[,，、;；\s]+", raw) if t.strip()]
        elif isinstance(raw, list):
            meta["tags"] = [str(t).strip() for t in raw if str(t).strip()]
        else:
            meta["tags"] = []
    save_book(b)
    return jsonify({"ok": True})

# ---------- 章节 ----------
@app.route("/api/chapters")
def list_chapters():
    b, err = book_or_404()
    if err: return err
    return jsonify([{"i": i, "title": c["title"], "paras": len(c["paras"]),
                     "chars": sum(len(p) for p in c["paras"]), "volume": c.get("volume")}
                    for i, c in enumerate(b["chapters"])])

@app.route("/api/chapter/<int:i>", methods=["GET", "PUT", "DELETE"])
def chapter(i):
    b, err = book_or_404()
    if err: return err
    if not (0 <= i < len(b["chapters"])):
        return jsonify({"error": "章节不存在"}), 404
    if request.method == "GET":
        return jsonify({"title": b["chapters"][i]["title"], "text": "\n".join(b["chapters"][i]["paras"])})
    if request.method == "PUT":
        d = request.json
        if "title" in d:
            b["chapters"][i]["title"] = d["title"].strip() or b["chapters"][i]["title"]
        if "text" in d:
            b["chapters"][i]["paras"] = [l for l in d["text"].replace("\r\n", "\n").split("\n") if l.strip()]
        save_book(b)
        return jsonify({"ok": True})
    b["chapters"].pop(i)
    save_book(b)
    return jsonify({"ok": True, "chapters": len(b["chapters"])})

@app.route("/api/chapters/merge_prev/<int:i>", methods=["POST"])
def merge_prev(i):
    b, err = book_or_404()
    if err: return err
    if not (1 <= i < len(b["chapters"])):
        return jsonify({"error": "无法合并"}), 400
    prev, cur = b["chapters"][i-1]["paras"], b["chapters"].pop(i)["paras"]
    if prev and cur and prev[-1] and prev[-1][-1] not in core.TERMINAL:
        prev[-1] += cur[0]; prev.extend(cur[1:])
    else:
        prev.extend(cur)
    save_book(b)
    return jsonify({"ok": True, "chapters": len(b["chapters"])})

@app.route("/api/chapters/normalize", methods=["POST"])
def normalize_titles():
    b, err = book_or_404()
    if err: return err
    b["chapters"] = core.normalize_numeric_titles(b["chapters"])
    save_book(b)
    return jsonify({"ok": True})

@app.route("/api/chapters/merge_duplicates", methods=["POST"])
def merge_dups():
    b, err = book_or_404()
    if err: return err
    before = len(b["chapters"])
    b["chapters"] = core.merge_duplicate_chapters(b["chapters"])
    save_book(b)
    return jsonify({"ok": True, "before": before, "after": len(b["chapters"])})

# ---------- 分卷 ----------
@app.route("/api/chapter/<int:i>/volume", methods=["POST"])
def set_volume(i):
    b, err = book_or_404()
    if err: return err
    if not (0 <= i < len(b["chapters"])):
        return jsonify({"error": "章节不存在"}), 404
    name = request.json.get("name", "").strip()
    if name:
        b["chapters"][i]["volume"] = name
    else:
        b["chapters"][i].pop("volume", None)
    save_book(b)
    return jsonify({"ok": True})

# ---------- 查找替换 ----------
@app.route("/api/find", methods=["POST"])
def find():
    b, err = book_or_404()
    if err: return err
    kw = request.json.get("kw", "")
    if not kw:
        return jsonify([])
    hits = []
    for i, c in enumerate(b["chapters"]):
        for j, p in enumerate(c["paras"]):
            if kw in p:
                hits.append({"chapter": i, "title": c["title"], "para": j,
                             "text": p[:120], "count": p.count(kw)})
    return jsonify(hits[:500])

@app.route("/api/replace", methods=["POST"])
def replace():
    b, err = book_or_404()
    if err: return err
    kw, rep = request.json.get("kw", ""), request.json.get("rep", "")
    if not kw:
        return jsonify({"error": "关键词为空"}), 400
    n = 0
    for c in b["chapters"]:
        for j, p in enumerate(c["paras"]):
            if kw in p:
                n += p.count(kw)
                c["paras"][j] = p.replace(kw, rep)
    save_book(b)
    return jsonify({"ok": True, "replaced": n})

# ---------- 广告检查 ----------
@app.route("/api/ads/patterns", methods=["GET", "POST"])
def ads_patterns():
    b, err = book_or_404()
    if err: return err
    if request.method == "POST":
        pats = request.json.get("patterns", [])
        for p in pats:
            try:
                re.compile(p)
            except re.error as e:
                return jsonify({"error": f"正则无效「{p}」: {e}"}), 400
        b["settings"]["ads_patterns"] = pats
        save_book(b)
        return jsonify({"ok": True})
    return jsonify({"patterns": b["settings"]["ads_patterns"], "presets": core.AD_PRESETS})

@app.route("/api/ads/scan", methods=["POST"])
def ads_scan():
    b, err = book_or_404()
    if err: return err
    pats = request.json.get("patterns") or b["settings"]["ads_patterns"]
    rx = []
    for p in pats:
        try:
            rx.append(re.compile(p))
        except re.error:
            continue
    hits = []
    for i, c in enumerate(b["chapters"]):
        for j, p in enumerate(c["paras"]):
            if any(r.search(p) for r in rx):
                hits.append({"chapter": i, "title": c["title"], "para": j, "text": p[:150]})
    return jsonify(hits[:2000])

@app.route("/api/ads/delete", methods=["POST"])
def ads_delete():
    b, err = book_or_404()
    if err: return err
    targets = request.json.get("items", [])
    by_ch = {}
    for t in targets:
        by_ch.setdefault(t["chapter"], set()).add(t["para"])
    n = 0
    for ci, ps in by_ch.items():
        if 0 <= ci < len(b["chapters"]):
            before = len(b["chapters"][ci]["paras"])
            b["chapters"][ci]["paras"] = [p for j, p in enumerate(b["chapters"][ci]["paras"]) if j not in ps]
            n += before - len(b["chapters"][ci]["paras"])
    save_book(b)
    return jsonify({"ok": True, "deleted": n})

# ---------- 文字样式预设 ----------
@app.route("/api/styles/presets")
def style_presets():
    return jsonify(core.STYLE_PRESETS)

# ---------- 素材上传 ----------
@app.route("/api/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    kind = request.form.get("kind", "")
    b, err = book_or_404()
    if err: return err
    if not f:
        return jsonify({"error": "未选择文件"}), 400
    st = b["settings"]
    ext = os.path.splitext(f.filename)[1].lower()
    if kind.startswith("font_"):
        key = kind[5:]
        dst = os.path.join(FONTS, key + ext)
        f.save(dst)
        st["fonts"][key] = dst
    elif kind == "cover":
        dst = os.path.join(ASSETS, "cover" + ext)
        f.save(dst)
        st["cover"] = dst
    elif kind == "tocbg":
        dst = os.path.join(ASSETS, f"tocbg_{len(st['toc_bgs'])}" + ext)
        f.save(dst)
        st["toc_bgs"].append(dst)
    elif kind == "header":
        dst = os.path.join(ASSETS, f"header_{len(st['header']['images'])}" + ext)
        f.save(dst)
        st["header"]["images"].append(dst)
    elif kind == "illust":
        dst = os.path.join(ASSETS, f"illust_{len(st['illust']['images'])}" + ext)
        f.save(dst)
        st["illust"]["images"].append(dst)
    elif kind == "inline":
        dst = os.path.join(ASSETS, f"inline_{len(st['inline_images'])}" + ext)
        f.save(dst)
        st["inline_images"].append({"path": dst, "chapter": 0, "para": 0,
                                    "where": "after", "width_pct": 60, "wrap": "block"})
    else:
        return jsonify({"error": "未知类型"}), 400
    save_book(b)
    if kind.startswith("font_"):
        save_profile(b["settings"])
    return jsonify({"ok": True, "path": dst})

@app.route("/api/assets/clear", methods=["POST"])
def clear_assets():
    b, err = book_or_404()
    if err: return err
    kind = request.json.get("kind")
    st = b["settings"]
    if kind == "headers":
        st["header"]["images"] = []
    elif kind == "illusts":
        st["illust"]["images"] = []
    elif kind == "toc_bgs":
        st["toc_bgs"] = []
    elif kind == "cover":
        st["cover"] = ""
    elif kind == "inline_images":
        st["inline_images"] = []
    save_book(b)
    return jsonify({"ok": True})

# ---------- 正文内插图 ----------
@app.route("/api/inline_images/<int:idx>", methods=["PUT", "DELETE"])
def inline_image(idx):
    b, err = book_or_404()
    if err: return err
    lst = b["settings"]["inline_images"]
    if not (0 <= idx < len(lst)):
        return jsonify({"error": "不存在"}), 404
    if request.method == "DELETE":
        lst.pop(idx)
    else:
        d = request.json
        for k in ("chapter", "para", "width_pct"):
            if k in d:
                lst[idx][k] = int(d[k])
        for k in ("where", "wrap"):
            if k in d:
                lst[idx][k] = d[k]
    save_book(b)
    return jsonify({"ok": True})

# ---------- 版式设置（通用深度合并） ----------
def deep_update(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_update(dst[k], v)
        else:
            dst[k] = v

@app.route("/api/settings", methods=["POST"])
def set_settings():
    b, err = book_or_404()
    if err: return err
    data = request.json or {}
    if "output_dir" in data:
        v = (data["output_dir"] or "").strip().strip('"').strip("'")
        data["output_dir"] = os.path.normpath(v) if v else ""
    deep_update(b["settings"], data)
    save_book(b)
    save_profile(b["settings"])
    return jsonify({"ok": True})

@app.route("/api/edge_styles")
def edge_styles():
    return jsonify([{"key": k, "name": n} for k, n in core.EDGE_STYLES])

@app.route("/api/edge_preview/<key>.png")
def edge_preview(key):
    """边缘样式示意图（按需生成并缓存到 work/edge_previews/）"""
    valid = {k for k, _ in core.EDGE_STYLES}
    if key not in valid:
        return jsonify({"error": "未知样式"}), 404
    cache = os.path.join(WORK, "edge_previews")
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, key + ".png")
    if not os.path.exists(out):
        try:
            core.make_edge_preview(key, out)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return send_from_directory(cache, key + ".png")

# ---------- 构建 ----------
build_state = {"running": False, "logs": [], "result": None}

@app.route("/api/build", methods=["POST"])
def build():
    b, err = book_or_404()
    if err: return err
    if build_state["running"]:
        return jsonify({"error": "正在构建中"}), 400
    payload = request.get_json(silent=True) or {}
    if "output_dir" in payload:
        v = (payload["output_dir"] or "").strip().strip('"').strip("'")
        b["settings"]["output_dir"] = os.path.normpath(v) if v else ""
        save_book(b)
    def run():
        build_state.update(running=True, logs=[], result=None)
        try:
            def log(m): build_state["logs"].append(str(m))
            out_dir = b["settings"].get("output_dir") or OUTDIR
            out_dir = os.path.normpath(out_dir)
            try:
                os.makedirs(out_dir, exist_ok=True)
                if not os.path.isdir(out_dir):
                    raise OSError("不是有效文件夹")
            except Exception as e:
                log(f"保存位置不可用（{e}），已回退默认目录：{OUTDIR}")
                out_dir = OUTDIR
                os.makedirs(out_dir, exist_ok=True)
            out = os.path.join(out_dir, b["title"] + "_精排.epub")
            res = core.build_epub(b, WORK, out, PYLIBS, log=log)
            build_state["result"] = res
        except Exception as e:
            import traceback
            build_state["logs"].append("ERROR: " + str(e))
            build_state["logs"].append(traceback.format_exc()[-800:])
        finally:
            build_state["running"] = False
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/build/status")
def build_status():
    return jsonify(build_state)

@app.route("/api/download")
def download():
    path = request.args.get("path", "")
    ap = os.path.abspath(path)
    allowed = ap.startswith(os.path.abspath(OUTDIR))
    res = build_state.get("result")
    if res and os.path.abspath(res.get("path", "")) == ap:
        allowed = True  # 本次构建产物（可能在自定义保存位置）
    if not os.path.isfile(path) or not allowed:
        return jsonify({"error": "文件不存在"}), 404
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8642
    print(f"EPUB 精排工坊已启动: http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
