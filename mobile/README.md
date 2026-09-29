# EPUB 精排工坊 · 手机版

**一个单文件网页**：把 `epub-studio-mobile.html` 传到手机，用浏览器打开即可排版电子书。全程本地运行，**不联网、不上传**，书稿只留在你的手机上。

> 不需要装 App、不需要电脑、不需要 Python 环境。

## 界面预览

| 导入书籍 | 字体与文字样式 | 封面与头图 |
|:---:|:---:|:---:|
| ![导入](https://raw.githubusercontent.com/kasaki-7/kasaki-book-typesetting/main/docs/mobile/02-import.png) | ![样式](https://raw.githubusercontent.com/kasaki-7/kasaki-book-typesetting/main/docs/mobile/03-style.png) | ![图片](https://raw.githubusercontent.com/kasaki-7/kasaki-book-typesetting/main/docs/mobile/04-image.png) |

## 功能

- **导入**：TXT（自动切章，可改正则重新切章）/ EPUB（按原目录重切）
- **字体**：4 个槽位（正文 / 对话 / 章标题 / 目录），上传 TTF/OTF 后**在浏览器内按书中实际用字裁剪**——17MB 宋体通常压到 50KB 左右，成书体积大幅缩小
- **文字样式规则**：引号、括号、作者有话说等各自定制字体/颜色/字号/粗斜体，内置预设 + 自定义正则
- **章节头图**：多张轮换，宽高可调，**11 种水墨边缘蒙版**（方正 / 云边 / 雾边 / 拖墨 / 糙圆 / 晕染 / 胶片 / 撕边 / 撕框 / 笔刷 / 毛边）
- **封面 / 全屏插图**：尺寸可调，插图可按"每 N 章"插入
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
推荐 **Chrome / Edge / Via** 浏览器。第一次打开约需几秒（文件约 940KB），点"开始使用"进入。

**第三步：排版**
导入 → （可选）上传字体、配样式 → 传封面头图选边缘样式 → 填书名 → 点"开始生成"。

生成的 `.epub` 用"阅读"、静读天下、微信读书等 App 打开即可。

### 常见问题

**Q：生成的 EPUB 里字体没生效？**
部分阅读器默认忽略内嵌字体，在阅读器设置里选"使用文档内嵌字体 / 出版物资置字体"。

**Q：切章把正文切碎了？**
在"导入"页改切章正则（默认识别"第X章/节/回"），改完点"重新切章"。

**Q：iPhone 能用吗？**
可以，Safari 打开，操作一致。

**Q：字体太大了会怎样？**
字体会存进浏览器本地存储。超大字体（>20MB）可能保存失败，但本次生成仍可正常使用。

## 从源码构建

仓库里 `mobile/` 目录已包含源码与依赖，无需联网：

```
mobile/
├── template.html            # 页面模板（含 /*__JSZIP__*/ 与 /*__HBWASM__*/ 两个占位符）
├── build.py                 # 注入脚本
├── lib/
│   ├── jszip.min.js         # 浏览器端 ZIP 打包（MIT）
│   └── hb-subset.wasm       # harfbuzz 字体子集化（MIT，harfbuzzjs）
└── epub-studio-mobile.html  # 构建产物（已提交，可直接使用）
```

```bash
cd mobile
python build.py     # 产出 epub-studio-mobile.html
```

## 技术说明

- **纯前端单文件**：无服务端，数据不出本机
- **字体子集化**：harfbuzz 编译为 WebAssembly（`hb-subset.wasm`），通过 `WebAssembly.instantiate` 直接调用 C 导出函数完成裁剪，实测 17.47MB 字体 → 48KB 仅需 25ms
- **边缘蒙版**：Canvas 2D 合成（透明起点 + 白色形状 + `destination-out` 挖边）生成 alpha 蒙版，再 `destination-in` 应用到头图
- **EPUB 打包**：JSZip 生成 ZIP，`mimetype` 以 STORE 方式置于首位，含 nav + ncx 双目录、`dc:subject` 标签
- **兼容性**：需要支持 WebAssembly 的现代浏览器（Chrome / Edge / Safari / Firefox 均可）

## 相关

桌面版（功能更全：分卷、查找替换、广告清理、注释、正文编辑、文字锚点插图）见仓库根目录。

## 许可证

[MIT](https://github.com/kasaki-7/kasaki-book-typesetting/blob/main/LICENSE)
