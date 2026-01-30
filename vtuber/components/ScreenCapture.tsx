'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';

interface ScreenCaptureProps {
    onReaction: (text: string, audioBase64: string, category: string) => void;
    onAudioChunk?: (chunk: string, isComplete: boolean) => void;
    onStatusUpdate?: (status: string) => void;
    sendFrame?: (data: any) => void;
    intervalSeconds?: number;
}

const ScreenCapture: React.FC<ScreenCaptureProps> = ({
    onStatusUpdate,
    sendFrame,
    intervalSeconds = 10
}) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [isCapturing, setIsCapturing] = useState(false);
    const isCapturingRef = useRef(false);
    const [debugStatus, setDebugStatus] = useState<string>("Waiting for user...");
    const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);

    const [useNative, setUseNative] = useState(false);

    // Stop capture and cleanup
    const stopCapture = useCallback(() => {
        if (heartbeatIntervalRef.current) {
            clearInterval(heartbeatIntervalRef.current);
            heartbeatIntervalRef.current = null;
        }

        if (videoRef.current && videoRef.current.srcObject) {
            const stream = videoRef.current.srcObject as MediaStream;
            stream.getTracks().forEach(track => track.stop());
            videoRef.current.srcObject = null;
        }

        setIsCapturing(false);
        isCapturingRef.current = false;
        setUseNative(false);
        setDebugStatus("Stopped");
        if (onStatusUpdate) onStatusUpdate("Stopped");
    }, [onStatusUpdate]);

    const startHeartbeatLoop = (nativeMode: boolean) => {
        // Clear existing if any
        if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);

        heartbeatIntervalRef.current = setInterval(async () => {
            if (!isCapturingRef.current) return;
            // if (!sendFrame) return; // Wait, actually we should check connection status in parent

            let imageBase64: string | null = null;

            if (!nativeMode) {
                // Browser Mode Checks
                if (!videoRef.current || !canvasRef.current) return;
                const stream = videoRef.current.srcObject as MediaStream;
                if (!stream || !stream.active) {
                    stopCapture();
                    return;
                }

                // Draw to canvas
                const context = canvasRef.current.getContext('2d');
                if (!context) return;

                // Resize canvas
                if (videoRef.current.videoWidth === 0 || videoRef.current.videoHeight === 0) return;

                canvasRef.current.width = videoRef.current.videoWidth;
                canvasRef.current.height = videoRef.current.videoHeight;
                context.drawImage(videoRef.current, 0, 0);

                // Get Base64
                imageBase64 = canvasRef.current.toDataURL('image/jpeg', 0.6).split(',')[1];
            }

            try {
                if (sendFrame) {
                    sendFrame({
                        type: 'vision_frame',
                        image_base64: imageBase64,
                        use_native_capture: nativeMode,
                        timestamp: Date.now() / 1000
                    });
                    // Note: Status updates now come from the server via onStatusUpdate
                } else {
                    setDebugStatus("Disconnected");
                }

            } catch (err) {
                console.error("ScreenCapture Heartbeat Error:", err);
                setDebugStatus("Capture Error");
            }

        }, intervalSeconds * 1000);
    };

    const startNativeCapture = () => {
        setIsCapturing(true);
        isCapturingRef.current = true;
        setUseNative(true);
        setDebugStatus("Vision Active (OBS Mode)");
        startHeartbeatLoop(true);
    };

    // Clean up on unmount
    useEffect(() => {
        return () => {
            stopCapture();
        };
    }, [stopCapture]);

    return (
        <div className="fixed top-0 left-0 p-0 z-50">
            {/* Hidden processing elements */}
            <video ref={videoRef} className="hidden" muted playsInline />
            <canvas ref={canvasRef} className="hidden" />

            {/* UI Overlay */}
            {!isCapturing ? (
                <div className="p-4 flex gap-2">

                    <button
                        onClick={startNativeCapture}
                        title="Use this if running inside OBS"
                        className="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded shadow-lg flex items-center gap-2 transition-all hover:scale-105"
                    >
                        <span>🎥</span>
                        <span>OBS Mode</span>
                    </button>
                </div>
            ) : (
                <div className="m-2 bg-black/70 text-green-400 text-xs px-2 py-1 rounded font-mono border border-green-900 pointer-events-none opacity-60">
                    {useNative ? '🎥' : '👁️'} {debugStatus}
                </div>
            )}
        </div>
    );
};

export default ScreenCapture;
