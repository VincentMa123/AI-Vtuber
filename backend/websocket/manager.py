"""
WebSocket Connection Manager
Manages WebSocket connections and broadcasts messages to connected clients
"""

from fastapi import WebSocket
from typing import List, Dict, Any
import json
import asyncio


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WebSocket] New connection. Total: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WebSocket] Connection closed. Total: {len(self.active_connections)}")
    
    async def send_personal(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WebSocket] Error sending to client: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients"""
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] Error broadcasting to client: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_chat_message(self, username: str, message: str, user_id: str = None):
        """Broadcast a chat message from Twitch"""
        await self.broadcast({
            "type": "chat_message",
            "username": username,
            "message": message,
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    async def broadcast_ai_response(self, response: str, audio_base64: str = None, emotion: str = "neutral"):
        """Broadcast Lumina's AI response with emotion"""
        await self.broadcast({
            "type": "ai_response",
            "username": "Lumina",
            "message": response,
            "audio_base64": audio_base64,
            "emotion": emotion,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    async def broadcast_status(self, status: Dict[str, Any]):
        """Broadcast aggregation status update"""
        await self.broadcast({
            "type": "status_update",
            "data": status
        })
    
    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()
