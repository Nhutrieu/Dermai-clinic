import json
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .schemas import Citation, DiseaseGuidance

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
PATIENT_UNSAFE_EXCERPT = re.compile(
    r"\b(điều\s*trị|phác\s*đồ|liều|mg|ml|thuốc|bôi|uống|tiêm|kháng\s*sinh|corticoid)\b",
    re.IGNORECASE,
)

# Trang PDF chứa phần đại cương và biểu hiện lâm sàng. Chủ động không lấy các
# trang phác đồ điều trị để nội dung bệnh nhân nhận được không giống đơn thuốc.
DISEASE_GUIDANCE = {
    "Acne": {
        "title": "Hướng xử trí tham khảo cho mụn trứng cá",
        "query": "trứng cá acne nguyên tắc điều trị kiểm soát chất bã dày sừng viêm",
        "pages": {27, 28},
        "summary": "• Điều trị tập trung kiểm soát tiết bã, dày sừng và tình trạng viêm.\n\n• Phương án cần được chọn theo mức độ tổn thương và đặc điểm từng người.\n\n• Tránh tự nặn hoặc tác động mạnh lên vùng mụn.",
    },
    "Candidiasis": {
        "title": "Hướng xử trí tham khảo cho Candida",
        "query": "Candida da niêm mạc nguyên tắc điều trị phòng bệnh vệ sinh giữ khô",
        "pages": {53, 54, 55},
        "summary": "• Cần xác định và loại bỏ những yếu tố thuận lợi khiến Candida phát triển.\n\n• Giữ vùng da, nếp gấp và quần áo sạch, khô thoáng.\n\n• Tổn thương lan rộng hoặc tái phát cần được khám trực tiếp.",
    },
    "Eczema": {
        "title": "Hướng xử trí tham khảo cho chàm",
        "query": "chàm eczema viêm da cơ địa điều trị chăm sóc tắm làm ẩm phòng bệnh",
        "pages": {118, 119},
        "summary": "• Tắm bằng nước ấm, dùng sản phẩm làm sạch ít kích ứng và giữ ẩm da đều đặn.\n\n• Hạn chế gãi và tránh các yếu tố làm bệnh bùng phát.\n\n• Khi da rỉ dịch, đau hoặc có dấu hiệu nhiễm trùng, cần đi khám.",
    },
    "Lupus": {
        "title": "Hướng xử trí tham khảo cho biểu hiện da lupus",
        "query": "lupus ban đỏ điều trị phòng bệnh tránh nắng theo dõi",
        "pages": {83, 88},
        "summary": "• Bảo vệ da khỏi ánh nắng bằng che chắn phù hợp.\n\n• Lupus có thể liên quan nhiều cơ quan nên cần bác sĩ đánh giá và theo dõi lâu dài.\n\n• Không trì hoãn khám khi xuất hiện triệu chứng toàn thân.",
    },
    "Psoriasis": {
        "title": "Hướng xử trí tham khảo cho vảy nến",
        "query": "vảy nến psoriasis chiến lược điều trị duy trì dự phòng bùng phát",
        "pages": {165, 166, 167},
        "summary": "• Điều trị thường gồm giai đoạn kiểm soát tổn thương và giai đoạn duy trì ổn định.\n\n• Duy trì sinh hoạt điều độ và tránh yếu tố làm bệnh bùng phát.\n\n• Cần phối hợp theo dõi vì bệnh có thể tái phát theo từng đợt.",
    },
    "SkinCancer": {
        "title": "Hướng xử trí khi nghi ngờ tổn thương ung thư da",
        "query": "ung thư da nguyên tắc điều trị loại bỏ tổn thương theo dõi tái phát",
        "pages": {224, 225, 229, 230, 236, 237, 238},
        "summary": "• Đây là nhóm cần được khám chuyên khoa sớm để xác định chính xác.\n\n• Hướng điều trị phụ thuộc loại tổn thương, mức độ xâm lấn và kết quả mô bệnh học.\n\n• Sau điều trị cần được theo dõi tái phát và tổn thương mới.",
    },
    "Tinea": {
        "title": "Hướng xử trí tham khảo cho nấm da",
        "query": "nấm da dermatophytosis nguyên tắc điều trị loại bỏ yếu tố phòng bệnh vệ sinh",
        "pages": {49, 50},
        "summary": "• Giữ vùng da khô sạch và loại bỏ các yếu tố thuận lợi cho nấm phát triển.\n\n• Không dùng chung quần áo, khăn hoặc vật dụng cá nhân.\n\n• Tổn thương lan rộng hay dai dẳng cần được kiểm tra trực tiếp.",
    },
    "Warts": {
        "title": "Hướng xử trí tham khảo cho hạt cơm (mụn cóc)",
        "query": "hạt cơm mụn cóc warts điều trị tùy từng trường hợp",
        "pages": {75, 76, 77},
        "summary": "• Không có một phương án phù hợp cho mọi loại hạt cơm.\n\n• Cách xử trí phụ thuộc vị trí, số lượng và đặc điểm tổn thương.\n\n• Không tự cắt, đốt hoặc làm tổn thương vùng da tại nhà.",
    },
}


class RagStore:
    def __init__(self, path: Path):
        self.path = path
        self.index = None
        self.chunks: list[dict] | None = None
        self.vectorizer: TfidfVectorizer | None = None

    @property
    def ready(self) -> bool:
        return self.index is not None and bool(self.chunks)

    def load(self) -> None:
        chunks_file = self.path / "chunks.json"
        if not chunks_file.exists():
            return
        chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
        self.chunks = [item for item in chunks if item.get("text", "").strip()]
        if not self.chunks:
            return
        # Dựng chỉ mục từ tài liệu cục bộ khi service khởi động, không tải thêm
        # model embedding hàng trăm MB trên máy demo.
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=40_000,
        )
        self.index = self.vectorizer.fit_transform(item["text"] for item in self.chunks)

    def _retrieve(
        self, question: str, *, allowed_pages: set[int] | None = None, limit: int = 8
    ) -> list[dict]:
        if not self.ready or self.vectorizer is None:
            return []
        query = self.vectorizer.transform([question])
        scores = (self.index @ query.T).toarray().ravel()
        ranked = np.argsort(scores)[::-1]
        selected = []
        for raw_index in ranked:
            score = float(scores[int(raw_index)])
            if score < 0.025:
                break
            item = self.chunks[int(raw_index)]
            if allowed_pages and int(item.get("page", 0)) not in allowed_pages:
                continue
            selected.append({**item, "score": score})
            if len(selected) >= limit:
                break
        return selected

    @staticmethod
    def _patient_excerpt(text: str, max_chars: int = 760) -> str | None:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned or PATIENT_UNSAFE_EXCERPT.search(cleaned):
            return None
        if len(cleaned) <= max_chars:
            return cleaned
        shortened = cleaned[:max_chars]
        sentence_end = max(shortened.rfind(". "), shortened.rfind("; "))
        if sentence_end >= max_chars // 2:
            shortened = shortened[: sentence_end + 1]
        return shortened.rstrip() + "…"

    def guidance(self, disease: str) -> DiseaseGuidance:
        config = DISEASE_GUIDANCE.get(disease)
        if not config or not self.ready:
            return DiseaseGuidance(
                title="Thông tin từ tài liệu y khoa",
                answer=NO_EVIDENCE,
                citations=[],
                has_evidence=False,
            )
        retrieved = self._retrieve(
            config["query"], allowed_pages=config["pages"], limit=12
        )
        citations: list[Citation] = []
        seen_pages: set[int] = set()
        for item in retrieved:
            page = int(item["page"])
            if page in seen_pages:
                continue
            citations.append(Citation(source=item["source"], page=page))
            seen_pages.add(page)
            if len(citations) == 2:
                break
        if not citations:
            return DiseaseGuidance(
                title=config["title"],
                answer=NO_EVIDENCE,
                citations=[],
                has_evidence=False,
            )
        return DiseaseGuidance(
            title=config["title"],
            answer=config["summary"],
            citations=citations,
            has_evidence=True,
        )

    def answer(self, question: str) -> tuple[str, list[Citation], bool]:
        if MEDICATION_PATTERN.search(question):
            return REFUSAL, [], True
        selected = self._retrieve(question, limit=12)
        if not selected:
            return NO_EVIDENCE, [], False
        excerpts: list[str] = []
        citations: list[Citation] = []
        for item in selected:
            excerpt = self._patient_excerpt(item["text"])
            if not excerpt:
                continue
            excerpts.append(excerpt)
            citations.append(Citation(source=item["source"], page=int(item["page"])))
            if len(excerpts) == 2:
                break
        if not excerpts:
            return NO_EVIDENCE, [], False
        return "\n\n".join(excerpts), citations, False
