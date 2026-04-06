#!/usr/bin/env python
"""Convert a .docx file into plain text with tables and extracted images.

Usage:
    python scripts/docx_to_text.py --input-docx /path/to/file.docx [--output-txt /path/to/file.txt]
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_project

REPO_ROOT = bootstrap_project(__file__)

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from pptflow.cli import run_cli
from pptflow.errors import InputError

TOOL_NAME = "docx_to_text"
REL_EMBED_KEY = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"


def _iter_block_items(document: DocxDocument) -> Iterator[Paragraph | Table]:
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _extract_text_from_paragraph(paragraph: Paragraph) -> str:
    text = paragraph.text.replace("\xa0", " ").strip()
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())


def _extract_table_lines(table: Table) -> list[str]:
    lines: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            cell_text = cell.text.replace("\xa0", " ").strip()
            normalized = " / ".join(part.strip() for part in cell_text.splitlines() if part.strip())
            cells.append(normalized)
        if any(cells):
            lines.append(" | ".join(cells))
    return lines


def _extract_image_suffix(content_type: str | None) -> str:
    if not content_type or "/" not in content_type:
        return ".bin"
    subtype = content_type.split("/", 1)[1].strip().lower()
    if subtype == "jpeg":
        return ".jpg"
    return f".{subtype}" if subtype else ".bin"


def _resolve_image_parts(block: Paragraph | Table) -> list[tuple[bytes, str]]:
    rel_ids: list[str] = []
    for node in block._element.iter():  # pyright: ignore[reportPrivateUsage]
        if node.tag.endswith("}blip"):
            rel_id = node.attrib.get(REL_EMBED_KEY)
            if rel_id:
                rel_ids.append(rel_id)

    image_parts: list[tuple[bytes, str]] = []
    for rel_id in rel_ids:
        relationship = block.part.related_parts.get(rel_id)
        if relationship is None:
            continue
        image_blob = getattr(relationship, "blob", None)
        content_type = getattr(relationship, "content_type", None)
        if image_blob:
            image_parts.append((image_blob, _extract_image_suffix(content_type)))
    return image_parts


def _render_docx_to_text(input_docx: Path, image_dir: Path) -> tuple[str, dict[str, int], list[str]]:
    document = Document(str(input_docx))

    blocks: list[str] = []
    artifacts: list[str] = []
    metrics = {"paragraphs": 0, "tables": 0, "images": 0}
    image_counter = 0
    image_dir.mkdir(parents=True, exist_ok=True)
    doc_stem = input_docx.stem

    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            paragraph_text = _extract_text_from_paragraph(block)
            if paragraph_text:
                blocks.append(paragraph_text)
                metrics["paragraphs"] += 1
        else:
            table_lines = _extract_table_lines(block)
            if table_lines:
                blocks.append("[表格]")
                blocks.extend(table_lines)
                metrics["tables"] += 1

        image_parts = _resolve_image_parts(block)
        if not image_parts:
            continue

        for image_blob, suffix in image_parts:
            image_counter += 1
            metrics["images"] += 1
            image_path = (image_dir / f"{doc_stem}_image_{image_counter:03d}{suffix}").resolve()
            image_path.write_bytes(image_blob)
            artifacts.append(str(image_path))
            blocks.append(f"[此处有图片]{image_path}")

    rendered = "\n\n".join(block for block in blocks if block.strip()).strip()
    if not rendered:
        raise InputError("文档未提取到任何文本内容", details={"input_docx": str(input_docx)})
    return f"{rendered}\n", metrics, artifacts


def handle_docx_to_text(args: argparse.Namespace) -> dict[str, Any]:
    input_docx = Path(args.input_docx).expanduser().resolve()
    if not input_docx.exists():
        raise InputError("input_docx 不存在", details={"input_docx": str(input_docx)})
    if input_docx.suffix.lower() != ".docx":
        raise InputError("仅支持 .docx 文件", details={"input_docx": str(input_docx)})

    output_txt = (
        Path(args.output_txt).expanduser().resolve()
        if args.output_txt
        else input_docx.with_suffix(".txt")
    )
    image_dir = (
        Path(args.image_dir).expanduser().resolve()
        if args.image_dir
        else (REPO_ROOT / "PPT" / "pic").resolve()
    )

    rendered_text, metrics, image_artifacts = _render_docx_to_text(input_docx, image_dir)
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    output_txt.write_text(rendered_text, encoding="utf-8")

    return {
        "artifacts": [str(output_txt), *image_artifacts],
        "metrics": metrics,
        "input_docx": str(input_docx),
        "output_txt": str(output_txt),
        "image_dir": str(image_dir),
        "image_artifacts": image_artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    parser.add_argument("--input-docx", required=True, help=".docx 文件路径")
    parser.add_argument("--output-txt", default=None, help="输出 .txt 路径，默认与源文件同名")
    parser.add_argument("--image-dir", default=None, help="图片输出目录，默认写入 PPT/pic")
    return run_cli(handle_docx_to_text, tool=TOOL_NAME, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
