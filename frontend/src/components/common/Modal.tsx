import React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../utils/cn';
import { Button } from './Button';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: string;
    children: React.ReactNode;
    className?: string;
    footer?: React.ReactNode;
    hideHeader?: boolean;
}

export function Modal({ isOpen, onClose, title, children, className, footer, hideHeader }: ModalProps) {
    if (!isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity animate-fade-in"
                onClick={onClose}
            />

            {/* Content */}
            <div
                className={cn(
                    "relative bg-midnight-900 border border-white/5 rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col z-10 animate-slide-up overflow-hidden",
                    className
                )}
            >
                {!hideHeader && (
                    <div className="flex items-center justify-between p-6 border-b border-white/5">
                        <h2 className="text-lg font-display font-medium text-white">{title}</h2>
                        <Button variant="ghost" size="icon" onClick={onClose} className="rounded-xl">
                            <X className="h-5 w-5" />
                        </Button>
                    </div>
                )}

                <div className={cn("p-6 overflow-y-auto flex-1 text-starlight-300", hideHeader && "p-0")}>
                    {children}
                </div>

                {footer && (
                    <div className="p-4 border-t border-dark-border bg-dark-bg-elevated/50 rounded-b-xl flex justify-end gap-2">
                        {footer}
                    </div>
                )}
            </div>
        </div>,
        document.body
    );
}
