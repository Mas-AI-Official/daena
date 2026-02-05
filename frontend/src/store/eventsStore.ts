import { create } from 'zustand';

interface SystemEvent {
    id: string;
    type: string;
    payload: any;
    timestamp: string;
}

interface EventsState {
    events: SystemEvent[];
    isConnected: boolean;
    addEvent: (event: SystemEvent) => void;
    setConnected: (connected: boolean) => void;
    clearEvents: () => void;
}

export const useEventsStore = create<EventsState>((set) => ({
    events: [],
    isConnected: false,

    addEvent: (event) => set((state) => ({
        events: [event, ...state.events].slice(0, 100) // Keep last 100
    })),

    setConnected: (connected) => set({ isConnected: connected }),

    clearEvents: () => set({ events: [] })
}));
