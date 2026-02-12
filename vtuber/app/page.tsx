'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useAudioPlayer, EmotionType } from '../hooks/useAudioPlayer';
import { useChatWebSocket, WebSocketMessage } from '../lib/chatWebSocket';

const Avatar = dynamic(() => import('../components/Avatar'), {
  ssr: false,
  loading: () => <div className="text-9xl animate-pulse">🌟</div>
});

const ScreenCapture = dynamic(() => import('../components/ScreenCapture'), { ssr: false });

interface ChatEntry {
  id: number;
  username: string;
  message: string;
}

const VTuberPage = () => {
  const [emotion, setEmotion] = useState<EmotionType>('neutral');
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([]);
  const chatIdRef = useRef(0);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const sendMessageRef = useRef<((msg: object) => void) | null>(null);

  const handlePlaybackComplete = useCallback(() => {
    if (sendMessageRef.current) {
      sendMessageRef.current({ type: 'audio_playback_complete' });
    }
  }, []);

  const { isSpeaking, audioEnabled, enableAudio, playAudio, playAudioChunk, getCurrentVolume } = useAudioPlayer({
    onPlaybackComplete: handlePlaybackComplete
  });

  // Auto-enable audio for streaming mode
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const isStreaming = params.get('stream') === '1' || params.get('autoplay') === '1';
    const timer = setTimeout(() => {
      if (!audioEnabled) enableAudio();
    }, isStreaming ? 100 : 2000);
    return () => clearTimeout(timer);
  }, [audioEnabled, enableAudio]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleMessage = useCallback((msg: WebSocketMessage) => {
    if (msg.type === 'chat_message') {
      chatIdRef.current += 1;
      setChatMessages(prev => {
        const updated = [...prev, { id: chatIdRef.current, username: msg.username || 'Anon', message: msg.message || '' }];
        return updated.length > 30 ? updated.slice(-30) : updated;
      });
    } else if (msg.type === 'ai_response') {
      if (msg.emotion) setEmotion(msg.emotion);
      if (msg.audio_base64) playAudio(msg.audio_base64, () => setEmotion('neutral'));
    } else if (msg.type === 'stream_start') {
      if (msg.emotion) setEmotion(msg.emotion);
    } else if (msg.type === 'audio_chunk') {
      if (msg.audio_base64 || msg.complete) {
        playAudioChunk(msg.audio_base64 || '', msg.complete ?? false, msg.timestamp ?? 0, msg.volume);
        if (msg.complete) setTimeout(() => setEmotion('neutral'), 1000);
      }
    } else if (msg.type === 'stream_end') {
      setTimeout(() => setEmotion('neutral'), 1000);
    }
  }, [playAudio, playAudioChunk]);

  const { isConnected, sendMessage } = useChatWebSocket(handleMessage);

  useEffect(() => { sendMessageRef.current = sendMessage; }, [sendMessage]);

  const handleVisionReaction = useCallback((text: string, audioBase64: string, category: string) => {
    setEmotion('excited');
    playAudio(audioBase64, () => setEmotion('neutral'));
  }, [playAudio]);

  return (
    <>
      {/* Hidden heartbeat */}
      <ScreenCapture
        onReaction={handleVisionReaction}
        onAudioChunk={(chunk, isComplete) => {
          if (chunk || isComplete) {
            setEmotion('excited');
            playAudioChunk(chunk, isComplete);
            if (isComplete) setTimeout(() => setEmotion('neutral'), 1000);
          }
        }}
        sendFrame={sendMessage}
        intervalSeconds={10}
      />

      {/* Vtuber avatar overlay (bottom-right, transparent bg) */}
      <div className="avatar-overlay">
        <Avatar emotion={emotion} getCurrentVolume={getCurrentVolume} />
      </div>

      {/* Chat overlay (bottom-left) */}
      <div className="chat-overlay">
        <div className="chat-overlay-header">💬 Twitch Chat</div>
        <div className="chat-messages chat-scrollbar">
          {chatMessages.length === 0 && (
            <div className="chat-msg">
              <span className="text" style={{ opacity: 0.4, fontStyle: 'italic' }}>
                Waiting for messages...
              </span>
            </div>
          )}
          {chatMessages.map((msg) => (
            <div key={msg.id} className="chat-msg">
              <span className="username">{msg.username}:</span>
              <span className="text">{msg.message}</span>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Connection dot */}
      <div className={`connection-dot ${isConnected ? 'connected' : 'disconnected'}`} />

      {/* Status badge */}
      <div className={`status-badge ${isSpeaking ? 'speaking' : 'idle'}`}>
        {isSpeaking ? `🎤 ${emotion}` : '💤 Idle'}
      </div>

      {/* Audio enable button */}
      {!audioEnabled && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] cursor-pointer" onClick={enableAudio}>
          <div className="bg-white/90 px-4 py-2 rounded-lg shadow-lg text-center">
            <span className="text-xl mr-2">🔊</span>
            <span className="text-sm font-medium text-gray-800">Click to Enable Audio</span>
          </div>
        </div>
      )}
    </>
  );
};

export default VTuberPage;