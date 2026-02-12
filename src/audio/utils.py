import numpy as np
import logging

def calculate_rms_volume(pcm_data: bytes, sensitivity: float = 8000.0) -> float:
    """
    Calculates the Root Mean Square (RMS) volume of 16-bit PCM audio data.
    
    Args:
        pcm_data: Raw 16-bit PCM audio bytes.
        sensitivity: Divisor for normalization. Lower value = higher sensitivity.
                     Default 8000.0 provides good sensitivity for speech.
                     
    Returns:
        float: Normalized volume between 0.0 and 1.0.
    """
    try:
        if not pcm_data:
            return 0.0
            
        # Ensure even number of bytes for 16-bit samples
        if len(pcm_data) % 2 != 0:
            return 0.0
            
        samples = np.frombuffer(pcm_data, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
            
        # Calculate RMS
        rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
        
        # Normalize and clamp
        volume = min(1.0, rms / sensitivity)
        return volume
        
    except Exception as e:
        logging.error(f"[Audio Utils] Error calculating RMS: {e}")
        return 0.0
