import { create } from 'zustand';

interface Notification {
    id: string;
    type: 'info' | 'success' | 'warning' | 'error';
    title: string;
    message: string;
    duration?: number;
}

interface UIState {
    sidebarOpen: boolean;
    historySidebarOpen: boolean;
    toggleSidebar: () => void;
    toggleHistorySidebar: () => void;
    setSidebarOpen: (open: boolean) => void;
    setHistorySidebarOpen: (open: boolean) => void;

    notifications: Notification[];
    addNotification: (notification: Omit<Notification, 'id'>) => void;
    removeNotification: (id: string) => void;

    theme: 'dark' | 'light'; // Forced dark for now, but kept structure
}

export const useUIStore = create<UIState>((set, get) => ({
    sidebarOpen: true,
    historySidebarOpen: true,
    toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    toggleHistorySidebar: () => set((state) => ({ historySidebarOpen: !state.historySidebarOpen })),
    setSidebarOpen: (open) => set({ sidebarOpen: open }),
    setHistorySidebarOpen: (open) => set({ historySidebarOpen: open }),

    notifications: [],
    addNotification: (notification) => {
        const id = Math.random().toString(36).substring(7);
        const newNotification = { ...notification, id };

        set((state) => ({ notifications: [...state.notifications, newNotification] }));

        if (notification.duration !== 0) {
            setTimeout(() => {
                get().removeNotification(id);
            }, notification.duration || 5000);
        }
    },
    removeNotification: (id) => set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== id)
    })),

    theme: 'dark'
}));
