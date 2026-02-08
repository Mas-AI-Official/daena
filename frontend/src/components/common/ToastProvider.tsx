import React, { useEffect, useState, useCallback } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '../../utils/cn';

interface Toast {
    id: string;
    type: 'success' | 'error' | 'warning' | 'info';
    message: string;
    duration?: number;
}

interface ToastProviderProps {
    children: React.ReactNode;
}

const ToastContext = React.createContext<{
    toast: (type: Toast['type'], message: string, duration?: number) => void;
    success: (message: string, duration?: number) => void;
    error: (message: string, duration?: number) => void;
    warning: (message: string, duration?: number) => void;
    info: (message: string, duration?: number) => void;
} | null>(null);

export function ToastProvider({ children }: ToastProviderProps) {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const addToast = useCallback((type: Toast['type'], message: string, duration = 5000) => {
        const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        setToasts(prev => [...prev, { id, type, message, duration }]);

        if (duration > 0) {
            setTimeout(() => {
                setToasts(prev => prev.filter(t => t.id !== id));
            }, duration);
        }
    }, []);

    const removeToast = useCallback((id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    // Listen for API error events
    useEffect(() => {
        const handleApiError = (event: CustomEvent<{ message: string; status?: number }>) => {
            addToast('error', event.detail.message);
        };

        window.addEventListener('api-error', handleApiError as EventListener);
        return () => {
            window.removeEventListener('api-error', handleApiError as EventListener);
        };
    }, [addToast]);

    const contextValue = {
        toast: addToast,
        success: (message: string, duration?: number) => addToast('success', message, duration),
        error: (message: string, duration?: number) => addToast('error', message, duration),
        warning: (message: string, duration?: number) => addToast('warning', message, duration),
        info: (message: string, duration?: number) => addToast('info', message, duration)
    };

    return (
        <ToastContext.Provider value={contextValue}>
            {children}
            <ToastContainer toasts={toasts} onRemove={removeToast} />
        </ToastContext.Provider>
    );
}

export function useToast() {
    const context = React.useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
}

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: string) => void }) {
    return (
        <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
            {toasts.map((toast) => (
                <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
            ))}
        </div>
    );
}

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: (id: string) => void }) {
    const icons = {
        success: CheckCircle,
        error: AlertCircle,
        warning: AlertTriangle,
        info: Info
    };

    const colors = {
        success: 'border-green-500/30 bg-green-500/10 text-green-400',
        error: 'border-red-500/30 bg-red-500/10 text-red-400',
        warning: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
        info: 'border-blue-500/30 bg-blue-500/10 text-blue-400'
    };

    const Icon = icons[toast.type];

    return (
        <div
            className={cn(
                'pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg border backdrop-blur-md shadow-lg max-w-sm animate-slide-in-right',
                colors[toast.type]
            )}
        >
            <Icon className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="text-sm text-white flex-1">{toast.message}</p>
            <button
                onClick={() => onRemove(toast.id)}
                className="shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors"
            >
                <X className="w-4 h-4 text-starlight-400" />
            </button>
        </div>
    );
}

// Global toast function for use outside React components
let globalToast: typeof ToastContext extends React.Context<infer T> ? T : never = null;

export function setGlobalToast(toastFn: typeof globalToast) {
    globalToast = toastFn;
}

export function toast(type: Toast['type'], message: string, duration?: number) {
    if (globalToast) {
        globalToast.toast(type, message, duration);
    } else {
        // Fallback: dispatch custom event
        window.dispatchEvent(new CustomEvent('show-toast', {
            detail: { type, message, duration }
        }));
    }
}

export default ToastProvider;
