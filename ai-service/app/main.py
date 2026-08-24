import io
import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from .config import settings
from .image_quality import assess_image_quality
from .model import DISCLAIMER, OutOfScopeImageError, load_bundle, predict
from .rag import NO_EVIDENCE, RagStore
from .schemas import ChatRequest, ChatResponse, PredictionResponse, SupportChatRequest, SupportChatResponse
from .support_assistant import SupportDecision, classify_support_request, polish_safe_answer, rag_disease_key

state: dict = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state["model"] = load_bundle(settings.model_path, settings.ood_profile_path)
    store = RagStore(settings.rag_index_path)
    store.load()
    state["rag"] = store
    yield
    state.clear()


app = FastAPI(
    title="DermAI Clinical Decision Support API",
    version="1.0.0",
    description="AI hỗ trợ tham khảo; không thay thế bác sĩ và không kê đơn.",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {
        "status": "up",
        "modelReady": state.get("model") is not None,
        "ragReady": bool(state.get("rag") and state["rag"].ready),
    }


@app.post("/predict", response_model=PredictionResponse)
async def prediction(
    image: UploadFile = File(...),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    if x_user_role != "PATIENT":
        raise HTTPException(403, "Chỉ bệnh nhân được sử dụng tính năng kiểm tra da bằng AI.")
    if image.content_type not in settings.allowed_mime:
        raise HTTPException(415, "Chỉ chấp nhận JPEG, PNG hoặc WebP.")
    content = await image.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Ảnh vượt quá giới hạn 10 MB.")
    if state.get("model") is None:
        raise HTTPException(503, "Mô hình chưa được nạp; không tạo kết quả giả.")
    try:
        source = Image.open(io.BytesIO(content))
        source.verify()
        source = Image.open(io.BytesIO(content))
    except (UnidentifiedImageError, OSError):
        raise HTTPException(422, "Tệp không phải ảnh hợp lệ.") from None
    quality = assess_image_quality(source)
    if not quality.accepted:
        raise HTTPException(422, quality.reason)
    try:
        result = predict(
            state["model"],
            source,
            settings.confidence_threshold,
            settings.confidence_margin_threshold,
            settings.normalized_entropy_threshold,
        )
    except OutOfScopeImageError as error:
        raise HTTPException(422, str(error)) from None
    rag = state.get("rag")
    if rag:
        result["guidance"] = rag.guidance(result["disease"])
    return result


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    answer, citations, refused = state["rag"].answer(request.question)
    return ChatResponse(
        answer=answer, citations=citations, refused=refused, disclaimer=DISCLAIMER
    )


@app.post("/public-chat", response_model=ChatResponse)
async def public_chat(request: ChatRequest):
    if not settings.gemini_api_key:
        answer, citations, refused = state["rag"].answer(request.question)
        return ChatResponse(answer=answer, citations=citations, refused=refused, disclaimer=DISCLAIMER)
    system_instruction = (
        "Bạn là Trợ lý Derm, hỗ trợ thông tin chăm sóc da. Khi tự giới thiệu, chỉ dùng đúng tên “Trợ lý Derm”; không dùng tên DermAI Clinic và không tự tạo tên gọi khác. "
        "Trả lời bằng tiếng Việt, ngắn gọn, dễ hiểu và có trách nhiệm. "
        "Không chẩn đoán xác định, không kê đơn, không nêu liều thuốc và không khẳng định thay bác sĩ. "
        "Nếu có dấu hiệu cấp cứu, tổn thương lan nhanh, khó thở, sốt cao, đau dữ dội hoặc nhiễm trùng, "
        "hãy khuyên người dùng đi cấp cứu hoặc khám trực tiếp. Với câu hỏi ngoài da liễu, hãy nói rõ phạm vi hỗ trợ. "
        "Mỗi câu trả lời nên gói gọn trong 3 đến 6 ý và luôn kết thúc trọn câu; ưu tiên hỏi thêm thông tin cần thiết khi mô tả còn thiếu."
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": request.question}]}],
        # Gemini 3.x có thể dùng một phần ngân sách output cho reasoning. 500 token
        # dễ làm phần văn bản hiển thị bị cắt giữa câu, nên chừa đủ ngân sách để
        # hoàn tất một câu trả lời tư vấn ngắn.
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }
    candidate_models = [
        settings.gemini_model,
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-pro-latest",
    ]
    seen = set()
    models_to_try = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

    last_error = None
    async with httpx.AsyncClient(timeout=8.0) as client:
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                response = await client.post(url, headers={"x-goog-api-key": settings.gemini_api_key}, json=payload)
                response.raise_for_status()
                data = response.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                answer = "".join(part.get("text", "") for part in parts).strip()
                if answer:
                    return ChatResponse(answer=answer, citations=[], refused=False, disclaimer=DISCLAIMER)
            except httpx.HTTPStatusError as error:
                print(f"GEMINI API ERROR on model {model}: {error.response.status_code} {error.response.text}", flush=True)
                last_error = error
            except httpx.RequestError as error:
                print(f"GEMINI REQUEST ERROR on model {model}: {error}", flush=True)
                last_error = error

    # Gemini có thể quá tải tạm thời; kho tri thức nội bộ vẫn phải phục vụ người dùng.
    answer, citations, refused = state["rag"].answer(request.question)
    return ChatResponse(answer=answer, citations=citations, refused=refused, disclaimer=DISCLAIMER)


@app.post("/support-chat", response_model=SupportChatResponse)
async def support_chat(
    request: SupportChatRequest,
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
):
    if x_user_role != "PATIENT":
        raise HTTPException(403, "Chỉ bệnh nhân được sử dụng trợ lý hỗ trợ.")

    decision = classify_support_request(request.question)
    if decision.category == "DERMATOLOGY_GENERAL":
        rag = state.get("rag")
        disease_key = rag_disease_key(request.question)
        guidance = rag.guidance(disease_key) if rag and rag.ready and disease_key else None
        if guidance and guidance.has_evidence:
            rag_answer, refused = guidance.answer, False
        else:
            rag_answer, _citations, refused = rag.answer(request.question) if rag and rag.ready else (NO_EVIDENCE, [], False)
        if refused or rag_answer == NO_EVIDENCE:
            decision = SupportDecision(
                category="DERMATOLOGY_GENERAL",
                answer="Tài liệu hiện có chưa đủ để tôi trả lời câu hỏi này an toàn. Tôi có thể kết nối bạn với lễ tân để được hỗ trợ đặt lịch cùng bác sĩ da liễu.",
                requires_handoff=True,
                handoff_summary="Câu hỏi da liễu chung chưa có đủ dữ liệu RAG để trả lời; cần hỗ trợ đặt khám.",
            )
            answer = decision.answer
        else:
            answer = f"{rag_answer}\n\nThông tin trên chỉ mang tính tham khảo chung, không thay thế chẩn đoán hoặc chỉ định của bác sĩ."
    elif decision.category == "DERMATOLOGY_VISIT_GUIDE":
        # Preserve the reviewed care-seeking and emergency wording verbatim;
        # generative polishing must not weaken a safety instruction.
        answer = decision.answer
    else:
        answer = await polish_safe_answer(
            decision, settings.gemini_api_key, settings.gemini_model
        )
    return SupportChatResponse(
        answer=answer,
        category=decision.category,
        requires_handoff=decision.requires_handoff,
        handoff_summary=decision.handoff_summary,
        intent_confidence=decision.intent_confidence,
        needs_clarification=decision.needs_clarification,
        doctor_name=decision.doctor_name,
        requested_date=decision.requested_date,
        requested_time=decision.requested_time,
    )
