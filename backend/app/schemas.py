from typing import Optional

from pydantic import BaseModel


class CreateAgentRequest(BaseModel):
    name: str
    description: str
    instruction: str = "You are a helpful assistant."
    language: str = "en-US"
    model: str = "mistral-small"
    temperature: float = 0.5
    business_type: str = "Fashion"
    use_voice_to_voice: bool = True
    voice_gender: str = "female"
    business_info: dict = {}
    catalog_items: list[dict] = []
    faqs: list[dict] = []
    doctors: list[dict] = []


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str


class TtsRequest(BaseModel):
    text: str
    voice_gender: str = "female"


class UpdateAgentRequest(BaseModel):
    name: str
    description: str
    instruction: str
    language: str
    temperature: float
    business_type: str = "Fashion"
    use_voice_to_voice: bool = True
    voice_gender: str = "female"
    business_info: dict = {}
    catalog_items: list[dict] = []
    faqs: list[dict] = []
    doctors: list[dict] = []


class ProcessedKnowledgeResponse(BaseModel):
    business_info: dict
    catalog_items: list[dict]
    faqs: list[dict]
    doctors: list[dict]
