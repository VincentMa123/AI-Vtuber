from pydantic import BaseModel
from typing import Optional

class HeartbeatRequest(BaseModel):
    image_base64: Optional[str] = None
    timestamp: float = 0.0
    use_native_capture: bool = False

class HeartbeatResponse(BaseModel):
    processed: bool
    action: str  # "ignore" or "react"
    reaction_text: Optional[str] = None
    audio_base64: Optional[str] = None
    category: Optional[str] = None
    debug_info: Optional[str] = None
