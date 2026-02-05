import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useChatStore } from '../../store/chatStore';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { ToolTimeline } from './ToolTimeline';
import { Wifi, WifiOff, Sparkles } from 'lucide-react';
import { cn } from '../../utils/cn';
import api from '../../services/api/client';

interface ChatInterfaceProps {
    scope?: 'executive' | 'department' | 'agent';
    scopeId?: string;
    title?: string;
    className?: string; // Allow external styling
}

export function ChatInterface({ scope = 'executive', scopeId = 'daena', title, className }: ChatInterfaceProps) {
    const { messages, addMessage, sessionId, setSessionId } = useChatStore();
    const [isTyping, setIsTyping] = useState(false);

    useEffect(() => {
        if (!sessionId) {
            setSessionId(uuidv4());
        }
    }, [sessionId, setSessionId]);

    const wsUrl = sessionId ? `/ws/chat/${sessionId}` : '';
    const { isConnected } = useWebSocket({
        url: wsUrl,
        onMessage: (data) => {
            if (data.event_type === 'chat.message') {
                // If message is from 'user' but we already showed it optimistically, we might get a dupe.
                // The backend repeats 'user' messages.
                // Since this is a simple implementation, we ignore 'user' messages from WS for now
                // relying on optimism. In a real app we'd match IDs.

                const sender = data.payload?.sender || (data as any).sender;
                const content = data.payload?.content || (data as any).content;

                if (sender !== 'user') {
                    setIsTyping(false);
                    addMessage({
                        id: uuidv4(),
                        sender: sender === 'daena' ? 'daena' : 'assistant',
                        content: content,
                        timestamp: new Date().toISOString()
                    });
                }
            } else if (data.event_type === 'typing') {
                setIsTyping(true);
            }
        }
    });

    const handleSend = async (text: string) => {
        addMessage({
            id: uuidv4(),
            sender: 'user',
            content: text,
            timestamp: new Date().toISOString()
        });
        setIsTyping(true);

        try {
            if (scope === 'executive') {
                await api.post('/daena/chat', { message: text, session_id: sessionId });
            } else if (scope === 'department' && scopeId) {
                await api.post(`/departments/${scopeId}/chat`, { message: text, context: { session_id: sessionId } });
            } else if (scope === 'agent' && scopeId) {
                // Assuming scopeId format "dept:agent" or just "agent" if handled by router
                // If it's a direct agent chat route:
                await api.post(`/agents/${scopeId}/chat`, { message: text, context: { session_id: sessionId } });
            }
        } catch (error) {
            console.error('Failed to send message:', error);
            addMessage({
                id: uuidv4(),
                sender: 'system',
                content: 'Failed to establish neural link. Message dropped.',
                timestamp: new Date().toISOString()
            });
            setIsTyping(false);
        }
    };

    return (
        <div className={cn("flex flex-col h-[calc(100vh-140px)] bg-midnight-200/50 rounded-2xl border border-white/5 relative overflow-hidden shadow-2xl backdrop-blur-sm", className)}>
            {/* Ambient Background */}
            <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-primary-600/5 to-transparent opacity-50" />

            {/* Header */}
            <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5 backdrop-blur-md z-10 shrink-0">
                <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary-600 to-primary-400 flex items-center justify-center shadow-glow-sm">
                        <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <div>
                        <h3 className="font-display font-medium text-white text-sm">{title || "Daena Executive Link"}</h3>
                        <p className="text-[10px] text-starlight-300 font-mono tracking-wider uppercase">Secure Channel • Encrypted</p>
                    </div>
                </div>

                <div className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-300",
                    isConnected
                        ? "bg-status-success/10 text-status-success border-status-success/20 shadow-glow-success"
                        : "bg-status-error/10 text-status-error border-status-error/20"
                )}>
                    {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                    <span className="hidden sm:inline">{isConnected ? "Neural Link Active" : "Link Severed"}</span>
                </div>
            </div>

            {/* Messages Area - Grow to fill space */}
            <div className="flex-1 overflow-y-auto relative z-0 p-4 space-y-4">
                <MessageList messages={messages} isTyping={isTyping} />
            </div>

            {/* Neural Operations Timeline (Optional - can be collapsible) */}
            {/* <ToolTimeline /> */}

            {/* Input Area - Fixed at bottom */}
            <div className="p-4 bg-white/5 border-t border-white/5 relative z-10 shrink-0">
                <ChatInput onSend={handleSend} disabled={!isConnected} />
                <div className="flex justify-center mt-2">
                    <p className="text-[10px] text-starlight-500 font-mono">Daena AI v2.5 • Authorized Access Only</p>
                </div>
            </div>
        </div>
    );
}
