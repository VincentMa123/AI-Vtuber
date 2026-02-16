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
    const [debugStatus, setDebugStatus] = useState<string>("Vision Active");
    const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const isActiveRef = useRef(false);

    const stopCapture = useCallback(() => {
        if (heartbeatIntervalRef.current) {
            clearInterval(heartbeatIntervalRef.current);
            heartbeatIntervalRef.current = null;
        }
        isActiveRef.current = false;
        setDebugStatus("Stopped");
        if (onStatusUpdate) onStatusUpdate("Stopped");
    }, [onStatusUpdate]);

    const startHeartbeatLoop = useCallback(() => {
        if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);

        isActiveRef.current = true;
        setDebugStatus("Vision Active");

        heartbeatIntervalRef.current = setInterval(async () => {
            if (!isActiveRef.current) return;

            try {
                if (sendFrame) {
                    sendFrame({
                        type: 'vision_frame',
                        image_base64: null,
                        use_native_capture: true,
                        timestamp: Date.now() / 1000
                    });
                } else {
                    setDebugStatus("Disconnected");
                }
            } catch (err) {
                console.error("ScreenCapture Heartbeat Error:", err);
                setDebugStatus("Capture Error");
            }

        }, intervalSeconds * 1000);
    }, [sendFrame, intervalSeconds]);

    // Auto-start on mount
    useEffect(() => {
        startHeartbeatLoop();
        return () => stopCapture();
    }, [startHeartbeatLoop, stopCapture]);

    return null;
};

export default ScreenCapture;
