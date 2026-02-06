import { useRef, useEffect, useState } from 'react';
import { Bot, User, Sparkles, BrainCircuit, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn';
import { motion, AnimatePresence } from 'framer-motion';

interface Message {
    id: string;
    sender: string;
    content: string;
    timestamp: string;
}

interface MessageListProps {
    messages: Message[];
    isTyping?: boolean;
}

function extractThinking(content: string): { thinking: string | null, cleanContent: string } {
    // Match multiple <think> tags or a single unclosed one
    const thinkingBlocks: string[] = [];
    let cleanContent = content;

    // Handle closed tags
    const closedRegex = /<think>([\s\S]*?)<\/think>/g;
    let match;
    while ((match = closedRegex.exec(content)) !== null) {
        thinkingBlocks.push(match[1].trim());
    }

    // Remove closed tags from cleanContent
    cleanContent = cleanContent.replace(/<think>([\s\S]*?)<\/think>/g, '').trim();

    // Handle unclosed tag at the end (for streaming or malformed responses)
    if (cleanContent.includes('<think>')) {
        const parts = cleanContent.split('<think>');
        const unclosed = parts.pop();
        thinkingBlocks.push(unclosed?.trim() || "");
        cleanContent = parts.join('<think>').trim();
    }

    return {
        thinking: thinkingBlocks.length > 0 ? thinkingBlocks.join('\n\n') : null,
        cleanContent: cleanContent
    };
}

function ThinkingBlock({ content }: { content: string }) {
    const [isOpen, setIsOpen] = useState(true); // Default to open for visibility

    return (
        <div className="mb-4 rounded-xl bg-midnight-950/40 border border-primary-500/20 overflow-hidden shadow-inner-glow group/think">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center gap-2 p-3 text-[10px] text-primary-400/70 hover:text-primary-300 hover:bg-white/5 transition-all font-mono uppercase tracking-[0.2em]"
            >
                <div className="relative">
                    <BrainCircuit className="w-3.5 h-3.5 animate-pulse-slow" />
                    <div className="absolute inset-0 bg-primary-400/20 blur-sm rounded-full animate-pulse" />
                </div>
                <span>Neural Reasoning Process</span>
                <div className="flex-1 h-[1px] bg-gradient-to-r from-primary-500/20 via-primary-500/5 to-transparent ml-2" />
                {isOpen ? <ChevronDown className="w-3 h-3 opacity-50" /> : <ChevronRight className="w-3 h-3 opacity-50" />}
            </button>
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ type: "spring", damping: 20, stiffness: 100 }}
                        className="overflow-hidden"
                    >
                        <div className="p-4 pt-1 text-[11px] text-starlight-400/90 font-mono leading-relaxed bg-midnight-950/20 border-t border-white/5 italic">
                            {content.split('\n').map((line, i) => (
                                <div key={i} className="mb-1.5 last:mb-0">
                                    <span className="opacity-30 mr-2">›</span>
                                    {line}
                                </div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

// Mini Orb Component (Local Definition)
function MiniOrb({ mode, playing = false }: { mode: 'daena' | 'autopilot', playing?: boolean }) {
    const isAutopilot = mode === 'autopilot';
    const primaryColor = isAutopilot ? "bg-orange-500" : "bg-primary-500";
    const borderColor = isAutopilot ? "border-orange-500" : "border-primary-500";

    return (
        <div className="relative w-5 h-5 flex items-center justify-center">
            {/* Core */}
            <motion.div
                animate={{
                    scale: playing ? [1, 1.2, 1] : 1,
                    opacity: playing ? [0.8, 1, 0.8] : 1
                }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                className={cn("w-2.5 h-2.5 rounded-full shadow-[0_0_8px_currentColor]", primaryColor, isAutopilot ? "text-orange-500" : "text-primary-500")}
            />

            {/* Outer Rings */}
            <motion.div
                animate={playing ? {
                    scale: [1, 1.5, 1],
                    opacity: [0.5, 0, 0.5]
                } : {
                    rotate: 360
                }}
                transition={playing ? {
                    duration: 1, repeat: Infinity, ease: "easeOut"
                } : {
                    duration: 4, repeat: Infinity, ease: "linear"
                }}
                className={cn("absolute inset-0 rounded-full border border-dashed opacity-40 scale-125", borderColor)}
            />
        </div>
    );
}

export function MessageList({ messages, isTyping }: MessageListProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll on new messages
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isTyping]);

    // Layout Fix: Ensure container is full height and handles scroll
    return (
        <div className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent p-6 space-y-8">
            <AnimatePresence initial={false}>
                {messages.map((msg) => (
                    <MessageItem key={msg.id} msg={msg} />
                ))}

                {isTyping && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex gap-3"
                    >
                        <div className="flex-shrink-0 w-10 h-10 rounded-2xl bg-primary-500/10 flex items-center justify-center border border-primary-500/20 shadow-glow-sm">
                            <MiniOrb mode="daena" playing={true} />
                        </div>
                        <div className="bg-midnight-200/50 p-4 rounded-2xl border border-white/5 flex gap-1.5 items-center">
                            <span className="text-xs text-primary-400 animate-pulse font-mono tracking-widest">THINKING...</span>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
            <div ref={bottomRef} className="h-4" />
        </div>
    );
}

function MessageItem({ msg }: { msg: Message }) {
    const isUser = msg.sender === 'user';
    const isSystem = msg.sender === 'system';
    const isAutopilot = msg.sender === 'autopilot';

    // Extract thinking process if present
    const { thinking, cleanContent } = !isUser ? extractThinking(msg.content) : { thinking: null, cleanContent: msg.content };

    if (isSystem) {
        return (
            <div className="flex justify-center my-6">
                <span className="text-[10px] bg-white/5 px-4 py-1.5 rounded-full text-starlight-300 border border-white/10 uppercase tracking-widest font-mono">
                    {msg.content}
                </span>
            </div>
        );
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                "flex w-full gap-4",
                isUser ? "flex-row-reverse" : "flex-row"
            )}
        >
            <div className={cn(
                "flex-shrink-0 w-10 h-10 rounded-2xl flex items-center justify-center shadow-lg border transition-all duration-300",
                isUser
                    ? "bg-midnight-200 border-white/10 text-starlight-200"
                    : isAutopilot
                        ? "bg-orange-500/10 border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.3)] animate-pulse-slow"
                        : "bg-primary-500/10 border-primary-500/20 shadow-glow-sm"
            )}>
                {isUser ? <User className="w-5 h-5" /> : <MiniOrb mode={isAutopilot ? 'autopilot' : 'daena'} playing={false} />}
            </div>

            <div className={cn(
                "max-w-[80%] flex flex-col",
                isUser ? "items-end" : "items-start"
            )}>
                <div className={cn(
                    "p-4 rounded-2xl shadow-2xl relative overflow-hidden group border",
                    isUser
                        ? "bg-midnight-200 border-white/10 text-starlight-100 rounded-tr-none"
                        : "bg-midnight-300/80 border-white/5 text-starlight-100 rounded-tl-none backdrop-blur-md",
                    isAutopilot && "border-orange-500/20 shadow-orange-500/5"
                )}>
                    {/* Ambient Glow for AI messages */}
                    {!isUser && (
                        <div className={cn(
                            "absolute top-0 left-0 w-full h-[1px]",
                            isAutopilot
                                ? "bg-gradient-to-r from-transparent via-orange-400/30 to-transparent"
                                : "bg-gradient-to-r from-transparent via-primary-400/30 to-transparent"
                        )} />
                    )}

                    {/* Thinking Block */}
                    {thinking && <ThinkingBlock content={thinking} />}

                    <div className="text-sm leading-relaxed whitespace-pre-wrap relative z-10 text-shadow-sm">{cleanContent}</div>
                </div>

                <div className={cn(
                    "text-[10px] mt-2 opacity-40 font-mono uppercase tracking-tighter",
                    isUser ? "text-starlight-400" : isAutopilot ? "text-orange-400" : "text-primary-400"
                )}>
                    {isAutopilot && <span className="mr-2 border border-orange-500/30 px-1 rounded text-[8px]">AUTOPILOT_ENGAGED</span>}
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>
            </div>
        </motion.div>
    );
}
