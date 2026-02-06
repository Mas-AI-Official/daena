import { useEffect, useState, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { v4 as uuidv4 } from 'uuid';
import { wsService } from '../../services/websocket';
import { ChatHistorySidebar } from './ChatHistorySidebar';
import { useChatStore } from '../../store/chatStore';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { Wifi, WifiOff, Sparkles } from 'lucide-react';
import { cn } from '../../utils/cn';
import { useUIStore } from '../../store/uiStore';
import api from '../../services/api/client';
import { motion, AnimatePresence } from 'framer-motion';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial, Float, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import { Menu, PanelLeft, PanelLeftClose } from 'lucide-react';

// function CoreSphere removed per user request

// Neural Hero Background Component
function NeuralHero({ active, mode }: { active: boolean, mode: 'daena' | 'autopilot' }) {
    const isAutopilot = mode === 'autopilot';
    const primaryColor = isAutopilot ? "bg-orange-500" : "bg-primary-500";
    const borderColor = isAutopilot ? "border-orange-500" : "border-primary-500";
    const textColor = isAutopilot ? "text-orange-500" : "text-primary-500";
    const shadowColor = isAutopilot ? "shadow-orange-500/20" : "shadow-primary-500/20";

    return (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden z-0">
            <AnimatePresence>
                {!active && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 1.1, filter: "blur(10px)" }}
                        transition={{ duration: 0.8, ease: "easeInOut" }}
                        className="flex flex-col items-center justify-center relative"
                    >
                        {/* Core Orb */}
                        <div className="relative w-64 h-64 flex items-center justify-center">
                            {/* Outer rotating ring */}
                            <motion.div
                                animate={{ rotate: 360 }}
                                transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
                                className={cn("absolute inset-0 rounded-full border border-dashed opacity-20", borderColor)}
                            />

                            {/* Inner rotating ring */}
                            <motion.div
                                animate={{ rotate: -360 }}
                                transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                                className={cn("absolute inset-8 rounded-full border opacity-30", borderColor)}
                            />

                            {/* Glow */}
                            <div className={cn("absolute inset-0 rounded-full blur-[80px] opacity-20", primaryColor)} />

                            {/* Center Sphere */}
                            <div className={cn("w-32 h-32 rounded-full shadow-2xl backdrop-blur-sm border flex items-center justify-center relative overflow-hidden", borderColor, "bg-midnight-900/50")}>
                                <div className={cn("absolute inset-0 opacity-10 animate-pulse", primaryColor)} />
                                <div className={cn("w-2 h-2 rounded-full shadow-[0_0_20px_currentColor]", primaryColor, textColor)} />
                            </div>
                        </div>

                        {/* Text */}
                        <div className="mt-12 text-center space-y-2">
                            <motion.h1
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.2 }}
                                className="text-3xl font-display font-bold tracking-widest text-white"
                            >
                                {mode === 'autopilot' ? 'NEURAL AUTO' : 'NEURAL COMMAND'}
                            </motion.h1>
                            <motion.p
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 0.6 }}
                                transition={{ delay: 0.4 }}
                                className={cn("text-[10px] font-mono uppercase tracking-[0.5em]", textColor)}
                            >
                                Secure Interface Ready
                            </motion.p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Ambient Watermark when active */}
            <motion.div
                animate={{ opacity: active ? 0.05 : 0 }}
                transition={{ duration: 1 }}
                className={cn("absolute w-[800px] h-[800px] rounded-full blur-[150px]", primaryColor)}
            />
        </div>
    );
}

function MiniOrb({ mode }: { mode: 'daena' | 'autopilot' }) {
    const isAutopilot = mode === 'autopilot';
    const primaryColor = isAutopilot ? "bg-orange-500" : "bg-primary-500";
    const borderColor = isAutopilot ? "border-orange-500" : "border-primary-500";

    return (
        <div className="relative w-5 h-5 flex items-center justify-center">
            <div className={cn("absolute inset-0 rounded-full opacity-20 animate-pulse", primaryColor)} />
            <div className={cn("w-2.5 h-2.5 rounded-full shadow-[0_0_8px_currentColor]", primaryColor, isAutopilot ? "text-orange-500" : "text-primary-500")} />
            {/* Rotating ring */}
            <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                className={cn("absolute inset-0 rounded-full border border-dashed opacity-40 scale-125", borderColor)}
            />
        </div>
    );
}

interface ChatInterfaceProps {
    scope?: 'executive' | 'department' | 'agent';
    scopeId?: string;
    title?: string;
    className?: string;
}

export function ChatInterface({ scope = 'executive', scopeId = 'daena', title, className }: ChatInterfaceProps) {
    const { messages, addMessage, sessionId, setSessionId, setMessages } = useChatStore();
    const { historySidebarOpen, setHistorySidebarOpen } = useUIStore();
    const [searchParams] = useSearchParams();
    const [isTyping, setIsTyping] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [mode, setMode] = useState<'daena' | 'autopilot'>('daena');

    // Initial setup and reacting to query params
    useEffect(() => {
        const sessionParam = searchParams.get('session');
        if (sessionParam && sessionParam !== sessionId) {
            setSessionId(sessionParam);
            if (setMessages) setMessages([]);
        } else if (!sessionId && !sessionParam) {
            setSessionId(uuidv4());
        }
    }, [searchParams, sessionId, setSessionId, setMessages]);

    // WebSocket and History loading
    useEffect(() => {
        if (!sessionId) return;

        wsService.connect();
        setIsConnected(true); // Assuming connection for UI state

        // Fetch history for the current session
        api.get(`/daena/chat/history/${sessionId}`)
            .then(res => {
                if (res.data.messages && setMessages) {
                    const mappedMessages = res.data.messages.map((msg: any) => ({
                        id: msg.id || uuidv4(),
                        sender: msg.role === 'user' ? 'user' : 'daena',
                        content: msg.content,
                        timestamp: msg.created_at
                    }));
                    setMessages(mappedMessages);
                }
            })
            .catch(err => {
                console.log('No history or failed to fetch', err);
                if (setMessages) setMessages([]);
            });

        // Setup WS listeners if needed
        // wsService.on('message', ...)
    }, [sessionId, setMessages]);

    const handleSend = async (text: string) => {
        const userMsg = {
            id: uuidv4(),
            sender: 'user' as const,
            content: text,
            timestamp: new Date().toISOString()
        };
        addMessage(userMsg);
        setIsTyping(true);

        try {
            let endpoint = '/daena/chat';
            let payload: any = {
                message: text,
                session_id: sessionId,
                mode: mode === 'autopilot' ? 'aggressive' : 'standard' // map to backend mode
            };

            if (scope === 'department') {
                endpoint = `/departments/${scopeId}/chat`;
            } else if (scope === 'agent') {
                endpoint = `/agents/${scopeId}/chat`;
            }

            const response = await api.post(endpoint, payload);

            if (response.data && response.data.response) {
                addMessage({
                    id: uuidv4(),
                    sender: mode === 'autopilot' ? 'autopilot' : 'daena',
                    content: response.data.response,
                    timestamp: new Date().toISOString()
                });
            }
        } catch (err) {
            console.error('Chat error:', err);
        } finally {
            setIsTyping(false);
        }
    };

    return (
        <div className={cn("flex flex-1 overflow-hidden h-full gap-4 transition-all duration-300 px-6 pt-28 pb-2", className)}>
            {/* Sidebar for Executive Scope */}
            {scope === 'executive' && (
                <div className={cn(
                    "shrink-0 hidden md:block rounded-2xl overflow-hidden border border-white/5 shadow-2xl transition-all duration-300 h-full",
                    historySidebarOpen ? "w-80" : "w-16"
                )}>
                    <ChatHistorySidebar />
                </div>
            )}

            {/* Main Chat Area - Updated for layout fix */}
            <div className="flex-1 flex flex-col bg-midnight-300/50 rounded-2xl border border-white/5 overflow-hidden backdrop-blur-sm relative h-full shadow-2xl">

                {/* Background Hero */}
                <NeuralHero active={messages.length > 0 || isTyping} mode={mode} />

                {/* Status Bar */}
                <div className="h-12 border-b border-white/5 px-6 flex items-center justify-between bg-midnight-400/30 z-10 relative">
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => setHistorySidebarOpen(!historySidebarOpen)}
                            className="p-1 px-2 text-gray-400 hover:text-white transition-colors"
                        >
                            {historySidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
                        </button>
                        <div className="p-1 px-2 rounded-md bg-primary-500/10 border border-primary-500/20 flex items-center gap-2">
                            <MiniOrb mode={mode} />
                            <span className="text-[10px] font-bold text-primary-400 uppercase tracking-widest">
                                {title || (scope === 'executive' ? 'Executive Neural Link' : `${scopeId} Channel`)}
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        {/* Neural Mode Toggle */}
                        <div className="flex items-center gap-3">
                            <div className="hidden md:flex flex-col items-end mr-2">
                                <span className={cn(
                                    "text-[9px] uppercase tracking-widest font-bold",
                                    mode === 'autopilot' ? "text-orange-400" : "text-primary-400"
                                )}>
                                    {mode === 'autopilot' ? 'NEURAL AUTO' : 'NEURAL COMMAND'}
                                </span>
                                {isTyping && (
                                    <span className="text-[8px] text-starlight-400 animate-pulse">Processing...</span>
                                )}
                            </div>

                            <div className="flex bg-midnight-950/50 p-0.5 rounded-lg border border-white/5 relative">
                                <motion.div
                                    layout
                                    className={cn(
                                        "absolute top-0.5 bottom-0.5 w-[50%] rounded-md shadow-sm",
                                        mode === 'autopilot' ? "bg-orange-500/20 border border-orange-500/30 left-[50%] right-0.5" : "bg-primary-500/20 border border-primary-500/30 left-0.5 right-[50%]"
                                    )}
                                />
                                <button
                                    onClick={() => setMode('daena')}
                                    className={cn(
                                        "relative z-10 px-3 py-1.5 rounded-md text-[9px] uppercase tracking-wider font-bold transition-colors w-20",
                                        mode === 'daena' ? "text-primary-300" : "text-starlight-500 hover:text-starlight-300"
                                    )}
                                >
                                    Exec
                                </button>
                                <button
                                    onClick={() => setMode('autopilot')}
                                    className={cn(
                                        "relative z-10 px-3 py-1.5 rounded-md text-[9px] uppercase tracking-wider font-bold transition-colors w-20",
                                        mode === 'autopilot' ? "text-orange-300" : "text-starlight-500 hover:text-starlight-300"
                                    )}
                                >
                                    Auto
                                </button>
                            </div>
                        </div>

                        <div className="flex items-center gap-2 text-[10px] font-mono text-starlight-400">
                            {isConnected ? (
                                <>
                                    <Wifi className="w-3 h-3 text-status-success" />
                                    <span className="text-status-success uppercase">Synced</span>
                                </>
                            ) : (
                                <>
                                    <WifiOff className="w-3 h-3 text-status-error" />
                                    <span className="text-status-error uppercase">Reconnecting</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-hidden relative flex flex-col z-10 min-h-0">
                    <MessageList
                        messages={messages}
                        isTyping={isTyping}
                    />
                </div>

                {/* Input */}
                <div className="shrink-0 p-4 bg-midnight-950/20 border-t border-white/5 backdrop-blur-md z-10 relative">
                    <ChatInput onSend={handleSend} disabled={!isConnected} />
                </div>
            </div>

            {/* Ambient Glow */}
            <div className="absolute -bottom-24 left-1/2 -translate-x-1/2 w-3/4 h-48 bg-primary-500/5 blur-[100px] pointer-events-none rounded-full" />
        </div>
    );
}
