"""Combine extracted text and source-grounded notes into an offline reader."""

import argparse
import base64
import hashlib
import json
import shutil
from itertools import groupby
from pathlib import Path


ASSETS = Path(__file__).resolve().parents[1] / "assets"
IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def required_text(record, key, context):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} needs a nonempty {key!r} field.")
    return value.strip()


def read_figures(notes, notes_path, total):
    figures = []
    base = notes_path.resolve().parent
    for figure in notes.get("figures", []):
        if not isinstance(figure, dict):
            raise ValueError("Each figure must be an object.")
        title = required_text(figure, "title", "Figure")
        path = (base / required_text(figure, "path", title)).resolve()
        mime = IMAGES.get(path.suffix.lower())
        if not path.is_relative_to(base) or not mime:
            raise ValueError(f"{title} needs a PNG, JPEG, or WebP inside the notes directory.")
        start, end = figure.get("start", 1), figure.get("end", total)
        if not (type(start) is type(end) is int and 1 <= start <= end <= total):
            raise ValueError(f"{title} has an invalid section range.")
        source = f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        figures.append({"title": title, "caption": figure.get("caption", ""), "start": start,
                        "end": end, "src": source})
    return figures


def assemble(book, notes, notes_path):
    extracted = book["chapters"]
    authored = notes["chapters"]
    expected = list(range(1, len(extracted) + 1))
    if [item["n"] for item in extracted] != expected or not extracted:
        raise ValueError("Extracted sections must be nonempty and numbered from 1 in source order.")
    numbers = [item["n"] for item in authored]
    if any(type(number) is not int for number in numbers) or sorted(numbers) != expected:
        raise ValueError("Notes must cover every extracted section exactly once, with integer n values.")
    by_number = {item["n"]: item for item in authored}
    chapters = []
    for source in extracted:
        n = source["n"]
        note = by_number[n]
        label = f"Section {n}"
        examples = note.get("examples")
        if not isinstance(examples, list) or any(not isinstance(example, str) or not example.strip() for example in examples):
            raise ValueError(f"{label} needs an examples array of nonempty strings, or [] if there is no source example.")
        paragraphs = source["paragraphs"]
        if not isinstance(paragraphs, list) or not paragraphs or any(not isinstance(p, str) for p in paragraphs):
            raise ValueError(f"{label} has malformed extracted text.")
        chapters.append({
            **source,
            "theme": required_text(note, "theme", label),
            "summary": required_text(note, "summary", label),
            "detail": required_text(note, "detail", label),
            "examples": [example.strip() for example in examples],
        })
    groups = [{"title": title, "chapters": list(items)} for title, items in groupby(chapters, key=lambda item: item["theme"])]
    return {
        "id": book["id"],
        "title": required_text(book, "title", "Book"),
        "name": book["name"],
        "intro": notes.get("intro", ""),
        "themes": groups,
        "figures": read_figures(notes, notes_path, len(chapters)),
    }


def build(book_path, notes_path, output_path, attachment=None):
    data = assemble(read_json(book_path), read_json(notes_path), notes_path)
    assets = (
        ("<!-- READER_CSS -->", "<style>" + (ASSETS / "site.css").read_text(encoding="utf-8") + "</style>"),
        ("<!-- MAP_RUNTIME -->", "<script>" + (ASSETS / "map-runtime.js").read_text(encoding="utf-8") + "</script>"),
        ("<!-- READER_RUNTIME -->", "<script>" + (ASSETS / "reader.js").read_text(encoding="utf-8") + "</script>"),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if attachment:
        attachment = attachment.resolve(strict=True)
        with attachment.open("rb") as stream:
            identity = hashlib.file_digest(stream, "sha256").hexdigest()[:24]
        if identity != data["id"]:
            raise ValueError("--attach-source must be the same file used for extraction.")
        target = output_path.parent / ("source-" + identity + attachment.suffix.lower())
        if target.resolve() != attachment and not target.exists():
            shutil.copyfile(attachment, target)
        if target.resolve() != attachment and target.exists():
            with target.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest()[:24] != identity:
                    raise ValueError(f"The existing attachment does not match the source: {target}")
        data["attachment"] = target.name

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = (ASSETS / "reader.html").read_text(encoding="utf-8")
    for marker, contents in (*assets, ("<!-- BOOK_DATA -->", '<script type="application/json" id="book-data">' + payload + '</script>')):
        html = html.replace(marker, contents, 1)
    licenses = "\n".join((ASSETS / name).read_text(encoding="utf-8") for name in ("d3-LICENSE.txt", "markmap-LICENSE.txt"))
    html = html.replace("<!-- VENDOR_LICENSES -->", "<!--\n" + licenses + "\n-->")
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(html, encoding="utf-8")
    temporary.replace(output_path)
    return sum(len(group["chapters"]) for group in data["themes"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book", type=Path, help="Extracted book JSON")
    parser.add_argument("notes", type=Path, help="Source-grounded notes JSON")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attach-source", type=Path, help="Copy the unchanged original alongside the HTML")
    args = parser.parse_args()
    try:
        count = build(args.book, args.notes, args.out, args.attach_source)
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(f"{count} sections → {args.out}")


if __name__ == "__main__":
    main()
