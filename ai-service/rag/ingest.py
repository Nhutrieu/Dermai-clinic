import argparse
import json
import re
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


def chunks(text: str, size: int = 3200, overlap: int = 500):
    cleaned = re.sub(r"\s+", " ", text).strip()
    for start in range(0, len(cleaned), size - overlap):
        part = cleaned[start:start + size].strip()
        if len(part) >= 150:
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
    encoder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vectors = encoder.encode(
        [x["text"] for x in items], normalize_embeddings=True, show_progress_bar=True
    )
    args.output.mkdir(parents=True, exist_ok=True)
    np.save(args.output / "vectors.npy", vectors)
    (args.output / "chunks.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Indexed {len(items)} chunks from {len(reader.pages)} pages.")


if __name__ == "__main__":
    main()

