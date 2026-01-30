'use client';

import { useState, useCallback, useRef, useEffect } from 'react';

interface Position {
    x: number;
    y: number;
}

interface UseDraggableOptions {
    initialPosition?: Position;
    onDragEnd?: (position: Position) => void;
}

interface UseDraggableReturn {
    position: Position;
    isDragging: boolean;
    handleMouseDown: (e: React.MouseEvent) => void;
    setPosition: (position: Position) => void;
}

export function useDraggable(options: UseDraggableOptions = {}): UseDraggableReturn {
    const { initialPosition = { x: 0, y: 0 }, onDragEnd } = options;

    const [position, setPosition] = useState<Position>(initialPosition);
    const [isDragging, setIsDragging] = useState(false);
    const dragOffset = useRef<Position>({ x: 0, y: 0 });

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);
        dragOffset.current = {
            x: e.clientX - position.x,
            y: e.clientY - position.y
        };
    }, [position]);

    useEffect(() => {
        if (!isDragging) return;

        const handleMouseMove = (e: MouseEvent) => {
            const newX = e.clientX - dragOffset.current.x;
            const newY = e.clientY - dragOffset.current.y;
            setPosition({ x: newX, y: newY });
        };

        const handleMouseUp = () => {
            setIsDragging(false);
            onDragEnd?.(position);
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, onDragEnd, position]);

    return {
        position,
        isDragging,
        handleMouseDown,
        setPosition
    };
}

export default useDraggable;
