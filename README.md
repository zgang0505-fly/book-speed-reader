# 图解速读工作台 · Book Speed Reader

把一本 PDF、Word 或 EPUB 做成可直接在浏览器打开的速读网页。每节先显示要点和原书案例，下方可以展开原文。思维导图可以一键收起、展开所有章节或展开全部摘要。浏览器会记录每本书的已读进度。

## 安装到 Codex

克隆到 Codex 的个人技能目录，然后重新打开 Codex。

macOS / Linux

```sh
git clone https://github.com/zhaogang8105-ai/book-speed-reader.git ~/.codex/skills/book-speed-reader
```

Windows PowerShell

```powershell
git clone https://github.com/zhaogang8105-ai/book-speed-reader.git "$env:USERPROFILE/.codex/skills/book-speed-reader"
```

在 Codex 里附上你的书并发送下面这条指令。

> 用 $book-speed-reader 把这本书做成速读网页。每章提炼主要观点，选用原书中的具体案例，在速读下方保留可展开的原文，并加上能展开全部摘要的思维导图。

## 也可以直接运行脚本

需要 Python 3.11+。PDF 另外需要 `python -m pip install pypdf`。DOCX 和 EPUB 不用额外 Python 包。扫描版 PDF 的 OCR 和旧 Word 格式依赖见[格式说明](references/formats.md)。

```sh
python scripts/extract_book.py "book.epub" --out work/book.json
python scripts/build_reader.py work/book.json work/notes.json --out output/index.html
```

第一步保留按原书顺序提取的文本。由 Codex 根据原文撰写 `notes.json`，也可以按[说明中的结构](references/formats.md#notes-json)手工填写。第二步输出可离线打开的 HTML。需要保留版式、原图或原始文件时，在第二步加 `--attach-source "book.epub"` 并随网页一起保留生成的源附件。

本仓库用自编测试文本验证格式处理。Markmap 与 D3 随模板提供，其许可证见 [assets](assets/)。

---

Book Speed Reader is a Codex skill that turns a local book into a self-contained browser reader. It combines extracted source text, model-written section notes and examples, a collapsible mind map, and browser-local progress. Install the skill as shown above, attach your PDF, Word document, or EPUB, and ask Codex to use `$book-speed-reader`.
