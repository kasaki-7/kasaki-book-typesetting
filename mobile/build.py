# -*- coding: utf-8 -*-
"""把 lib/ 里的 jszip 与 harfbuzz wasm 注入 template.html，产出单文件 epub-studio-mobile.html

用法：
    python build.py

依赖（已随仓库提供，无需联网）：
    lib/jszip.min.js      浏览器端 ZIP 打包
    lib/hb-subset.wasm    harfbuzz 字体子集化（在浏览器内裁字体）

产物：
    epub-studio-mobile.html   约 940KB 单文件，传到手机浏览器打开即用
"""
import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
LIB = ROOT / "lib"

tpl = (ROOT / "template.html").read_text(encoding="utf-8")
jszip = (LIB / "jszip.min.js").read_text(encoding="utf-8")
wasm_b64 = base64.b64encode((LIB / "hb-subset.wasm").read_bytes()).decode("ascii")

assert "/*__JSZIP__*/" in tpl, "template.html 缺少 /*__JSZIP__*/ 占位符"
assert "/*__HBWASM__*/" in tpl, "template.html 缺少 /*__HBWASM__*/ 占位符"
assert "</script>" not in jszip, "jszip.min.js 含 </script>，无法内联"

out = tpl.replace("/*__JSZIP__*/", jszip, 1)
out = out.replace("/*__HBWASM__*/", wasm_b64, 1)

dst = ROOT / "epub-studio-mobile.html"
dst.write_text(out, encoding="utf-8")
print("OK ->", dst.name, f"{len(out.encode('utf-8')) / 1024:.0f} KB")
