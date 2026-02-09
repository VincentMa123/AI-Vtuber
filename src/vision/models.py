from pydantic import BaseModel
from typing import Optional

class HeartbeatRequest(BaseModel):
    image_base64: Optional[str] = None
    timestamp: float = 0.0
    use_native_capture: bool = False


