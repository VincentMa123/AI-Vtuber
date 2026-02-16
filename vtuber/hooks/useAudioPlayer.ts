import { useRef, useState, useCallback, useEffect } from 'react';

export type EmotionType = 'happy' | 'sad' | 'angry' | 'excited' | 'neutral';

interface UseAudioPlayerOptions {
    onPlaybackComplete?: () => void;
}

interface UseAudioPlayerReturn {
    isSpeaking: boolean;
    audioEnabled: boolean;
    enableAudio: () => void;
    playAudio: (base64Audio: string, onComplete?: () => void) => Promise<void>;
    playAudioChunk: (base64Audio: string, isComplete?: boolean, timestamp?: number, volume?: number) => Promise<void>;
    stopAudio: () => void;
    getCurrentVolume: () => number;
    isPlaybackCompleteRef: React.MutableRefObject<boolean>;
}

export function useAudioPlayer(options: UseAudioPlayerOptions = {}): UseAudioPlayerReturn {
    const { onPlaybackComplete } = options;
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [audioEnabled, setAudioEnabled] = useState(false);

    // AudioContext Refs
    const audioContextRef = useRef<AudioContext | null>(null);
    const nextStartTimeRef = useRef<number>(0);
    const visualNextStartTimeRef = useRef<number>(0);
    const sourceNodesRef = useRef<AudioBufferSourceNode[]>([]);

    // Queue to ensure sequential decoding and scheduling
    const processingChainRef = useRef<Promise<void>>(Promise.resolve());

    // Buffering Refs for Batch Processing
    const audioBufferRef = useRef<Uint8Array<ArrayBuffer>[]>([]);
    const audioBufferLengthRef = useRef<number>(0);
    const BUFFER_THRESHOLD = 8192;

    // Fallback for full file playback
    const audioRef = useRef<HTMLAudioElement | null>(null);

    // Queue for backend-provided volume data
    const volumeQueueRef = useRef<{ start: number; end: number; volume: number }[]>([]);

    // Track if backend signaled completion
    const isPlaybackCompleteRef = useRef(false);

    // Safety ref
    const mountedRef = useRef(true);
    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            // Cleanup on unmount
            if (audioContextRef.current) {
                audioContextRef.current.close();
            }
        };
    }, []);

    // Helper to safe-set speaking state
    const setSpeakingSafe = useCallback((speaking: boolean) => {
        if (mountedRef.current) {
            setIsSpeaking(speaking);
        }
    }, []);

    const enableAudio = useCallback(() => {
        setAudioEnabled(true);
        try {
            if (!audioContextRef.current) {
                const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
                audioContextRef.current = new AudioContextClass();
            }
            // Resume if suspended (browser autoplay policy)
            if (audioContextRef.current.state === 'suspended') {
                audioContextRef.current.resume();
            }

            // Play silent sound to unlock
            const buffer = audioContextRef.current.createBuffer(1, 1, 22050);
            const source = audioContextRef.current.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContextRef.current.destination);
            source.start(0);

        } catch (e) {
            console.error("[Audio] Enable error", e);
        }
    }, []);

    const stopAudio = useCallback(() => {
        // Stop all scheduled sources
        sourceNodesRef.current.forEach(node => {
            try {
                node.stop();
                node.disconnect();
            } catch (e) { /* ignore */ }
        });
        sourceNodesRef.current = [];

        // Reset timing
        if (audioContextRef.current) {
            nextStartTimeRef.current = audioContextRef.current.currentTime;
            visualNextStartTimeRef.current = 0;
        }

        // Clear buffer
        audioBufferRef.current = [];
        audioBufferLengthRef.current = 0;
        volumeQueueRef.current = [];
        isPlaybackCompleteRef.current = false;

        // Stop HTML Audio if playing
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            audioRef.current = null;
        }

        setSpeakingSafe(false);
    }, [setSpeakingSafe]);

    // Play full audio file (legacy / non-streaming)
    const playAudio = useCallback(async (base64Audio: string, onComplete?: () => void) => {
        stopAudio();

        try {
            const mimeType = base64Audio.startsWith('UklG') ? 'audio/wav' : 'audio/mpeg';
            const url = `data:${mimeType};base64,${base64Audio}`;
            const audio = new Audio(url);
            audioRef.current = audio;

            if (audioContextRef.current) {
                try {
                    // Ensure context is running
                    if (audioContextRef.current.state === 'suspended') {
                        audioContextRef.current.resume();
                    }

                    const source = audioContextRef.current.createMediaElementSource(audio);
                    source.connect(audioContextRef.current.destination);
                } catch (e) {
                    console.warn("Could not connect HTML audio to destination", e);
                }
            }

            audio.onended = () => {
                setSpeakingSafe(false);
                audioRef.current = null;
                onComplete?.();
            };

            audio.onerror = (e) => {
                console.warn("[Audio] Playback error", e);
                setSpeakingSafe(false);
            };

            setSpeakingSafe(true);
            await audio.play();
        } catch (err) {
            console.error("[Audio] Play failed", err);
            setSpeakingSafe(false);
        }
    }, [stopAudio, setSpeakingSafe]);


    const playAudioChunk = useCallback(async (base64Audio: string, isComplete: boolean = false, timestamp: number = 0, volume: number = 0) => {
        if (isComplete) {
            isPlaybackCompleteRef.current = true;
        }
        // Chain the processing to ensure sequential order
        processingChainRef.current = processingChainRef.current.then(async () => {
            if (!audioEnabled) {
                console.warn("[Audio] playAudioChunk skipped: Audio not enabled. Please click enable!");
                return;
            }
            if (!base64Audio && !isComplete) return;

            // Buffer the new chunk
            if (base64Audio) {
                try {
                    const binaryString = atob(base64Audio);
                    const len = binaryString.length;
                    const bytes = new Uint8Array(len);
                    for (let i = 0; i < len; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    audioBufferRef.current.push(bytes);
                    audioBufferLengthRef.current += len;
                } catch (e) {
                    console.error("[Audio] Buffer error", e);
                }
            }

            // Check threshold or completion
            const shouldDecode = audioBufferLengthRef.current >= BUFFER_THRESHOLD || (isComplete && audioBufferLengthRef.current > 0);

            if (!shouldDecode) return;

            // Initialize context if needed
            if (!audioContextRef.current) {
                const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
                audioContextRef.current = new AudioContextClass();
            }
            const ctx = audioContextRef.current;
            if (ctx.state === 'suspended') {
                ctx.resume();
            }

            try {
                // Merge Buffer
                const totalLength = audioBufferLengthRef.current;
                const mergedBytes = new Uint8Array(totalLength);
                let offset = 0;
                for (const chunk of audioBufferRef.current) {
                    mergedBytes.set(chunk, offset);
                    offset += chunk.length;
                }

                // Reset Buffer
                audioBufferRef.current = [];
                audioBufferLengthRef.current = 0;

                // Decode
                // Note: decodeAudioData might reject if the merged chunk is invalid (e.g. cut off MP3 frame at the end)
                // However, handling it here is robust enough usually.
                const audioBuffer = await ctx.decodeAudioData(mergedBytes.buffer as ArrayBuffer);

                // Scheduler Logic
                const currentTime = ctx.currentTime;

                // If nextStartTime is in the past (gap happened or first chunk), reset to now
                // Adding a small buffer (0.05s) to allow for scheduling processing time
                if (nextStartTimeRef.current < currentTime) {
                    nextStartTimeRef.current = currentTime + 0.05;
                }

                const source = ctx.createBufferSource();
                source.buffer = audioBuffer;

                source.connect(ctx.destination);

                const startTime = nextStartTimeRef.current;
                source.start(startTime);

                // Keep track of active nodes for stop functionality
                sourceNodesRef.current.push(source);
                source.onended = () => {
                    const index = sourceNodesRef.current.indexOf(source);
                    if (index > -1) {
                        sourceNodesRef.current.splice(index, 1);
                    }

                    // Event-driven completion check
                    if (sourceNodesRef.current.length === 0 && isPlaybackCompleteRef.current) {
                        console.log("[Audio] Playback finished (event-driven)");
                        setSpeakingSafe(false);
                        volumeQueueRef.current = []; // Immediate cleanup!
                        isPlaybackCompleteRef.current = false;

                        if (onPlaybackComplete) {
                            onPlaybackComplete();
                        }
                    }
                };

                // Advance time
                const duration = audioBuffer.duration;

                // Queue volume data
                if (volume !== undefined && volume > 0) {
                    // Visual Sync Logic:
                    // We use an independent "visual clock" based on performance.now()
                    // This avoids issues where audioContext.currentTime freezes (headless)
                    // or drifts significantly.
                    
                    const now = performance.now();
                    let start = visualNextStartTimeRef.current;
                    
                    // If the visual queue has fallen behind (gap in speech), jump to now
                    if (start < now) {
                        start = now;
                    }
                    
                    const end = start + (duration * 1000);
                    
                    volumeQueueRef.current.push({
                        start: start,
                        end: end,
                        volume: volume
                    });

                    visualNextStartTimeRef.current = end;

                    // Clean up old volume entries
                    const cutoff = now - 5000; 
                    volumeQueueRef.current = volumeQueueRef.current.filter(v => v.end > cutoff);
                }

                nextStartTimeRef.current += duration;

                setSpeakingSafe(true);

            } catch (e) {
                console.error("[Audio] Chunk decode/play error", e);
                // If decode fails (e.g. corruption), we just skip this batch
            }
        });

        // Wait for the chain step we just added
        await processingChainRef.current;

    }, [audioEnabled, setSpeakingSafe, onPlaybackComplete]);

    const getCurrentVolume = useCallback(() => {
        // Check backend volume queue first
        // Use performance.now() (ms) to match the new queue format
        const now = performance.now();
        const activeVolume = volumeQueueRef.current.find(v => now >= v.start && now < v.end);

        if (activeVolume) {
            return activeVolume.volume;
        }

        return 0;
    }, []);

    return {
        isSpeaking,
        audioEnabled,
        enableAudio,
        playAudio, // Full file (legacy)
        playAudioChunk, // Streaming (Web Audio API)
        stopAudio,
        getCurrentVolume,
        isPlaybackCompleteRef
    };
}
