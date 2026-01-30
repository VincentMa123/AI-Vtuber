'use client';

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import { useDraggable } from '../hooks/useDraggable';
import { useAudioPlayer, EmotionType } from '../hooks/useAudioPlayer';
import { useChatWebSocket, WebSocketMessage } from '../lib/chatWebSocket';

const Avatar = dynamic(() => import('../components/Avatar'), {
  ssr: false,
  loading: () => <div className="text-9xl animate-pulse">🌟</div>
});

const ScreenCapture = dynamic(() => import('../components/ScreenCapture'), { ssr: false });

const VTuberPage = () => {
  const [emotion, setEmotion] = useState<EmotionType>('neutral');

  // Custom hooks
  const { isSpeaking, audioEnabled, enableAudio, playAudio, playAudioChunk, getCurrentVolume } = useAudioPlayer();
  const { position: avatarPosition, isDragging, handleMouseDown } = useDraggable({
    initialPosition: { x: 0, y: 0 }
  });

  // Handle incoming WebSocket messages
  const handleMessage = (msg: WebSocketMessage) => {
    if (msg.type === 'ai_response') {
      console.log('[VTuber] AI response received (non-streaming)');

      if (msg.emotion) {
        setEmotion(msg.emotion);
      }

      if (msg.audio_base64) {
        playAudio(msg.audio_base64, () => {
          setEmotion('neutral');
        });
      }
    } else if (msg.type === 'stream_start') {
      console.log('[VTuber] Streaming started');
      if (msg.emotion) {
        setEmotion(msg.emotion);
      }
    } else if (msg.type === 'text_chunk') {
      // Text chunks are received but we don't need to display them in this UI
      // They're mainly for logging/debugging
      if (msg.chunk) {
        console.log('[VTuber] Text chunk:', msg.chunk);
      }
      if (msg.complete) {
        console.log('[VTuber] Text streaming complete');
      }
    } else if (msg.type === 'audio_chunk') {
      // console.log('[VTuber] Audio chunk received'); // Disabled for performance
      if (msg.audio_base64 || msg.complete) {
        playAudioChunk(msg.audio_base64 || '', msg.complete ?? false, msg.timestamp ?? 0);
        if (msg.complete) {
          // Reset emotion when streaming completes
          setTimeout(() => setEmotion('neutral'), 1000);
        }
      }
    } else if (msg.type === 'stream_end') {
      console.log('[VTuber] Streaming ended');
      setTimeout(() => setEmotion('neutral'), 1000);
    } else if (msg.type === 'vision_status') {
      console.log(`[Vision Status] ${msg.data?.content || msg.content}`);
    }
  };

  const { isConnected, sendMessage } = useChatWebSocket(handleMessage);

  // Handle Vision Reactions
  const handleVisionReaction = (text: string, audioBase64: string, category: string) => {
    console.log(`[Vision] Reaction: ${text} (${category})`);

    // Set emotion (default to excited for vision triggers)
    setEmotion('excited');

    // Play Audio
    playAudio(audioBase64, () => {
      setEmotion('neutral');
    });
  };

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#00FF00]">
      {/* Screen Capture (Hidden/Background) */}
      <ScreenCapture
        onReaction={handleVisionReaction}
        onAudioChunk={(chunk, isComplete) => {
          // If chunk provided, play it
          if (chunk || isComplete) {
            setEmotion('excited');
            playAudioChunk(chunk, isComplete);
            if (isComplete) {
              setTimeout(() => setEmotion('neutral'), 1000);
            }
          }
        }}
        sendFrame={sendMessage}
        intervalSeconds={10}
      />

      {/* Audio Enable Overlay */}
      {!audioEnabled && (
        <div
          className="absolute inset-0 z-[100] flex items-center justify-center bg-black/50 cursor-pointer backdrop-blur-sm"
          onClick={enableAudio}
        >
          <div className="bg-white p-6 rounded-xl shadow-2xl text-center transform hover:scale-105 transition-transform">
            <span className="text-4xl mb-4 block">🔊</span>
            <p className="text-xl font-bold mb-2 text-gray-800">Click to Enable Audio</p>
            <p className="text-gray-500 text-sm">Required for auto-playing voice</p>
          </div>
        </div>
      )}

      {/* Connection Status */}
      {!isConnected && (
        <div className="absolute top-4 left-4 bg-red-500 text-white px-2 py-1 rounded text-xs z-50">
          Disconnected
        </div>
      )}

      {/* Draggable Avatar */}
      <div className="absolute inset-0 flex items-end justify-center pb-0 pointer-events-none">
        <div
          className="w-[50vw] h-[85vh] max-w-[800px] max-h-[1000px] min-w-[300px] min-h-[400px] relative pointer-events-auto"
          style={{
            transform: `translate(${avatarPosition.x}px, ${avatarPosition.y}px)`,
            cursor: isDragging ? 'grabbing' : 'grab',
            userSelect: isDragging ? 'none' : 'auto',
          } as React.CSSProperties}
          onMouseDown={handleMouseDown}
        >
          <Avatar emotion={emotion} getCurrentVolume={getCurrentVolume} />
        </div>
      </div>

      {/* Status Indicator */}
      <div className={`fixed bottom-6 right-6 px-4 py-2 rounded-full ${isSpeaking ? 'bg-green-500/80 animate-pulse' : 'bg-gray-700/80'} text-white text-sm font-medium z-20`}>
        {isSpeaking ? `🎤 ${emotion}` : '💤 Idle'}
      </div>
    </div>
  );
};

export default VTuberPage;