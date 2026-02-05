
import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useUIStore } from '../../store/uiStore';
import { Menu } from 'lucide-react';
import { cn } from '../../utils/cn';

export function PageLayout() {
    const { sidebarOpen, toggleSidebar } = useUIStore();

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
                {/* Mobile Header (Only visible on small screens) */}
                <header className="md:hidden flex items-center h-16 px-6 border-b border-white/5 bg-[#0A0E1A]">
                    <button onClick={toggleSidebar} className="text-starlight-300 mr-4">
                        <Menu className="w-6 h-6" />
                    </button>
                    <span className="font-display font-bold text-lg">DAENA OS</span>
                </header>

                {/* Scrollable Area */}
                <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 md:p-8 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                    <div className="max-w-[1920px] mx-auto space-y-8 animate-fade-in pb-20">
                        <Outlet />
                    </div>
                </div>
            </main>
        </div>
    );
}
