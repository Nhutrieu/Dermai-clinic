import json
from pathlib import Path
from app.rag import RagStore


def test_refuses_prescription():
    answer, citations, refused = RagStore(Path("missing")).answer("Kê đơn thuốc gì và liều bao nhiêu?")
    assert refused is True
    assert citations == []
    assert "không thể kê đơn" in answer


def test_no_evidence_fails_closed():
    answer, citations, refused = RagStore(Path("missing")).answer("Bệnh chàm là gì?")
    assert refused is False
    assert citations == []
    assert "chưa cung cấp đủ" in answer


def test_disease_guidance_retrieves_cited_safe_excerpt(tmp_path):
    chunks = [
        {
            "source": "huong-dan-da-lieu.pdf",
            "page": 27,
            "text": "TRỨNG CÁ (Acne): nguyên tắc điều trị gồm kiểm soát tiết chất bã, dày sừng và viêm.",
        },
        {
            "source": "huong-dan-da-lieu.pdf",
            "page": 28,
            "text": "Điều trị trứng cá được lựa chọn theo mức độ tổn thương của từng người bệnh.",
        },
        {
            "source": "huong-dan-da-lieu.pdf",
            "page": 28,
            "text": "Điều trị bằng thuốc và liều cụ thể phải do bác sĩ quyết định.",
        },
    ]
    (tmp_path / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
    )
    store = RagStore(tmp_path)
    store.load()

    result = store.guidance("Acne")

    assert result.has_evidence is True
    assert result.citations[0].source == "huong-dan-da-lieu.pdf"
    assert result.citations[0].page in {27, 28}
    assert "mg" not in result.answer.lower()
    assert "liều" not in result.answer.lower()


def test_unknown_disease_guidance_fails_closed(tmp_path):
    store = RagStore(tmp_path)

    result = store.guidance("Unknown")

    assert result.has_evidence is False
    assert result.citations == []
