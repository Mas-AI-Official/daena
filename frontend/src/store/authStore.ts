import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
    id: string;
    username: string;
    role: 'founder' | 'daena_vp' | 'agent' | 'viewer';
    permissions: string[];
}

interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    login: (token: string, user: User) => void;
    logout: () => void;
    checkPermission: (permission: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            isAuthenticated: false,

            login: (token, user) => set({
                token,
                user,
                isAuthenticated: true
            }),

            logout: () => {
                localStorage.removeItem('daena_token'); // Clear legacy if any
                set({ token: null, user: null, isAuthenticated: false });
            },

            checkPermission: (permission) => {
                const { user } = get();
                if (!user) return false;
                if (user.role === 'founder') return true; // Founder has all
                return user.permissions.includes(permission);
            }
        }),
        {
            name: 'daena-auth-storage',
        }
    )
);
