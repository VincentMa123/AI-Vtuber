export type EmotionType = 'happy' | 'sad' | 'angry' | 'excited' | 'neutral';

export interface ExpressionParams {
    eyeSmile: number;
    mouthForm: number;
    browY: number;
    angry: number;
    eyeSize: number;
    armR: number;
    armL: number;
}

export const EXPRESSION_PRESETS: Record<EmotionType, ExpressionParams> = {
    happy: {
        eyeSmile: 0.7,
        mouthForm: 0.8,
        browY: 0.6,
        angry: 0,
        eyeSize: 0,
        armR: 0.3,
        armL: 0.3
    },
    sad: {
        eyeSmile: 0,
        mouthForm: -0.5,
        browY: 0.3,
        angry: 0,
        eyeSize: -0.2,
        armR: 0,
        armL: 0
    },
    angry: {
        eyeSmile: 0,
        mouthForm: -0.3,
        browY: 0.2,
        angry: 0.8,
        eyeSize: 0,
        armR: 0,
        armL: 0
    },
    excited: {
        eyeSmile: 0.3,
        mouthForm: 0.6,
        browY: 0.7,
        angry: 0,
        eyeSize: 0.5,
        armR: 0.6,
        armL: 0.4
    },
    neutral: {
        eyeSmile: 0,
        mouthForm: 0,
        browY: 0.5,
        angry: 0,
        eyeSize: 0,
        armR: 0,
        armL: 0
    }
};

/**
 * Get expression parameters for a given emotion
 */
export function getExpressionForEmotion(emotion: EmotionType): ExpressionParams {
    return EXPRESSION_PRESETS[emotion] || EXPRESSION_PRESETS.neutral;
}

/**
 * Create initial expression state
 */
export function createExpressionState(): ExpressionParams {
    return { ...EXPRESSION_PRESETS.neutral };
}

/**
 * Interpolate current expression towards target
 */
export function lerpExpression(
    current: ExpressionParams,
    target: ExpressionParams,
    speed: number = 0.08
): ExpressionParams {
    return {
        eyeSmile: current.eyeSmile + (target.eyeSmile - current.eyeSmile) * speed,
        mouthForm: current.mouthForm + (target.mouthForm - current.mouthForm) * speed,
        browY: current.browY + (target.browY - current.browY) * speed,
        angry: current.angry + (target.angry - current.angry) * speed,
        eyeSize: current.eyeSize + (target.eyeSize - current.eyeSize) * speed,
        armR: current.armR + (target.armR - current.armR) * speed,
        armL: current.armL + (target.armL - current.armL) * speed,
    };
}
