"""Extract an ordered, chapter-addressable text copy of a local document."""

import argparse
import hashlib
import json
import posixpath
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HTML_FILES = {".xhtml", ".html", ".htm"}
CHAPTER_HEADING = re.compile(
    r"^(?:第[〇零一二三四五六七八九十百千万\d]+[章节卷篇]|"
    r"(?:chapter|part|book)\s+[\divxlcdm]+\b)", re.IGNORECASE
)


def chapter(title, source, paragraphs):
    return {"title": title, "source": source, "paragraphs": paragraphs}


def xml(data):
    # Office and EPUB packages require no DTD to decode their document text.
    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", data.replace(b"\0", b""), re.I):
        raise ValueError("A package XML file contains an unsupported DTD or entity declaration.")
    return ET.fromstring(data)


def group_blocks(blocks, source, fallback, limit=6500):
    """Use the shallowest heading level, or split unstructured text at paragraph boundaries."""
    depths = [depth for depth, _ in blocks if depth is not None]
    counts = Counter(depths)
    top = min((depth for depth in counts if counts[depth] > 1), default=min(depths, default=None))
    result = []
    current = []
    title = fallback
    size = 0
    for depth, text in blocks:
        if current and ((top is not None and depth == top) or (top is None and size >= limit)):
            result.append(chapter(title, source, current))
            current = []
            title = f"{fallback} · {len(result) + 1}"
            size = 0
        if top is not None and depth == top:
            title = text.splitlines()[0]
        current.append(text)
        size += len(text)
    if current:
        result.append(chapter(title, source, current))
    return result


def word_text(node):
    separators = {WORD + "br": "\n", WORD + "cr": "\n", WORD + "tab": "\t", WORD + "noBreakHyphen": "\u2011"}
    return "".join((child.text or "") if child.tag == WORD + "t" else separators.get(child.tag, "")
                   for child in node.iter())


def word_blocks(parent, styles):
    for node in parent:
        if node.tag == WORD + "p":
            text = word_text(node)
            if not text.strip():
                continue
            style = node.find(f"{WORD}pPr/{WORD}pStyle")
            depth = styles.get(style.get(WORD + "val")) if style is not None else None
            level = node.find(f"{WORD}pPr/{WORD}outlineLvl")
            if level is not None and level.get(WORD + "val", "").isdigit():
                depth = int(level.get(WORD + "val")) + 1
            if depth is None and len(text) < 100 and CHAPTER_HEADING.match(text.strip()):
                depth = 1
            yield (depth, text)
        elif node.tag == WORD + "tbl":
            for row in node.findall(WORD + "tr"):
                cells = ["\n".join(text for _, text in word_blocks(cell, styles))
                         for cell in row.findall(WORD + "tc")]
                if any(cells):
                    yield (None, "\t".join(cells))
        elif node.tag in {WORD + "sdt", WORD + "sdtContent", WORD + "customXml", WORD + "ins"}:
            yield from word_blocks(node, styles)


def read_docx(path):
    with ZipFile(path) as package:
        names = set(package.namelist())
        document = xml(package.read("word/document.xml"))
        body = document.find(WORD + "body")
        if body is None:
            raise ValueError("The Word package has no document body.")
        styles = {}
        if "word/styles.xml" in names:
            for style in xml(package.read("word/styles.xml")).findall(WORD + "style"):
                ident = style.get(WORD + "styleId", "")
                level = style.find(f"{WORD}pPr/{WORD}outlineLvl")
                heading = re.fullmatch(r"heading\s*(\d+)", ident, re.I)
                if level is not None and level.get(WORD + "val", "").isdigit():
                    number = int(level.get(WORD + "val"))
                    if number < 9:
                        styles[ident] = number + 1
                elif heading:
                    styles[ident] = int(heading[1])
        chapters = group_blocks(list(word_blocks(body, styles)), "Word · 正文", "正文")
        for filename, label in (("footnotes", "脚注"), ("endnotes", "尾注")):
            member = f"word/{filename}.xml"
            if member not in names:
                continue
            paragraphs = [text for note in xml(package.read(member))
                          for _, text in word_blocks(note, styles)]
            if paragraphs:
                chapters.append(chapter(label, "Word · " + label, paragraphs))
        core = xml(package.read("docProps/core.xml")) if "docProps/core.xml" in names else None
        title = core.findtext("{*}title") if core is not None else None
    return title, chapters


class EbookText(HTMLParser):
    headings = {f"h{i}": i for i in range(1, 7)}
    boundaries = set(headings) | {"p", "li", "td", "th", "div", "section", "aside", "blockquote", "figcaption", "pre"}
    skip = {"head", "style", "script", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.parts = []
        self.depth = None
        self.skipping = None

    def flush(self):
        text = "\n".join(" ".join(line.split()) for line in "".join(self.parts).split("\n")).strip()
        if text:
            self.blocks.append((self.depth, text))
        self.parts.clear()

    def handle_starttag(self, tag, attrs):
        if self.skipping:
            return
        if tag in self.skip:
            self.skipping = tag
        elif tag in self.boundaries:
            self.flush()
            self.depth = self.headings.get(tag)
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.parts.append(alt)

    def handle_endtag(self, tag):
        if tag == self.skipping:
            self.skipping = None
        elif not self.skipping and tag in self.boundaries:
            self.flush()
            self.depth = None

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(re.sub(r"\s+", " ", data))


def read_epub(path):
    with ZipFile(path) as package:
        rootfile = xml(package.read("META-INF/container.xml")).find(".//{*}rootfile")
        if rootfile is None:
            raise ValueError("The EPUB has no package document declared in container.xml.")
        opf_name = rootfile.attrib["full-path"]
        opf = xml(package.read(opf_name))
        title = opf.findtext("{*}metadata/{*}title")
        manifest = {item.attrib["id"]: item.attrib["href"] for item in opf.findall("{*}manifest/{*}item")}
        chapters = []
        seen = set()
        for item in opf.findall("{*}spine/{*}itemref"):
            url = urlsplit(manifest[item.attrib["idref"]])
            if url.scheme or url.netloc:
                raise ValueError("A reading-order item references a remote resource.")
            name = posixpath.normpath(posixpath.join(posixpath.dirname(opf_name), unquote(url.path)))
            if name in seen:
                continue
            seen.add(name)
            if Path(name).suffix.lower() not in HTML_FILES:
                continue
            raw = package.read(name)
            if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                content = raw.decode("utf-16")
            else:
                content = raw.decode("utf-8-sig")
            parser = EbookText()
            parser.feed(content)
            parser.close()
            parser.flush()
            chapters.extend(group_blocks(parser.blocks, f"EPUB · {name}", f"文档 {len(seen)}"))
        return title, chapters


def ocr_page(path, number, language):
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise ValueError("OCR requires pdftoppm (Poppler) and Tesseract on PATH.")
    with tempfile.TemporaryDirectory(prefix="book-ocr-") as work:
        image = Path(work) / "page"
        subprocess.run(["pdftoppm", "-f", str(number), "-l", str(number), "-r", "300",
                        "-singlefile", "-png", str(path), str(image)], check=True, timeout=120)
        result = subprocess.run(["tesseract", str(image.with_suffix(".png")), "stdout", "-l", language],
                                capture_output=True, check=True, timeout=180)
        return result.stdout.decode("utf-8")


def read_pdf(path, ocr_language):
    from pypdf import PdfReader

    reader = PdfReader(path)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("The PDF is encrypted. Supply a readable copy.")
    starts = {}
    for item in reader.outline:
        if isinstance(item, list):
            continue
        index = reader.get_destination_page_number(item)
        if index is not None and 0 <= index < len(reader.pages):
            starts.setdefault(index, item.title)

    chapters = []
    paragraphs = []
    page_count = len(reader.pages)
    first = 0
    section_title = starts.get(0, "正文")
    size = 0
    extracted_text = False
    for index, page in enumerate(reader.pages):
        if index > first and (index in starts or (not starts and size >= 6500)):
            chapters.append(chapter(section_title, f"PDF · 第 {first + 1}–{index} 页", paragraphs))
            paragraphs = []
            first = index
            section_title = starts.get(index, f"第 {index + 1} 页起")
            size = 0
        text = page.extract_text() or ""
        ocr_used = False
        if not text.strip() and (ocr_language or len(page.images)):
            if not ocr_language:
                raise ValueError(f"PDF page {index + 1} has images and no text. Rerun with --ocr LANGUAGE.")
            text = ocr_page(path, index + 1, ocr_language)
            if not text.strip() and len(page.images):
                raise ValueError(f"OCR produced no text on PDF page {index + 1}. Review that page before proceeding.")
            ocr_used = True
        paragraphs.append(f"【PDF 第 {index + 1} 页{' · OCR' if ocr_used else ''}】")
        paragraphs.extend(part.strip() for part in re.split(r"\n\s*\n", text) if part.strip())
        extracted_text = extracted_text or bool(text.strip())
        size += len(text)
    if not extracted_text:
        raise ValueError("The PDF contains no extractable text.")
    if paragraphs:
        chapters.append(chapter(section_title, f"PDF · 第 {first + 1}–{page_count} 页", paragraphs))
    return (reader.metadata.title if reader.metadata else None), chapters


def convert_doc(path):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise ValueError("Old .doc files need LibreOffice on PATH or a .docx copy.")
    with tempfile.TemporaryDirectory(prefix="book-doc-") as work:
        profile = (Path(work) / "profile").resolve().as_uri()
        subprocess.run([soffice, "-env:UserInstallation=" + profile, "--headless", "--convert-to",
                        "docx", "--outdir", work, str(path)], check=True, timeout=150)
        return read_docx(Path(work) / (path.stem + ".docx"))


def extract(path, custom_title=None, ocr=None):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        title, chapters = read_pdf(path, ocr)
    elif suffix == ".docx":
        title, chapters = read_docx(path)
    elif suffix == ".doc":
        title, chapters = convert_doc(path)
    elif suffix == ".epub":
        title, chapters = read_epub(path)
    else:
        raise ValueError("Supported formats are PDF, DOCX, DOC, and EPUB.")
    if not chapters:
        raise ValueError("No readable chapters were extracted.")
    with path.open("rb") as source:
        identity = hashlib.file_digest(source, "sha256").hexdigest()[:24]
    return {
        "id": identity, "title": custom_title or (title or "").strip() or path.stem,
        "name": path.name, "format": suffix[1:],
        "chapters": [{"n": index, **item} for index, item in enumerate(chapters, 1)],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--title")
    parser.add_argument("--ocr", metavar="LANGUAGE", help="Tesseract languages for PDF pages with no text")
    args = parser.parse_args()
    try:
        book = extract(args.source.resolve(strict=True), args.title, args.ocr)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except ImportError as error:
        parser.exit(1, f"PDF input requires pypdf. Install it with python -m pip install pypdf. ({error})\n")
    except (OSError, ValueError, KeyError, BadZipFile, ET.ParseError, UnicodeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Extraction failed: {error}\n")
    print(f"{len(book['chapters'])} readable sections → {args.out}")


if __name__ == "__main__":
    main()
