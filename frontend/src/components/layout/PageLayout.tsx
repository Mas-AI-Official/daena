
import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useUIStore } from '../../store/uiStore';
import { Menu } from 'lucide-react';
import { cn } from '../../utils/cn';

export function PageLayout() {
    const { sidebarOpen, toggleSidebar } = useUIStore();
    const location = useLocation();
    const isChat = location.pathname.startsWith('/chat');

    return (
        <div className="flex h-screen bg-[#0A0E1A] text-white overflow-hidden font-sans selection:bg-primary-500/30">
            {/* Modular Sidebar */}
            <Sidebar />

            {/* Main Content */}
            <main
                className={cn(
                    "flex-1 flex flex-col min-w-0 overflow-hidden relative transition-all duration-300 ease-in-out",
                    sidebarOpen ? "ml-64" : "ml-20",
                    // On mobile, the sidebar is fixed/overlay, so margin might be different OR handled by media queries.
                    // For this premium desktop-first app, we'll assume the responsive behavior defined here:
                    "max-md:ml-0"
                )}
            >
                {/* Header */}
                <Header />

                {/* Scrollable Area */}
                <div className={cn(
                    "flex-1 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent flex flex-col",
                    isChat ? "overflow-hidden" : "overflow-y-auto p-6 md:p-8"
                )}>
                    <div className={cn(
                        "w-full h-full flex flex-col animate-fade-in",
                        !isChat && "space-y-8 pb-8"
                    )}>
                        <Outlet />
                    </div>
                </div>
            </main>
        </div>
    );
}
