# -*- coding: utf-8 -*-
"""三项新功能端到端构建测试：头图按章指定 / 选中文字改字体 / 注释标记图标"""
import sys, os, zipfile, re

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, r"C:\Users\86158\WorkBuddy\2026-09-24-23-45-45\pylibs")
import epub_core as core

WORK = os.path.join(BASE, "work", "test_v3")
os.makedirs(WORK, exist_ok=True)
FONT_KAI = r"C:\Windows\Fonts\simhei.ttf"   # 用黑体充当“选字字体 kai”
FONT_BODY = os.path.join(BASE, "work", "fonts", "body.ttf")

# 找两张测试头图（复用 work/assets 里之前上传的）
asset_dir = os.path.join(BASE, "work", "assets")
imgs = [os.path.join(asset_dir, f) for f in sorted(os.listdir(asset_dir))
        if f.startswith("header_") and f.lower().endswith((".png", ".jpg", ".jpeg"))][:2]
print("test header images:", [os.path.basename(x) for x in imgs])
assert len(imgs) >= 2, "需要至少两张已上传头图"

chapters = core.parse_txt(
    "第一章 雪夜\n\n　　他站在窗前，看着外面纷纷扬扬的雪。{{注:此章写于深秋}}\n"
    "　　「你终于来了。」她说。\n　　这世间所有的相遇，都是久别重逢。\n\n"
    "第二章 旧梦\n\n　　梦里又回到了那座小城。「别走。」他轻声说。\n\n"
    "第三章 归途\n\n　　雪停了。天边露出一线微光。\n　　「我们回家吧。」她说。\n")

book = {
    "title": "功能测试书", "author": "测试员",
    "chapters": chapters,
    "settings": {
        "fonts": {"body": FONT_BODY, "kai": FONT_KAI},
        "header": {"enabled": True, "rotate": True, "images": imgs,
                   "assign": [{"img": 1, "chapters": "2-3"}]},   # 区间：第2~3章固定用第2张图
        "text_fonts": [{"chapter": 1, "text": "「别走。」", "font": "kai"}],
        "notes": {"icon": "小鸟"},
        "cover": "",
    },
}

out = os.path.join(WORK, "test_v3.epub")
logs = []
res = core.build_epub(book, WORK, out, r"C:\Users\86158\WorkBuddy\2026-09-24-23-45-45\pylibs", log=logs.append)
for l in logs: print(" ", l)

z = zipfile.ZipFile(out)
names = z.namelist()
print("\n=== EPUB 文件 ===")
for n in names: print("  ", n, z.getinfo(n).file_size)

ok = True
def check(name, cond):
    global ok
    print(("✓" if cond else "✗"), name)
    if not cond: ok = False

# --- 功能1：头图指定 ---
head_files = sorted(n for n in names if re.match(r"images/head\d+", n))
check("两张头图都进包", len(head_files) == 2)
ch1 = z.read("chapters/ch001.xhtml").decode("utf-8")   # 第2章（0基1）
m1 = re.search(r'chapter-img"><img src="../images/(head\d+\.\w+)"', ch1)
ch0 = z.read("chapters/ch000.xhtml").decode("utf-8")
m0 = re.search(r'chapter-img"><img src="../images/(head\d+\.\w+)"', ch0)
print("  第1章头图:", m0.group(1) if m0 else None, " 第2章头图:", m1.group(1) if m1 else None)
check("区间 2-3：第2章用指定图", m1 and m1.group(1).startswith("head1"))
check("第1章仍走轮换(第1张)", m0 and m0.group(1).startswith("head0"))
ch2 = z.read("chapters/ch002.xhtml").decode("utf-8")
m2 = re.search(r'chapter-img"><img src="../images/(head\d+\.\w+)"', ch2)
check("区间 2-3：第3章也用指定图", m2 and m2.group(1).startswith("head1"))

# --- 功能2：选字 ---
css = z.read("styles.css").decode("utf-8")
check("CSS 含 .tf_kai 规则", ".tf_kai" in css and '"kai"' in css)
check("kai 字体已子集进包", "fonts/f_kai.ttf" in names)
check("第2章命中 span", '<span class="tf_kai">「别走。」</span>' in ch1)

# --- 功能3：注释图标 ---
check("noteicon.png 进包", "images/noteicon.png" in names)
check("注释标记用小鸟图标", '<img class="note-ico" src="../images/noteicon.png"' in ch0)
check("正文标记不再是 [注N] 文字", not re.search(r'class="note-ref"[^>]*>\[注\d+\]</a>', ch0))
check("注释跳转结构完整", 'epub:type="noteref"' in ch0 and "fn_0_0" in ch0)
# 页尾注释文字仍保留 [注1]
check("页尾注释保留 [注1] 文字", "[注1] 此章写于深秋" in ch0)

# --- XML 合法性 ---
from xml.dom import minidom
for n in names:
    if n.endswith((".xhtml", ".opf", ".ncx")):
        try: minidom.parseString(z.read(n))
        except Exception as e: ok = False; print("✗ XML", n, e)
print("✓ 全部 XML 合法")

print("\n" + ("ALL PASS ✅" if ok else "FAILED ❌"))
sys.exit(0 if ok else 1)
