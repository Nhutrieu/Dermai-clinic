import json
import re
from pathlib import Path

import numpy as np

from .schemas import Citation

REFUSAL = (
    "Tôi không thể kê đơn hoặc đưa ra liều thuốc. "
    "Bạn nên trao đổi trực tiếp với bác sĩ da liễu."
)
NO_EVIDENCE = (
    "Tài liệu hiện có chưa cung cấp đủ thông tin đáng tin cậy để trả lời câu hỏi này."
)
MEDICATION_PATTERN = re.compile(
    r"\b(kê\s*đơn|đơn\s*thuốc|liều|uống\s*bao\s*nhiêu|thuốc\s*gì|prescri|dosage)\b",
    re.IGNORECASE,
)


class RagStore:
    def __init__(self, path: Path):
        self.path = path
        self.index = self.chunks = self.encoder = None

    @property
    def ready(self) -> bool:
        return self.index is not None

    def load(self) -> None:
        index_file, chunks_file = self.path / "vectors.npy", self.path / "chunks.json"
        if not index_file.exists() or not chunks_file.exists():
            return
        from sentence_transformers import SentenceTransformer
        self.encoder = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        self.index = np.load(index_file)
        self.chunks = json.loads(chunks_file.read_text(encoding="utf-8"))

    def answer(self, question: str) -> tuple[str, list[Citation], bool]:
        if MEDICATION_PATTERN.search(question):
            return REFUSAL, [], True
        if not self.ready:
            return NO_EVIDENCE, [], False
        vector = self.encoder.encode([question], normalize_embeddings=True)[0]
        scores = self.index @ vector
        ids = np.argsort(scores)[::-1][:4]
        selected = [self.chunks[int(i)] for i in ids if scores[int(i)] >= 0.35]
        if not selected:
            return NO_EVIDENCE, [], False
        # Extractive mode is deterministic and cannot introduce unsupported facts.
        excerpts = [item["text"].strip() for item in selected[:2]]
        citations = [
            Citation(source=item["source"], page=item["page"]) for item in selected[:2]
        ]
        answer = "\n\n".join(excerpts)
        return answer, citations, False

