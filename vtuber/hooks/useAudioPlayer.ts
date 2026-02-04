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
    playAudioChunk: (base64Audio: string, isComplete?: boolean, timestamp?: number) => Promise<void>;
    stopAudio: () => void;
    getCurrentVolume: () => number;
}

export function useAudioPlayer(options: UseAudioPlayerOptions = {}): UseAudioPlayerReturn {
    const { onPlaybackComplete } = options;
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [audioEnabled, setAudioEnabled] = useState(false);

    // AudioContext Refs
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const nextStartTimeRef = useRef<number>(0);
    const sourceNodesRef = useRef<AudioBufferSourceNode[]>([]);
    const dataArrayRef = useRef<Uint8Array<ArrayBuffer> | null>(null);

    // Queue to ensure sequential decoding and scheduling
    const processingChainRef = useRef<Promise<void>>(Promise.resolve());

    // Buffering Refs for Batch Processing
    const audioBufferRef = useRef<Uint8Array<ArrayBuffer>[]>([]);
    const audioBufferLengthRef = useRef<number>(0);
    const BUFFER_THRESHOLD = 24000; // ~24KB (approx 1.5s of audio at 128kbps)

    // Fallback for full file playback
    const audioRef = useRef<HTMLAudioElement | null>(null);

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

                // Create Analyser
                const analyser = audioContextRef.current.createAnalyser();
                analyser.fftSize = 256;
                analyserRef.current = analyser;
                dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
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
        }

        // Clear buffer
        audioBufferRef.current = [];
        audioBufferLengthRef.current = 0;

        // Cancel existing queue by replacing the promise chain (effectively ignoring previous tasks)
        // Note: We can't cancel running promises, but we can prevent new ones from acting.
        // For simplicity, we just reset the state.

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

            // Connect to Analyser for HTML5 Audio (Cross-origin issues may occur if not strict, but local blob is fine)
            // Note: MediaElementSource needs context to be running
            if (audioContextRef.current) {
                try {
                    // Ensure context is running
                    if (audioContextRef.current.state === 'suspended') {
                        audioContextRef.current.resume();
                    }

                    const source = audioContextRef.current.createMediaElementSource(audio);
                    if (analyserRef.current) {
                        source.connect(analyserRef.current);
                        analyserRef.current.connect(audioContextRef.current.destination);
                    } else {
                        source.connect(audioContextRef.current.destination);
                    }
                } catch (e) {
                    console.warn("Could not connect HTML audio to analyser", e);
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


    const playAudioChunk = useCallback(async (base64Audio: string, isComplete: boolean = false) => {
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

            // Ensure analyser exists
            if (!analyserRef.current) {
                const analyser = ctx.createAnalyser();
                analyser.fftSize = 256;
                analyserRef.current = analyser;
                dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
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

                // Connect source -> analyser -> destination
                if (analyserRef.current) {
                    source.connect(analyserRef.current);
                    analyserRef.current.connect(ctx.destination);
                    console.log("[Audio] Connected source to analyser");
                } else {
                    source.connect(ctx.destination);
                    console.warn("[Audio] Analyser missing during connection!");
                }

                const startTime = nextStartTimeRef.current;
                source.start(startTime);

                // Keep track of active nodes for stop functionality
                sourceNodesRef.current.push(source);
                source.onended = () => {
                    const index = sourceNodesRef.current.indexOf(source);
                    if (index > -1) {
                        sourceNodesRef.current.splice(index, 1);
                    }
                    if (sourceNodesRef.current.length === 0 && !isComplete) {
                        // All chunks played (so far)
                        // Don't necessarily stop speaking if we expect more, but 
                        // if the queue is empty and we are done, we will handle it.
                        // Actually, we should check in the chain or rely on isComplete flag from caller?
                        // The caller passes isComplete=true on the last chunk.
                    }
                };

                // Advance time
                nextStartTimeRef.current += audioBuffer.duration;

                setSpeakingSafe(true);

            } catch (e) {
                console.error("[Audio] Chunk decode/play error", e);
                // If decode fails (e.g. corruption), we just skip this batch
            }
        });

        // Wait for the chain step we just added
        await processingChainRef.current;

        if (isComplete) {
            // Calculate when the final silence should trigger
            const ctx = audioContextRef.current;
            if (ctx) {
                // Wait for the queue to finish playing
                const remainingTime = Math.max(0, nextStartTimeRef.current - ctx.currentTime);
                setTimeout(() => {
                    // Check again if we are really done
                    if (sourceNodesRef.current.length === 0) {
                        setSpeakingSafe(false);
                        // Signal backend that playback is complete
                        if (onPlaybackComplete) {
                            console.log('[Audio] Playback complete, signaling backend');
                            onPlaybackComplete();
                        }
                    }
                }, (remainingTime * 1000) + 100); // 100ms buffer
            } else {
                setSpeakingSafe(false);
                // Signal backend that playback is complete
                if (onPlaybackComplete) {
                    console.log('[Audio] Playback complete (no ctx), signaling backend');
                    onPlaybackComplete();
                }
            }
        }

    }, [audioEnabled, setSpeakingSafe, onPlaybackComplete]);

    const getCurrentVolume = useCallback(() => {
        if (!analyserRef.current || !dataArrayRef.current) {
            if (Math.random() < 0.01) console.warn("[Audio] getCurrentVolume: Analyser not ready. Enabled:", audioEnabled);
            return 0;
        }

        analyserRef.current.getByteFrequencyData(dataArrayRef.current);

        // Calculate average volume
        let sum = 0;
        for (let i = 0; i < dataArrayRef.current.length; i++) {
            sum += dataArrayRef.current[i];
        }
        const average = sum / dataArrayRef.current.length;

        // Normalize 0-255 to 0-1
        // Usually speech doesn't hit 255 constantly, so we can scale it up a bit

        // DEBUG: Log raw average if 0
        if (average === 0 && Math.random() < 0.01) {
            console.log("[Audio] Raw Average is 0. Analyser connected?", !!analyserRef.current);
        } else if (average > 0 && Math.random() < 0.05) {
            console.log("[Audio] Raw Average:", average);
        }

        return Math.min(1, average / 100);
    }, []);

    return {
        isSpeaking,
        audioEnabled,
        enableAudio,
        playAudio, // Full file (legacy)
        playAudioChunk, // Streaming (Web Audio API)
        stopAudio,
        getCurrentVolume
    };
}
