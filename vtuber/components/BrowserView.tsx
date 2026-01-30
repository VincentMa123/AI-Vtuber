'use client';

import React, { useState, useEffect, useCallback } from 'react';

interface BrowserViewProps {
    sendMessage?: (data: any) => void;
    isConnected?: boolean;
}

export const BrowserView: React.FC<BrowserViewProps> = ({
    sendMessage,
    isConnected = false
}) => {
    const [isRunning, setIsRunning] = useState(false);
    const [currentUrl, setCurrentUrl] = useState('');
    const [lastAction, setLastAction] = useState('');
    const [screenshot, setScreenshot] = useState<string | null>(null);

    // Handle incoming WebSocket messages (called from parent)
    const handleMessage = useCallback((data: any) => {
        switch (data.type) {
            case 'browser_started':
                setIsRunning(true);
                break;
            case 'browser_stopped':
                setIsRunning(false);
                setScreenshot(null);
                break;
            case 'browser_action':
                setLastAction(data.action || '');
                setCurrentUrl(data.url || '');
                break;
            case 'browser_screenshot':
                setScreenshot(data.image_base64 || null);
                break;
        }
    }, []);

    const startBrowser = () => {
        if (sendMessage) {
            sendMessage({ type: 'start_browser', interval: 30 });
        }
    };

    const stopBrowser = () => {
        if (sendMessage) {
            sendMessage({ type: 'stop_browser' });
        }
    };

    const sendCommand = (command: string, extra?: any) => {
        if (sendMessage) {
            sendMessage({ type: 'browser_command', command, ...extra });
        }
    };

    return (
        <div className="bg-gray-900/90 rounded-lg p-4 backdrop-blur-sm border border-gray-700">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-white font-semibold flex items-center gap-2">
                    🌐 Browser Control
                    <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-500' : 'bg-gray-500'}`} />
                </h3>

                {!isRunning ? (
                    <button
                        onClick={startBrowser}
                        disabled={!isConnected}
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white text-sm px-3 py-1 rounded transition-colors"
                    >
                        Start Browsing
                    </button>
                ) : (
                    <button
                        onClick={stopBrowser}
                        className="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded transition-colors"
                    >
                        Stop
                    </button>
                )}
            </div>

            {/* Status */}
            {isRunning && (
                <div className="text-xs text-gray-400 mb-2">
                    <div className="truncate">URL: {currentUrl || 'Loading...'}</div>
                    <div>Last: {lastAction || 'Idle'}</div>
                </div>
            )}

            {/* Screenshot Preview */}
            {screenshot && (
                <div className="relative aspect-video bg-black rounded overflow-hidden mb-3">
                    <img
                        src={`data:image/jpeg;base64,${screenshot}`}
                        alt="Browser View"
                        className="w-full h-full object-contain"
                    />
                </div>
            )}

            {/* Manual Controls */}
            {isRunning && (
                <div className="flex flex-wrap gap-1">
                    <button
                        onClick={() => sendCommand('scroll_down')}
                        className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded"
                    >
                        ↓ Scroll
                    </button>
                    <button
                        onClick={() => sendCommand('scroll_up')}
                        className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded"
                    >
                        ↑ Scroll
                    </button>
                    <button
                        onClick={() => sendCommand('click_product')}
                        className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded"
                    >
                        🛒 Click
                    </button>
                    <button
                        onClick={() => sendCommand('go_back')}
                        className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded"
                    >
                        ← Back
                    </button>
                    <button
                        onClick={() => sendCommand('go_home')}
                        className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-2 py-1 rounded"
                    >
                        🏠 Home
                    </button>
                </div>
            )}

            {/* Connection Status */}
            {!isConnected && (
                <div className="text-yellow-400 text-xs mt-2">
                    ⚠️ Not connected to server
                </div>
            )}
        </div>
    );
};

export default BrowserView;
