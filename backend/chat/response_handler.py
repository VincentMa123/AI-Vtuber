"""
Response Handler for Chat Aggregation
Contains the callback logic for handling aggregated chat messages and generating AI responses.
"""

import base64
from typing import List
import logging
import core.config as config
import core.state as state
import core.utils as utils
from chat.emotions import detect_emotion
from websocket.manager import ws_manager
import asyncio


# Emotion context mapping for LLM
EMOTION_CONTEXT = {
    "happy": "The viewer seems happy and positive! Match their energy with enthusiasm.",
    "sad": "The viewer seems sad or down. Be gentle, supportive, and comforting.",
    "angry": "The viewer seems frustrated or upset. Stay calm, be understanding, and try to help.",
    "excited": "The viewer is super excited! Match their hype and be energetic!",
    "neutral": ""
}


async def handle_aggregated_response(
    message: str, 
    top_messages: list,
    llm_providers: dict,
    tts_manager,
    use_streaming: bool = True,
) -> None:
    """
    Generate AI response for aggregated chat messages.
    
    Args:
        message: The aggregated/selected message to respond to
        top_messages: List of top messages from the batch
        llm_providers: Dictionary of LLM provider instances
        tts_manager: TTSManager instance for audio generation
    """
    try:
        logging.info(f"[Response Handler] Generating response for: {message[:100]}...")
        
        # Detect emotion from USER INPUT
        user_emotion = detect_emotion(message)
        logging.info(f"[Response Handler] User emotion detected: {user_emotion}")
        
        # Add emotion context to the message for the LLM
        emotion_instruction = EMOTION_CONTEXT.get(user_emotion, "")
        enhanced_message = message
        if emotion_instruction:
            enhanced_message = f"[EMOTION CONTEXT: {emotion_instruction}]\n\nUser message: {message}"
        
        # Get LLM provider
        llm_provider = state.llm_provider
        provider = llm_providers.get(llm_provider)
        
        if not provider:
            logging.error(f"[Response Handler] Error: Invalid LLM provider: {llm_provider}")
            return
        
        # Use streaming if enabled and provider supports it
        if use_streaming:
            try:
                await handle_streaming_response(
                    enhanced_message=enhanced_message,
                    llm_provider=llm_provider,
                    provider=provider,
                    llm_providers=llm_providers,
                    tts_manager=tts_manager,
                    user_emotion=user_emotion
                )
                return
            except Exception as e:
                logging.warning(f"[Response Handler] Streaming failed: {e}, falling back to non-streaming")
        
        # Non-streaming fallback
        output_text = await provider.generate(enhanced_message, [], None)
        
        # Fallback logic if primary provider fails
        if not output_text:
            logging.warning(f"[Response Handler] Primary provider '{llm_provider}' failed, trying fallbacks...")
            
            # 1. Fallback: DeepSeek (Preference as per user request)
            if llm_provider != "deepseek":
                logging.info("[Response Handler] Fallback: Trying DeepSeek...")
                output_text = await llm_providers["deepseek"].generate(enhanced_message, [], None)
                
            # 2. Fallback: OpenRouter
            if not output_text and llm_provider != "openrouter":
                logging.info("[Response Handler] Fallback: Trying OpenRouter...")
                output_text = await llm_providers["openrouter"].generate(enhanced_message, [], None)
                
            # 3. Fallback: Remote vLLM
            if not output_text and llm_provider != "remote":
                logging.info("[Response Handler] Fallback: Trying Remote vLLM...")
                output_text = await llm_providers["remote"].generate(enhanced_message, [], None)
            
            # 4. Fallback: Local
            if not output_text and llm_provider != "local":
                logging.info("[Response Handler] Fallback: Trying Local Model...")
                output_text = llm_providers["local"].generate(enhanced_message, [], None)
        
        if output_text:
            logging.info(f"[Response Handler] Generated response: {output_text[:100]}...")
            
            # Generate Audio for TTS via Manager
            audio_base64 = await tts_manager.generate_audio(output_text)

            # Use the USER's detected emotion for avatar animation
            logging.info(f"[Response Handler] Using emotion for avatar: {user_emotion}")

            # Broadcast via WebSocket (with audio and emotion!)
            await ws_manager.broadcast_ai_response(output_text, audio_base64, user_emotion)
            
            # Send to Twitch chat if bot is available
            if config.TWITCH_ENABLED:
                from twitch.bot import get_twitch_bot
                bot = get_twitch_bot()
                if bot:
                    await bot.send_response(output_text)
        else:
            logging.warning("[Response Handler] No response generated")
            
    except Exception as e:
        logging.error(f"[Response Handler] Error: {e}", exc_info=True)


async def handle_streaming_response(
    enhanced_message: str,
    llm_provider: str,
    provider,
    llm_providers: dict,
    tts_manager,
    user_emotion: str
) -> None:
    """
    Handle streaming response: LLM tokens -> TTS audio chunks -> WebSocket
    """
    logging.info("[Response Handler] Starting streaming response...")
    
    # Broadcast stream start
    await ws_manager.broadcast_stream_start(user_emotion)
    
    accumulated_text = ""
    full_text = ""
    
    try:
        # Get streaming generator from provider
        text_stream = provider.generate_stream(enhanced_message, [], None)
        
        # Create a queue to buffer text for TTS
        text_queue = asyncio.Queue()
        min_tts_chunk = 15  # Minimum characters before starting TTS
        
        async def collect_text():
            """Collect text tokens and queue them for TTS"""
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
            """Generator for TTS that yields text chunks"""
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
            min_chunk_size=min_tts_chunk
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
        
        # Clean text for Twitch
        clean_text = utils.clean_text_for_tts(full_text)
        
        # Send to Twitch chat if bot is available
        if config.TWITCH_ENABLED and clean_text:
            from twitch.bot import get_twitch_bot
            bot = get_twitch_bot()
            if bot:
                await bot.send_response(clean_text)
        
        logging.info(f"[Response Handler] Streaming complete: {len(full_text)} chars")
        
    except Exception as e:
        logging.error(f"[Response Handler] Streaming error: {e}", exc_info=True)
        await ws_manager.broadcast_stream_end()
        raise
