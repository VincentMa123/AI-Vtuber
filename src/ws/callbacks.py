import base64
import logging
import core.utils as utils
from ws.manager import ws_manager

async def broadcast_browser_update(data):

    msg_type = data.get("type")
    
    if msg_type == "audio":
        audio_base64 = data.get("data")
        volume = 0.0
        
        if audio_base64:
            try:
                audio_bytes = base64.b64decode(audio_base64)
                
                # Simple header skip if WAV
                header_offset = 0
                if len(audio_bytes) > 12 and audio_bytes[0:4] == b'RIFF' and audio_bytes[8:12] == b'WAVE':
                    # Find 'data' chunk by scanning for its marker
                    offset = 12
                    while offset + 8 <= len(audio_bytes):
                        chunk_id = audio_bytes[offset:offset+4]
                        chunk_size = int.from_bytes(audio_bytes[offset+4:offset+8], 'little')
                        if chunk_id == b'data':
                            header_offset = offset + 8
                            break
                        offset += 8 + chunk_size
                    else:
                        header_offset = 44  # Fallback to common size
                
                pcm_data = audio_bytes[header_offset:]                
                if len(pcm_data) > 0:
                    volume = utils.calculate_rms_volume(pcm_data)
            except Exception as e:
                logging.error(f"[Audio Volume] Error: {e}")

        await ws_manager.broadcast_audio_chunk(
            audio_base64=audio_base64,
            volume=volume,
            is_complete=False
        )
        
    elif msg_type == "status":
        await ws_manager.broadcast_vision_status(data.get("content"))
        
    elif msg_type == "stop":
        await ws_manager.broadcast_stop_signal()
        
    elif msg_type == "text":
        await ws_manager.broadcast_text_chunk(
        chunk=data.get("content"),
        is_complete=True
        )
         
    else:
        await ws_manager.broadcast(data)
