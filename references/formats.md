# Formats and reader data

Use Python 3.11 or newer. DOCX and EPUB extraction only use the standard library.

| Input | How text is organized | Dependencies and source fidelity |
| --- | --- | --- |
| PDF | Top-level bookmarks delimit sections at page boundaries. Without bookmarks, adjacent pages are grouped into sequential reading sections. The original panel shows page markers. | Install `pypdf` for PDF. If pages are scans, install Poppler and Tesseract with the source language data, then rerun with `--ocr chi_sim+eng` or the appropriate languages. Check OCR against the scanned pages, especially figures, numbers and tables. |
| DOCX | Heading styles and clear chapter labels delimit sections. Unstructured text is grouped at paragraph boundaries. Standard table rows, footnotes and endnotes are included as text. | Word layout, drawings and embedded objects are available in the attached original if needed. |
| DOC | Convert the legacy file to DOCX, then follow the Word path. | Install LibreOffice and make `soffice` available on PATH. A user-supplied DOCX copy also works. |
| EPUB | Read the package spine in order and use the document headings. Text on supplemental spine pages stays in reading order. | Use a readable, unencrypted EPUB. The original file preserves figures, links, pagination and typography. |

Text extraction is best-effort for multi-column layouts, formulas, unusual encodings, or poorly recognized scans. Compare the extraction with the relevant pages. Use `--attach-source SOURCE` during the build when the source's layout, figures or tables matter or the user wants the actual file alongside the reader. The attachment is a byte-for-byte copy and must ship in the same folder as the HTML. Include both when delivering or hosting that reader.

## Notes JSON

The extractor writes the source title, file name, stable source ID, and ordered `chapters`. Each chapter has `n`, `title`, `source`, and `paragraphs`. Treat this as the text record. Changes to chapter boundaries should preserve paragraph order and contents, then renumber chapter IDs from 1.

Write UTF-8 `notes.json` with the following shape. The text here illustrates shape only.

```json
{
  "intro": "本书围绕一个问题展开，并用两个案例说明条件如何改变结果。",
  "chapters": [
    {
      "n": 1,
      "theme": "核心机制",
      "summary": "一句话说清这一节的主要结论。",
      "detail": "顺着原文交代原因、过程及适用条件。",
      "examples": ["复述原文中的具体人物、事件或机制，并说明它与结论的关系。"]
    }
  ]
}
```

- Cover all extracted IDs exactly once. Use a meaningful theme name for each contiguous group of sections. The builder retains source order.
- `intro` and `figures` are optional. For a figure, give `title` and `path` relative to the notes directory, with optional `caption`, `start` and `end` section IDs. Use PNG, JPEG or WebP. Figures are embedded and offered from their matching sections and the gallery. Use images the user can include and check that they illuminate the chapter.
- `examples` can hold one or more concise source cases. Use `[]` if an index, preface, or other section offers no example. An explanation may use a source analogy with attribution.
- The reader keeps progress in browser storage under the source ID. Rebuilding for the same file preserves the key. Moving the HTML or switching browsers can affect browser-local storage. When file URL storage is restricted, serve the output folder on loopback with `python -m http.server 8000 --bind 127.0.0.1 --directory OUTPUT`.
