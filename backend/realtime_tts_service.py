import io
import wave
import base64
import numpy as np
import threading
from typing import Optional
import os

# Configure FFmpeg path for pydub (used by RealtimeTTS SystemEngine)
winget_ffmpeg_path = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'Microsoft', 'WinGet', 'Packages',
    'Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe',
    'ffmpeg-8.0.1-full_build', 'bin'
)

if os.path.exists(os.path.join(winget_ffmpeg_path, 'ffmpeg.exe')):
    # Add to PATH for this process
    os.environ['PATH'] = winget_ffmpeg_path + os.pathsep + os.environ.get('PATH', '')

try:
    from RealtimeTTS import TextToAudioStream, SystemEngine
except ImportError as e:
    TextToAudioStream = None
    SystemEngine = None
    print(f"RealtimeTTS import failed: {e}")
except Exception as e:
    TextToAudioStream = None
    SystemEngine = None
    print(f"RealtimeTTS import failed with unexpected error: {e}")

class RealtimeTTSWrapper:
    def __init__(self, engine_name="system"):
        if not TextToAudioStream:
            raise ImportError("RealtimeTTS library is not available")
            
        self.audio_buffer = []
        self.lock = threading.Lock()
        
        # Initialize Engine based on config (currently defaulting to SystemEngine)
        # Expansion: Add CoquiEngine, AzureEngine, etc. based on engine_name
        print(f"Initializing RealtimeTTS with {engine_name} engine...")
        self.engine = SystemEngine() 
        
        # Initialize Stream
        self.stream = TextToAudioStream(self.engine)
        
    def _on_audio_chunk(self, chunk):
        """Callback to receive audio chunks."""
        # Chunk is usually bytes (PCM 16-bit) or numpy array?
        # RealtimeTTS on_audio_chunk typically returns bytes
        with self.lock:
            self.audio_buffer.append(chunk)

    def generate_audio(self, text: str) -> Optional[bytes]:
        """
        Generates audio for the given text and returns WAV bytes.
        """
        try:
            with self.lock:
                self.audio_buffer = []
            
            # Feed text to the stream
            self.stream.feed(text)
            
            # Play in 'muted' mode to capture chunks without local playback
            # We pass our callback to capture the raw audio data
            self.stream.play(
                muted=True, 
                on_audio_chunk=self._on_audio_chunk
            )
            
            # Combine all chunks
            with self.lock:
                if not self.audio_buffer:
                    print("No audio chunks generated")
                    return None
                
                full_audio_data = b''.join(self.audio_buffer)
            
            # Convert raw PCM to WAV
            channel_count = 1
            sample_width = 2  # 16-bit audio
            # Get sample rate from engine if possible, otherwise default to 22050/24000
            # SystemEngine usually defaults to system rate, let's assume 22050 or try to fetch
            sample_rate = 22050
            if hasattr(self.engine, 'get_stream_info'):
                 info = self.engine.get_stream_info()
                 if hasattr(info, 'rate'):
                     sample_rate = int(info.rate)

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(channel_count)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(full_audio_data)
            
            return wav_buffer.getvalue()
            
        except Exception as e:
            print(f"RealtimeTTS generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None
