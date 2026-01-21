"""
Response Handler for Chat Aggregation
Contains the callback logic for handling aggregated chat messages and generating AI responses.
"""

import base64
from typing import List
import config
import state
import utils
from chat.emotions import detect_emotion
from websocket.manager import ws_manager


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
    tts_providers: dict,
    RealtimeTTSProvider
) -> None:
    """
    Generate AI response for aggregated chat messages.
    
    Args:
        message: The aggregated/selected message to respond to
        top_messages: List of top messages from the batch
        llm_providers: Dictionary of LLM provider instances
        tts_providers: Dictionary of TTS provider instances
        RealtimeTTSProvider: RealtimeTTS provider class for lazy initialization
    """
    try:
        print(f"[Response Handler] Generating response for: {message[:100]}...")
        
        # Detect emotion from USER INPUT
        user_emotion = detect_emotion(message)
        print(f"[Response Handler] User emotion detected: {user_emotion}")
        
        # Add emotion context to the message for the LLM
        emotion_instruction = EMOTION_CONTEXT.get(user_emotion, "")
        enhanced_message = message
        if emotion_instruction:
            enhanced_message = f"[EMOTION CONTEXT: {emotion_instruction}]\n\nUser message: {message}"
        
        # Get LLM provider
        llm_provider = state.llm_provider
        provider = llm_providers.get(llm_provider)
        
        if not provider:
            print(f"[Response Handler] Error: Invalid LLM provider: {llm_provider}")
            return
        
        # Generate response with emotion context
        output_text = await provider.generate(enhanced_message, [], None)
        
        if output_text:
            print(f"[Response Handler] Generated response: {output_text[:100]}...")
            
            # Generate Audio for TTS
            audio_base64 = await _generate_tts_audio(
                output_text, 
                tts_providers, 
                RealtimeTTSProvider
            )

            # Use the USER's detected emotion for avatar animation
            print(f"[Response Handler] Using emotion for avatar: {user_emotion}")

            # Broadcast via WebSocket (with audio and emotion!)
            await ws_manager.broadcast_ai_response(output_text, audio_base64, user_emotion)
            
            # Send to Twitch chat if bot is available
            if config.TWITCH_ENABLED:
                from twitch.bot import get_twitch_bot
                bot = get_twitch_bot()
                if bot:
                    await bot.send_response(output_text)
        else:
            print("[Response Handler] No response generated")
            
    except Exception as e:
        print(f"[Response Handler] Error: {e}")
        import traceback
        traceback.print_exc()


async def _generate_tts_audio(
    text: str,
    tts_providers: dict,
    RealtimeTTSProvider
) -> str | None:
    """
    Generate TTS audio for the given text.
    
    Returns:
        Base64 encoded audio string, or None if generation failed
    """
    try:
        clean_text = utils.clean_text_for_tts(text)
        if not clean_text:
            return None
            
        if config.TTS_PROVIDER == "elevenlabs":
            audio_bytes = await tts_providers["elevenlabs"].generate_audio(clean_text)
            if audio_bytes:
                return base64.b64encode(audio_bytes).decode('utf-8')
                
        elif config.TTS_PROVIDER == "realtimetts":
            # Lazy init RealtimeTTS if needed
            if tts_providers["realtimetts"] is None:
                tts_providers["realtimetts"] = RealtimeTTSProvider(config.REALTIMETTS_ENGINE)
            
            if tts_providers["realtimetts"]:
                audio_bytes = await tts_providers["realtimetts"].generate_audio(clean_text)
                if audio_bytes:
                    return base64.b64encode(audio_bytes).decode('utf-8')
                    
    except Exception as e:
        print(f"[Response Handler] TTS Error: {e}")
    
    return None
