import base64
from typing import List
import logging
import core.config as config
import core.state as state
import core.utils as utils
from chat.emotions import detect_emotion
from ws.manager import ws_manager
import asyncio
from twitch.bot import get_twitch_bot

EMOTION_CONTEXT = {
    "happy": "The viewer seems happy and positive! Match their energy with enthusiasm.",
    "sad": "The viewer seems sad or down. Be gentle, supportive, and comforting.",
    "angry": "The viewer seems frustrated or upset. Stay calm, be understanding, and try to help.",
    "excited": "The viewer is super excited! Match their hype and be energetic!",
    "neutral": ""
}

async def handle_aggregated_response(
    message: str, 
    llm_providers: dict,
    tts_manager,
    use_streaming: bool = True,
) -> None:

    # Use acquire_speech_slot to ensure exclusive access during response
    async with state.acquire_speech_slot("chat"):
        try:
            logging.info(f"[Response Handler] Generating response for: {message[:100]}...")
            
            user_emotion = detect_emotion(message)
            logging.info(f"[Response Handler] User emotion detected: {user_emotion}")
            
            emotion_instruction = EMOTION_CONTEXT.get(user_emotion, "")
            enhanced_message = message
            if emotion_instruction:
                enhanced_message = f"[EMOTION CONTEXT: {emotion_instruction}]\n\nUser message: {message}"
            
            llm_provider = state.llm_provider
            provider = llm_providers.get(llm_provider)
            
            if not provider:
                logging.error(f"[Response Handler] Error: Invalid LLM provider: {llm_provider}")
                return

            if use_streaming:
                try:
                    await handle_streaming_response(
                        enhanced_message=enhanced_message,
                        provider=provider,
                        tts_manager=tts_manager,
                        user_emotion=user_emotion
                    )
                    return
                except Exception as e:
                    logging.warning(f"[Response Handler] Streaming failed: {e}")
            
        except Exception as e:
            logging.error(f"[Response Handler] Error: {e}", exc_info=True)


async def handle_streaming_response(
    enhanced_message: str,
    provider,
    tts_manager,
    user_emotion: str
) -> None:

    import time
    start_time = time.time()
    logging.info("[Response Handler] Starting streaming response...")
    
    # Broadcast stream start
    await ws_manager.broadcast_stream_start(user_emotion)
    
    accumulated_text = ""
    full_text = ""
    
    try:
        # Get chat history for context
        history = state.get_history()
        
        # Store user message in history
        state.add_to_history("user", enhanced_message)
        
        text_stream = provider.generate_stream(enhanced_message, history, None)
        
        text_queue = asyncio.Queue()
        min_tts_chunk = 1  
        
        async def collect_text():

            nonlocal accumulated_text, full_text
            async for token in text_stream:
                accumulated_text += token
                full_text += token
                
                # Broadcast text chunk immediately
                await ws_manager.broadcast_text_chunk(token, is_complete=False)
                
                # Queue text for TTS when we have enough
                if len(accumulated_text) >= min_tts_chunk:
                    await text_queue.put(accumulated_text)
                    accumulated_text = ""
            
            # Queue any remaining text
            if accumulated_text:
                await text_queue.put(accumulated_text)
            
            # Signal completion
            await text_queue.put(None)
        
        async def text_stream_for_tts():

            while True:
                chunk = await text_queue.get()
                if chunk is None:
                    break
                yield chunk
        
        # Start text collection
        collect_task = asyncio.create_task(collect_text())
        
        # Start TTS streaming
        audio_stream = tts_manager.generate_audio_stream(
            text_stream_for_tts(),
        )
        
        # Stream audio chunks as they're ready
        async for audio_chunk_base64 in audio_stream:
            if audio_chunk_base64:
                await ws_manager.broadcast_audio_chunk(audio_chunk_base64, is_complete=False)
        
        # Wait for text collection to complete
        await collect_task
        
        # Broadcast final chunks
        await ws_manager.broadcast_text_chunk("", is_complete=True)
        await ws_manager.broadcast_audio_chunk("", is_complete=True)
        await ws_manager.broadcast_stream_end()
        
        # Wait for frontend to signal audio playback is complete
        await state.wait_for_audio_complete(timeout=10.0)
        
        # Store AI response in history
        if full_text:
            state.add_to_history("assistant", full_text)
        
        # Send to Twitch chat if bot is available
        if config.TWITCH_ENABLED and full_text:
            bot = get_twitch_bot()
            if bot:
                await bot.send_response(full_text)
        
        logging.info(f"[Response Handler] Streaming complete: {len(full_text)} chars")
        logging.info(f"[Response Handler] Streaming took {time.time() - start_time:.2f}s")
        
    except Exception as e:
        logging.error(f"[Response Handler] Streaming error: {e}", exc_info=True)
        await ws_manager.broadcast_stream_end()
        raise
