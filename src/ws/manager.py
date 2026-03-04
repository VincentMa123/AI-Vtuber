from fastapi import WebSocket
from typing import List, Dict, Any
import asyncio
import logging


def _timestamp() -> float:
    return asyncio.get_running_loop().time()

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.shutting_down = False  # Add shutdown flag
        
    async def connect(self, websocket: WebSocket):

        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"[WebSocket] New connection. Total: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"[WebSocket] Connection closed. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        # Don't broadcast if we're shutting down
        if self.shutting_down:
            return
        
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logging.debug(f"[WebSocket] Error broadcasting to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_chat_message(self, username: str, message: str, user_id: str = None):

        await self.broadcast({
            "type": "chat_message",
            "username": username,
            "message": message,
            "user_id": user_id,
            "timestamp": _timestamp()
        })
    
    async def broadcast_ai_response(self, response: str, audio_base64: str = None, emotion: str = "neutral"):

        audio_len = len(audio_base64) if audio_base64 else 0
        logging.info(f"[WebSocket] Broadcasting AI response with audio: {audio_len} chars, emotion: {emotion}")
        
        await self.broadcast({
            "type": "ai_response",
            "username": "Lumina",
            "message": response,
            "audio_base64": audio_base64,
            "emotion": emotion,
            "timestamp": _timestamp()
        })
    
    async def broadcast_text_chunk(self, chunk: str, is_complete: bool = False):

        await self.broadcast({
            "type": "text_chunk",
            "chunk": chunk,
            "complete": is_complete,
            "timestamp": _timestamp()
        })
    
    async def broadcast_audio_chunk(self, audio_base64: str = None, volume: float = 0.0, is_complete: bool = False):

        await self.broadcast({
            "type": "audio_chunk",
            "audio_base64": audio_base64,
            "volume": volume,
            "complete": is_complete,
            "timestamp": _timestamp()
        })

    async def broadcast_vision_status(self, content: str):
        await self.broadcast({
            "type": "vision_status",
            "content": content
        })

    async def broadcast_stop_signal(self):
        await self.broadcast({
            "type": "audio_chunk",
            "complete": True
        })
    
    async def broadcast_stream_start(self, emotion: str = "neutral"):

        await self.broadcast({
            "type": "stream_start",
            "emotion": emotion,
            "timestamp": _timestamp()
        })
    
    async def broadcast_stream_end(self):

        await self.broadcast({
            "type": "stream_end",
            "timestamp": _timestamp()
        })
    
    async def close_all(self):
        """Close all active WebSocket connections gracefully during shutdown."""
        self.shutting_down = True  # Signal shutdown first
        connections_to_close = self.active_connections.copy()
        for connection in connections_to_close:
            try:
                await connection.close()
            except Exception as e:
                logging.debug(f"[WebSocket] Error closing connection: {e}")
            self.disconnect(connection)

ws_manager = WebSocketManager()
