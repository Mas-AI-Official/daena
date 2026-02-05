import { useState, useRef, type KeyboardEvent } from 'react';
import { Send, Loader2, Mic, MicOff } from 'lucide-react';
import { Button } from '../common/Button';
import { cn } from '../../utils/cn';
import { useVoiceControl } from '../../hooks/useVoiceControl';

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
    const [value, setValue] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const { isListening, toggleListening, hasSupport } = useVoiceControl({
        onCommand: (text) => {
            setValue(prev => prev ? `${prev} ${text}` : text);
        }
    });

    const handleSend = () => {
        if (value.trim() && !disabled) {
            onSend(value);
            setValue('');
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setValue(e.target.value);
        e.target.style.height = 'auto';
        e.target.style.height = `${Math.min(e.target.scrollHeight, 150)}px`;
    };

    return (
        <div className="w-full">
            <div className="relative flex gap-2 items-end">
                {/* Voice Button */}
                {hasSupport && (
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={toggleListening}
                        className={cn(
                            "h-[44px] w-[44px] rounded-xl mb-0.5 transition-all duration-300",
                            isListening
                                ? "text-status-error bg-status-error/10 animate-pulse"
                                : "text-starlight-300 hover:text-primary-400 hover:bg-primary-500/10"
                        )}
                        disabled={disabled}
                    >
                        {isListening ? <MicOff className="w-5 h-5 shadow-glow-error" /> : <Mic className="w-5 h-5" />}
                    </Button>
                )}

                <div className="flex-1 relative">
                    <textarea
                        ref={textareaRef}
                        value={value}
                        onChange={handleChange}
                        onKeyDown={handleKeyDown}
                        placeholder={isListening ? "Listening..." : "Type your message to Daena..."}
                        disabled={disabled}
                        rows={1}
                        className={cn(
                            "w-full min-h-[44px] max-h-[200px] resize-none rounded-xl border border-white/10 bg-midnight-200/50 px-4 py-3 text-sm text-starlight-100 placeholder:text-starlight-300 focus:outline-none focus:ring-1 focus:ring-primary-500/50 focus:bg-midnight-200/80 transition-all shadow-inner disabled:opacity-50 scrollbar-hide",
                            isListening && "border-status-error/30 ring-status-error/20"
                        )}
                    />
                    {isListening && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex gap-1">
                            <span className="w-1 h-3 rounded-full bg-status-error animate-wave-1" />
                            <span className="w-1 h-3 rounded-full bg-status-error animate-wave-2" />
                            <span className="w-1 h-3 rounded-full bg-status-error animate-wave-3" />
                        </div>
                    )}
                </div>

                <Button
                    size="icon"
                    variant={value.trim() ? "primary" : "secondary"}
                    onClick={handleSend}
                    disabled={!value.trim() || disabled}
                    className={cn(
                        "h-[44px] w-[44px] rounded-xl flex-shrink-0 transition-all duration-300",
                        value.trim() && "shadow-glow-md scale-105"
                    )}
                >
                    {disabled ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </Button>
            </div>

            <div className="text-center mt-3">
                <p className="text-[10px] text-starlight-300/60 font-medium flex items-center justify-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-primary-500" />
                    Daena AI v2.5 • Authorized Access Only
                    <span className="w-1 h-1 rounded-full bg-primary-500" />
                </p>
            </div>
        </div>
    );
}
