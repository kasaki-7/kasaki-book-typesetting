# -*- coding: utf-8 -*-
"""组装手机版单文件 HTML：注入业务 JS、注释图标与 harfbuzz wasm（v3 起不再依赖 JSZip）"""
import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, ".mobile-libs")
LIB = os.path.join(HERE, "lib")

template = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()

# 注释图标（base64 内嵌，须在业务 JS 之前，业务代码初始化时就要用）
js = open(os.path.join(SRC, "mobile_v3.js"), encoding="utf-8").read()
icons = open(os.path.join(SRC, "note_icons.js"), encoding="utf-8").read()
assert "</script>" not in js and "</script>" not in icons, "JS 内含 </script> 会截断！"
out = template.replace("/*__JS__*/", "\n" + icons + "\n" + js + "\n")

# harfbuzz wasm（base64）
wasm_path = os.path.join(LIB, "hb-subset.wasm")
if not os.path.isfile(wasm_path):
    wasm_path = os.path.join(SRC, "hb-subset.wasm")
wasm_b64 = base64.b64encode(open(wasm_path, "rb").read()).decode("ascii")
out = out.replace("/*__HBWASM__*/", wasm_b64)

assert "/*__JS__*/" not in out and "/*__HBWASM__*/" not in out, "占位符未全部替换"
dst = os.path.join(HERE, "epub-studio-mobile.html")
open(dst, "w", encoding="utf-8", newline="\n").write(out)
print("OK -> %s (%.0f KB)" % (dst, os.path.getsize(dst) / 1024))
