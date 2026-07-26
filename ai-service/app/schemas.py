from pydantic import BaseModel, Field


class RankedPrediction(BaseModel):
    label: str
    probability: float = Field(ge=0, le=1)


class PredictionResponse(BaseModel):
    disease: str
    confidence: float
    top3: list[RankedPrediction]
    gradcam_image: str
    model_version: str
    uncertain: bool
    disclaimer: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class Citation(BaseModel):
    source: str
    page: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool = False
    disclaimer: str

