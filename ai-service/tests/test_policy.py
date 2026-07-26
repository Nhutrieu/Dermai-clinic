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

