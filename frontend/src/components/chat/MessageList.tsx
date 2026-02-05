import { useRef, useEffect } from 'react';
import { Bot, User, Sparkles } from 'lucide-react';
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

export function MessageList({ messages, isTyping }: MessageListProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isTyping]);

    if (messages.length === 0 && !isTyping) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-starlight-300 opacity-30 space-y-6 select-none">
                <div className="p-6 rounded-full bg-midnight-200 border border-white/5 animate-float">
                    <Bot className="w-16 h-16" />
                </div>
                <div className="text-center">
                    <p className="text-lg font-display font-medium text-white mb-2">Daena Executive Node</p>
                    <p className="text-sm">Secure link established. Awaiting directives.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-8">
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
                            <Sparkles className="w-5 h-5 text-primary-400 animate-pulse" />
                        </div>
                        <div className="bg-midnight-200/50 p-4 rounded-2xl border border-white/5 flex gap-1.5 items-center">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce" />
                            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce delay-150" />
                            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-bounce delay-300" />
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
                    : "bg-primary-500/10 border-primary-500/20 text-primary-500 shadow-glow-sm"
            )}>
                {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
            </div>

            <div className={cn(
                "max-w-[80%] flex flex-col",
                isUser ? "items-end" : "items-start"
            )}>
                <div className={cn(
                    "p-4 rounded-2xl shadow-2xl relative overflow-hidden group border",
                    isUser
                        ? "bg-midnight-200 border-white/10 text-starlight-100 rounded-tr-none"
                        : "bg-midnight-300/80 border-white/5 text-starlight-100 rounded-tl-none backdrop-blur-md"
                )}>
                    {/* Ambient Glow for AI messages */}
                    {!isUser && (
                        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-primary-400/30 to-transparent" />
                    )}

                    <div className="text-sm leading-relaxed whitespace-pre-wrap relative z-10 text-shadow-sm">{msg.content}</div>
                </div>

                <div className={cn(
                    "text-[10px] mt-2 opacity-40 font-mono uppercase tracking-tighter",
                    isUser ? "text-starlight-400" : "text-primary-400"
                )}>
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </div>
            </div>
        </motion.div>
    );
}
