import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


def clean_text(text: str) -> str:
    replacements = {"ƣ": "ư", "Ƣ": "Ư", "Ö": "Ú"}
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def chunks(text: str, size: int = 1100, overlap: int = 120):
    cleaned = clean_text(text)
    for start in range(0, len(cleaned), size - overlap):
        part = cleaned[start:start + size].strip()
        if len(part) >= 120:
            yield part


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("rag/index"))
    args = parser.parse_args()
    reader, items = PdfReader(args.pdf), []
    for page_number, page in enumerate(reader.pages, 1):
        for part in chunks(page.extract_text() or ""):
            items.append({"source": args.pdf.name, "page": page_number, "text": part})
    if not items:
        raise SystemExit("PDF không có text; cần OCR trước khi ingest.")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "chunks.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    metadata = {
        "source": args.pdf.name,
        "sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "pages": len(reader.pages),
        "chunks": len(items),
        "chunk_size": 1100,
        "overlap": 120,
        "retrieval": "tfidf_word_unigram_bigram",
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Indexed {len(items)} chunks from {len(reader.pages)} pages.")


if __name__ == "__main__":
    main()
