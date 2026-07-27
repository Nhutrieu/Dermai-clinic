import io
import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from .config import settings
from .model import DISCLAIMER, load_bundle, predict
from .rag import RagStore
from .schemas import ChatRequest, ChatResponse, PredictionResponse

state: dict = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state["model"] = load_bundle(settings.model_path)
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
async def prediction(image: UploadFile = File(...)):
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
    return predict(state["model"], source)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    answer, citations, refused = state["rag"].answer(request.question)
    return ChatResponse(
        answer=answer, citations=citations, refused=refused, disclaimer=DISCLAIMER
    )


@app.post("/public-chat", response_model=ChatResponse)
async def public_chat(request: ChatRequest):
    if not settings.gemini_api_key:
        raise HTTPException(503, "Gemini chưa được cấu hình API key.")
    system_instruction = (
        "Bạn là trợ lý tư vấn thông tin chăm sóc da chung của DermAI Clinic. "
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
    async with httpx.AsyncClient(timeout=25.0) as client:
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

    if isinstance(last_error, httpx.HTTPStatusError):
        raise HTTPException(502, f"Gemini error {last_error.response.status_code}: {last_error.response.text[:200]}")
    raise HTTPException(503, "Không thể kết nối Gemini.")
