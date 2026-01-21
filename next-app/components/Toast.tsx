//Components/Toast.tsx

"use client";

import React, { useEffect, useState } from 'react';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastProps {
    message: string;
    type?: ToastType;
    duration?: number;
    onClose?: () => void;
}

export const Toast: React.FC<ToastProps> = ({
    message,
    type = 'info',
    duration = 3000,
    onClose,
}) => {
    const [isVisible, setIsVisible] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => {
            setIsVisible(false);
            onClose?.();
        }, duration);

        return () => clearTimeout(timer);
    }, [duration, onClose]);

    if (!isVisible) return null;

    const bgColor = {
        success: 'bg-gradient-to-r from-green-500 to-emerald-600',
        error: 'bg-gradient-to-r from-red-500 to-rose-600',
        info: 'bg-gradient-to-r from-blue-500 to-cyan-600',
        warning: 'bg-gradient-to-r from-amber-500 to-orange-600' 
    }[type];

    const icon = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️'
    }[type];

    return (
        <div className="fixed top-6 right-6 z-50 animate-in slide-in-from-right-8 duration-300">
            <div className={`${bgColor} text-white rounded-xl shadow-2xl p-4 max-w-md backdrop-blur-sm border border-white/20`}>
                <div className="flex items-center gap-3">
                    <span className="text-xl">{icon}</span>
                    <div className="flex-1">
                        <p className="font-bold">{type.toUpperCase()}</p>
                        <p className="text-sm opacity-90">{message}</p>
                    </div>
                    <button
                        onClick={() => setIsVisible(false)}
                        className="text-white/70 hover:text-white text-lg"
                    >
                        ×
                    </button>
                </div>
                {/* Progress bar */}
                <div className="mt-2 h-1 bg-white/30 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-white/70 rounded-full animate-[shrink_3s_linear]"
                        style={{ animationDuration: `${duration}ms` }}
                    />
                </div>
            </div>
        </div>
    );
};