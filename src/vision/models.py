from pydantic import BaseModel
from typing import Optional, Union, List

class HeartbeatRequest(BaseModel):
    image_base64: Optional[Union[str, List[str]]] = None
    timestamp: float = 0.0
    use_native_capture: bool = False
