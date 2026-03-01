'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as PIXI from 'pixi.js';

import type { EmotionType } from '../hooks/useAudioPlayer';

interface AvatarProps {
    emotion: EmotionType;
    getCurrentVolume?: () => number;
}

const Avatar: React.FC<AvatarProps> = ({ emotion, getCurrentVolume }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [model, setModel] = useState<any>(null);
    const appRef = useRef<PIXI.Application | null>(null);
    const animationRef = useRef<number | null>(null);

    // Debug state
    const [debugStatus, setDebugStatus] = useState<string>("Initializing...");
    const [error, setError] = useState<string | null>(null);

    // Model initialization
    useEffect(() => {
        if (!canvasRef.current) return;
        setDebugStatus("Canvas ref found");

        let app: PIXI.Application | null = null;
        let mounted = true;

        const init = async () => {
            console.log("[Avatar] === INIT START ===");
            setDebugStatus("Loading PIXI...");
            (window as any).PIXI = PIXI;
            PIXI.utils.skipHello();
            console.log("[Avatar] PIXI assigned to window");

            try {
                let attempts = 0;
                while (
                    !(window as any).Live2D &&
                    !(window as any).Live2DCubismCore &&
                    attempts < 20
                ) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    attempts++;
                }

                console.log("[Avatar] Live2D check:", {
                    Live2D: !!(window as any).Live2D,
                    Live2DCubismCore: !!(window as any).Live2DCubismCore,
                    attempts
                });

                if (!(window as any).Live2D && !(window as any).Live2DCubismCore) {
                    const msg = 'Live2D runtimes not loaded from script';
                    console.error("[Avatar]", msg);
                    setError(msg);
                    setDebugStatus("Error: No Live2D Runtime");
                    return;
                }

                console.log("[Avatar] Live2D runtime found, importing display library...");
                setDebugStatus("Importing Display Library...");
                const { Live2DModel } = await import('pixi-live2d-display/cubism4');
                if (!mounted) return;

                setDebugStatus("Creating PIXI App...");
                app = new PIXI.Application({
                    view: canvasRef.current!,
                    autoStart: true,
                    backgroundAlpha: 0,
                    width: 1000,
                    height: 1000,
                    sharedTicker: true,
                    sharedLoader: true,
                    antialias: true,
                    resolution: window.devicePixelRatio || 1,
                    powerPreference: 'high-performance',
                });
                appRef.current = app;

                const modelUrl = 'model/hiyori/hiyori_pro_t11.model3.json';
                console.log("[Avatar] Loading model from:", modelUrl);
                setDebugStatus(`Loading Model: ${modelUrl}`);

                Live2DModel.from(modelUrl).then((loadedModel: any) => {
                    if (!mounted || !app) return;
                    console.log("[Avatar] MODEL LOADED SUCCESSFULLY!", {
                        width: loadedModel.width,
                        height: loadedModel.height,
                        internalModel: !!loadedModel.internalModel
                    });
                    setDebugStatus("Model Loaded Successfully!");

                    app.stage.addChild(loadedModel);
                    setModel(loadedModel);

                    loadedModel.x = app.screen.width / 2 - (loadedModel.width * 0.5) / 2; // Better centering
                    loadedModel.y = app.screen.height - 900; // Adjust Y for smaller canvas
                    loadedModel.scale.set(0.5);
                    loadedModel.interactive = false; // Disable hit testing
                    loadedModel.buttonMode = false;

                    if (typeof loadedModel.autoInteract !== 'undefined') {
                        loadedModel.autoInteract = false;
                    }
                    (loadedModel as any).autoInteract = false; // Force disable auto interaction
                }).catch((err: any) => {
                    console.error("Model load error:", err);
                    setError(`Load Failed: ${err.message}`);
                    setDebugStatus("Model Load Failed");
                });

            } catch (err: any) {
                console.error("Failed to load Live2D setup:", err);
                setError(`Setup Failed: ${err.message}`);
                setDebugStatus("Setup Failed");
            }
        };

        init();

        return () => {
            mounted = false;
            if (app) {
                app.destroy(true, { children: true });
            }
        };

    }, []);


    // Lip Sync Loop - Natural speech-like mouth animation
    useEffect(() => {
        if (!model || !appRef.current || !getCurrentVolume) return;

        console.log("[Avatar] LipSync Effect Setup - Natural Speech Animation");

        const internalModel = model.internalModel;
        if (!internalModel) return;

        const originalMotionUpdate = internalModel.motionManager?.update?.bind(internalModel.motionManager);

        // State for natural lip sync animation
        let currentMouthValue = 0;
        let previousVolume = 0;
        let velocitySmooth = 0;
        let lastTime = performance.now();

        const updateLipSync = () => {
            const coreModel = internalModel.coreModel;
            if (!coreModel) return;

            const now = performance.now();
            const deltaTime = Math.min((now - lastTime) / 1000, 0.1);
            lastTime = now;

            const volume = getCurrentVolume();

            // Calculate velocity for syllable detection
            const volumeVelocity = (volume - previousVolume) / Math.max(deltaTime, 0.016);
            previousVolume = volume;
            velocitySmooth = velocitySmooth * 0.7 + volumeVelocity * 0.3;

            const threshold = 0.01;
            let targetMouth = 0;

            if (volume > threshold) {
                // Debug volume
                if (Math.random() < 0.05) console.log(`[Avatar] Volume: ${volume.toFixed(3)}`);

                // Base opening from volume
                const volumeComponent = Math.min(1.0, volume * 5);
                const syllableFrequency = 2; // Hz - syllables per second
                const syllableWave = Math.sin(now * 0.001 * syllableFrequency * Math.PI * 2);

                // Range: 0.4 to 1.0 (mouth never fully closes during speech, but varies)
                const syllableModulation = 0.4 + (syllableWave * 0.5 + 0.5) * 0.6;

                // Add some randomness for natural variation (prevents robotic feel)
                const randomJitter = 1 + (Math.random() - 0.5) * 0.1;

                // Velocity still adds emphasis on new syllables/words
                const velocityBoost = Math.max(0, velocitySmooth * 0.1);

                targetMouth = Math.min(1.0, volumeComponent * syllableModulation * randomJitter + velocityBoost);
            }

            // Smooth interpolation - opening faster than closing
            const openSpeed = 25;   // Fast open
            const closeSpeed = 20;  // Slightly slower close for natural feel
            const speed = targetMouth > currentMouthValue ? openSpeed : closeSpeed;
            const smoothFactor = 1 - Math.exp(-speed * deltaTime);

            currentMouthValue += (targetMouth - currentMouthValue) * smoothFactor;
            currentMouthValue = Math.max(0, Math.min(1, currentMouthValue));

            coreModel.setParameterValueById('ParamMouthOpenY', currentMouthValue);
        };

        if (internalModel.motionManager && originalMotionUpdate) {
            internalModel.motionManager.update = (m: any, now: number) => {
                const result = originalMotionUpdate(m, now);
                updateLipSync();
                return result;
            };
        } else {
            console.log("[Avatar] Fallback: Using ticker for lip sync");
            const app = appRef.current!;
            const tickerUpdate = () => updateLipSync();
            app.ticker.add(tickerUpdate, null, PIXI.UPDATE_PRIORITY.LOW);
            return () => app.ticker.remove(tickerUpdate);
        }

        return () => {
            if (internalModel.motionManager && originalMotionUpdate) {
                internalModel.motionManager.update = originalMotionUpdate;
            }
        };
    }, [model, getCurrentVolume]);

    const playMotion = (group: string) => {
        if (!model) return;
        try {
            model.internalModel.motionManager.startMotion(group, 0);
        } catch (e) {
            console.error("Failed to play motion:", e);
        }
    };

    // Emotion-based motion triggers
    const previousEmotionRef = useRef<EmotionType | null>(null);

    useEffect(() => {
        if (!model) return;

        // Only trigger on emotion change
        if (previousEmotionRef.current === emotion) return;
        previousEmotionRef.current = emotion;

        // Map emotions to motion groups
        const emotionMotionMap: Record<EmotionType, string[]> = {
            happy: ['Flick'],
            excited: ['FlickUp'],
            sad: ['Flick@Body'],
            angry: ['FlickDown', 'Tap@Body'], // Will randomly pick one
            neutral: ['Idle']
        };

        const motions = emotionMotionMap[emotion];
        if (motions && motions.length > 0) {
            // Pick a random motion from available options for this emotion
            const selectedMotion = motions[Math.floor(Math.random() * motions.length)];
            console.log(`[Avatar] Emotion changed to: ${emotion} → Playing motion: ${selectedMotion}`);
            playMotion(selectedMotion);
        }
    }, [model, emotion]);

    return (
        <div className="w-full h-full flex items-center justify-center overflow-visible relative" style={{ border: '3px solid red' }}>
            <canvas ref={canvasRef} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />

            {/* Debug Overlay */}
            <div className="absolute top-0 left-0 bg-black/80 text-white p-2 text-xs font-mono z-50 pointer-events-none w-full break-words">
                <div className="font-bold mb-1">Avatar Debug</div>
                <div>Status: {debugStatus}</div>
                <div>Model: {model ? 'LOADED' : 'NOT LOADED'}</div>
                {error && <div className="text-red-400 font-bold mt-1">Error: {error}</div>}
            </div>
        </div>
    );
};

export default Avatar;
