# EPUB 精排工坊 · 手机版

**一个单文件网页**：把 `epub-studio-mobile.html` 传到手机，用浏览器打开即可排版电子书。全程本地运行，**不联网、不上传**，书稿只留在你的手机上。

> 不需要装 App、不需要电脑、不需要 Python 环境。兼容夸克、Via、Chrome、Edge、系统自带浏览器等多数安卓浏览器。

## 界面预览

| 导入书籍 | 字体与文字样式 | 封面与头图 | 正文编辑 |
|:---:|:---:|:---:|:---:|
| ![导入](https://raw.githubusercontent.com/kasaki-7/kasaki-book-typesetting/main/docs/mobile/02-import.png) | ![样式](https://raw.githubusercontent.com/kasaki-7/kasaki-book-typesetting/main/docs/mobile/v3-style.png) | ![图片](https://raw.githubusercontent.com/kasaki-7/kasaki-book-typesetting/main/docs/mobile/v3-image.png) | ![编辑](https://raw.githubusercontent.com/kasaki-7/kasaki-book-typesetting/main/docs/mobile/v3-edit.png) |

## 功能

- **导入**：TXT（自动切章，可改正则重新切章，广告过滤规则可自定义）/ EPUB（按原目录重切）
- **字体**：4 个槽位（正文 / 对话 / 章标题 / 目录），上传 TTF/OTF 后**在浏览器内按书中实际用字裁剪**——17MB 宋体通常压到 50KB 左右，成书体积大幅缩小
- **文字样式规则**：引号、括号、作者有话说等各自定制字体/颜色/字号/粗斜体，内置预设 + 自定义正则
- **选中文字换字体**：正文编辑里拖选任意文字，一键换用指定字体（如书信用楷体）
- **注释**：正文里写 `{{注:内容}}`，生成可点击的注释标记与章末注释；**8 款内置小图标**（查看/船/书/树/树叶/数据/小鸟/音符）可替换 [注N] 文字标记
- **章节头图**：多张轮换，**可为指定章节固定某一张图（支持区间写法如 1-20,25）**，宽高可调，**11 种水墨边缘蒙版**（方正 / 云边 / 雾边 / 拖墨 / 糙圆 / 晕染 / 胶片 / 撕边 / 撕框 / 笔刷 / 毛边）
- **正文内插图**：在正文编辑里选中文字，把插图插到选中文字前/后，宽度可调
- **全屏插图页**：每隔 N 章插入，或**指定章后插入（支持区间）**；正文编辑里可一键"本章后加全屏插图"
- **目录页背景图**：可铺底图（多张轮换），显示方式可选，文字区自动垫半透明底
- **首字下沉**：每章第一段首字下沉，字号/字体/颜色可调
- **封面**：尺寸可调（最大宽度 px，0 = 原图）
- **阅读版式**：边距（百分比，不随阅读器字号膨胀）、行距、段距、首行缩进、章标题字号、自定义 CSS
- **书籍元数据**：书名 / 作者 / 简介 / 标签（写入 dc:title、dc:creator、dc:description、dc:subject）
- **生成**：浏览器内打包 EPUB 3，下载后用任意阅读器 App 打开
- **设置记忆**：字体与样式自动保存在本机浏览器，换书不用重配；支持导出 / 导入设置文件

## 怎么用

**第一步：传到手机**（任选一种）

| 方式 | 操作 |
|---|---|
| 微信 / QQ | 把 `epub-studio-mobile.html` 发给"文件传输助手"，手机端下载后用浏览器打开 |
| USB 数据线 | 复制到手机"下载"文件夹，用文件管理器打开 |
| 网盘 | 上传后再在手机端下载 |

**第二步：打开**

推荐 **Chrome / Edge / Via / 夸克** 浏览器（不要用某些浏览器的"文档预览模式"，要用浏览器方式打开）。第一次打开约需几秒（文件约 1MB），点"开始使用"进入。

> 提示：生成完成后，日志区会出现一条"若没有自动下载，点此或长按保存"的链接——如果浏览器拦截了自动下载，点它或长按选"下载"即可。

**第三步：排版**
导入 → （可选）上传字体、配样式 → 传封面头图选边缘样式 → 填书名 → 点"开始生成"。

生成的 `.epub` 用"阅读"、静读天下、微信读书等 App 打开即可。

### 常见问题

**Q：生成的 EPUB 里字体没生效？**
部分阅读器默认忽略内嵌字体，在阅读器设置里选"使用文档内嵌字体 / 出版物资置字体"。

**Q：切章把正文切碎了？**
在"导入"页改切章正则（默认识别"第X章/节/回"），改完点"重新切章"。

**Q：某个浏览器打开后点按钮没反应？**
本工具已针对旧内核浏览器做了兼容（不依赖 file.text()/arrayBuffer() 等新接口，压缩不可用时自动降级）。若页面完全空白，说明该浏览器连 JavaScript 都未启用，换 Chrome / Via / 夸克打开即可。

**Q：iPhone 能用吗？**
可以，Safari 打开，操作一致。

**Q：字体太大了会怎样？**
字体会存进浏览器本地存储（总量上限约 3.5MB base64）。超出部分本次会话内仍可正常使用，只是下次打开需重传。

## 从源码构建

仓库里 `mobile/` 目录已包含源码与依赖，无需联网：

```
mobile/
├── template.html            # 页面模板（含 /*__JS__*/ 与 /*__HBWASM__*/ 两个占位符）
├── build.py                 # 注入脚本
├── lib/
│   └── hb-subset.wasm       # harfbuzz 字体子集化（MIT，harfbuzzjs）
└── epub-studio-mobile.html  # 构建产物（已提交，可直接使用）
```

```bash
cd mobile
python build.py     # 产出 epub-studio-mobile.html
```

## 技术说明

- **纯前端单文件**：无服务端，数据不出本机
- **字体子集化**：harfbuzz 编译为 WebAssembly（`hb-subset.wasm`），通过 `WebAssembly.instantiate` 直接调用 C 导出函数完成裁剪，实测 9.3MB 黑体 → 24KB、17.47MB 宋体 → 48KB（25ms）
- **ZIP 打包**：内嵌 MiniZip（基于浏览器原生 CompressionStream 的极简 ZIP 实现，约 200 行），不可用时自动降级为不压缩打包；`mimetype` 以 STORE 方式置于首位，含 nav + ncx 双目录、`dc:subject` 标签
- **边缘蒙版**：Canvas 2D 合成（透明起点 + 白色形状 + `destination-out` 挖边）生成 alpha 蒙版，再 `destination-in` 应用到头图
- **兼容性**：不使用 `file.text()` / `blob.arrayBuffer()` 等新接口，全部走 FileReader；旧内核浏览器（不支持原生压缩）自动降级为不压缩 EPUB；页面错误会以提示与日志形式可见

## 许可证

[MIT](https://github.com/kasaki-7/kasaki-book-typesetting/blob/main/LICENSE)
