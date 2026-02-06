import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface Message {
    id: string;
    sender: 'user' | 'daena' | 'system' | 'agent' | 'assistant' | 'autopilot';
    content: string;
    timestamp: string;
    metadata?: any;
}

interface ChatState {
    messages: Message[];
    addMessage: (msg: Message) => void;
    setMessages: (msgs: Message[]) => void;
    clearMessages: () => void;
    sessionId: string | null;
    setSessionId: (id: string) => void;
}

export const useChatStore = create<ChatState>()(
    persist(
        (set) => ({
            messages: [],
            addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
            setMessages: (msgs) => set({ messages: msgs }),
            clearMessages: () => set({ messages: [] }),
            sessionId: null,
            setSessionId: (id) => set({ sessionId: id }),
        }),
        {
            name: 'daena-chat-storage',
        }
    )
);
