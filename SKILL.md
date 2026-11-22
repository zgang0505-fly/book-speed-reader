---
name: book-speed-reader
description: Turn a supplied PDF, Word, or EPUB into an interactive speed-reading webpage with all extracted original text, section-by-section takeaways, source examples, a collapsible mind map, and reading progress. Use for 图解速读、拆书网页、逐章原文与导图 requests.
---

# 图解速读工作台

Convert the user's supplied document into an HTML reader they can open. Keep the reading order and defaults used by the template: section takeaways and examples first, original text collapsed underneath, and progress stored per book in the browser. The map supports topic overview, chapter titles, all summaries, and fit-to-view.

1. Extract the file with `scripts/extract_book.py SOURCE --out WORK/book.json`. Check the extracted title, section count, boundaries, and source order. PDF bookmark ranges and Word/EPUB headings can be incomplete. Use source page ranges or contiguous paragraph boundaries when the document needs a correction. Keep every extracted paragraph when adjusting sections.
2. Read each section's original text and write a short takeaway, an explanation, and any concrete cases the section actually supports. For long books, read bounded groups of sections and check that the notes cover every section exactly once. Use the document's language or the user's requested language. Give the case a name or circumstances and explain what it illustrates. Attribute a source-specific claim as needed. Use an empty examples array for sections with no grounded case.
3. Build with `scripts/build_reader.py WORK/book.json WORK/notes.json --out OUTPUT/index.html`. Read [formats and note schema](references/formats.md) for optional figures, exact source attachment, OCR, and JSON fields. The output HTML embeds its own assets and works without a server. If the user requests hosting, use the authorized hosting workflow in their environment and preserve the intended audience for the original.
4. Check the generated reader in a browser. Verify that early, middle, and late sections show their own notes and original, the next-section action preserves progress after reload when browser storage is available, and the mind map opens and fits in all-summary mode. Provide the working browser entry and state any text extraction or OCR limitations that affect the result.

Keep source documents, work files and generated readers in the user's output workspace. A request to share or publish this skill package applies to its instructions, scripts and template. Publishing a reader containing a book is a separate action governed by the user's requested destination and audience.
