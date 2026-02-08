import React from 'react';
import { X, AlertTriangle, Info } from 'lucide-react';
import { cn } from '../../utils/cn';
import { LoadingButton } from './LoadingButton';

interface ConfirmationModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void | Promise<void>;
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    isDanger?: boolean;
    isLoading?: boolean;
}

export function ConfirmationModal({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    isDanger = false,
    isLoading = false
}: ConfirmationModalProps) {
    if (!isOpen) return null;

    const handleConfirm = async () => {
        await onConfirm();
        if (!isLoading) {
            onClose();
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative bg-midnight-900 border border-white/10 rounded-xl shadow-2xl max-w-md w-full mx-4 animate-fade-in-up">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        {isDanger ? (
                            <div className="p-2 rounded-lg bg-red-500/10">
                                <AlertTriangle className="w-5 h-5 text-red-400" />
                            </div>
                        ) : (
                            <div className="p-2 rounded-lg bg-primary-500/10">
                                <Info className="w-5 h-5 text-primary-400" />
                            </div>
                        )}
                        <h3 className="text-lg font-semibold text-white">{title}</h3>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1 rounded-lg hover:bg-white/5 text-starlight-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-4">
                    <p className="text-starlight-300 leading-relaxed">{message}</p>
                </div>

                {/* Footer */}
                <div className="flex justify-end gap-3 p-4 border-t border-white/10">
                    <button
                        onClick={onClose}
                        disabled={isLoading}
                        className="px-4 py-2 text-sm font-medium rounded-lg bg-midnight-200 hover:bg-midnight-300 text-starlight-100 border border-white/10 transition-colors disabled:opacity-50"
                    >
                        {cancelText}
                    </button>
                    <LoadingButton
                        onClick={handleConfirm}
                        isLoading={isLoading}
                        variant={isDanger ? 'danger' : 'primary'}
                        loadingText="Processing..."
                    >
                        {confirmText}
                    </LoadingButton>
                </div>
            </div>
        </div>
    );
}

export default ConfirmationModal;
