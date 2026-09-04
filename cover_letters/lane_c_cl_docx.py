#!/usr/bin/env python3
"""Build a Lane C cover letter by replacing text in a retained DOCX template.

Only word/document.xml is changed. Every other package part is copied byte-for-byte
from the formatting authority.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from pathlib import Path


TEXT_NODE = re.compile(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", re.DOTALL)


def build(payload_path: Path) -> Path:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    template = Path(payload["template_path"])
    output = Path(payload["output_path"])

    paragraphs = payload["paragraphs"]
    address = payload["address"]
    if len(paragraphs) != 4 or len(address) != 3:
        raise ValueError("Lane C cover letters require four body paragraphs and three address lines")

    replacement_text = [
        payload["name"],
        payload["contact"],
        payload["date"],
        *address,
        payload["salutation"],
        *paragraphs,
        payload.get("closing", "Sincerely,"),
        payload["name"],
    ]

    with zipfile.ZipFile(template, "r") as source:
        document_xml = source.read("word/document.xml").decode("utf-8")
        matches = list(TEXT_NODE.finditer(document_xml))
        if len(matches) != len(replacement_text):
            raise ValueError(
                f"Template has {len(matches)} text nodes; expected {len(replacement_text)}"
            )

        cursor = 0
        pieces: list[str] = []
        for match, replacement in zip(matches, replacement_text):
            pieces.append(document_xml[cursor : match.start()])
            pieces.append(match.group(1))
            pieces.append(html.escape(replacement, quote=False))
            pieces.append(match.group(3))
            cursor = match.end()
        pieces.append(document_xml[cursor:])
        patched_document_xml = "".join(pieces).encode("utf-8")

        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite existing artifact: {output}")
        with zipfile.ZipFile(output, "w") as target:
            for item in source.infolist():
                data = patched_document_xml if item.filename == "word/document.xml" else source.read(item.filename)
                target.writestr(item, data)

    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    print(build(args.payload))


if __name__ == "__main__":
    main()
