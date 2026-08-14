from pydantic import BaseModel, Field


class RankedPrediction(BaseModel):
    label: str
    probability: float = Field(ge=0, le=1)


class Citation(BaseModel):
    source: str
    page: int


class DiseaseGuidance(BaseModel):
    title: str
    answer: str
    citations: list[Citation]
    has_evidence: bool


class PredictionResponse(BaseModel):
    disease: str
    confidence: float
    top3: list[RankedPrediction]
    gradcam_image: str
    model_version: str
    uncertain: bool
    disclaimer: str
    guidance: DiseaseGuidance | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool = False
    disclaimer: str


class SupportChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class SupportChatResponse(BaseModel):
    answer: str
    category: str
    requires_handoff: bool
    handoff_summary: str
    intent_confidence: float = Field(ge=0, le=1)
    needs_clarification: bool = False
    doctor_name: str | None = None
    requested_date: str | None = None
    requested_time: str | None = None
    automated: bool = True
