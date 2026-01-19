/**
 * Toast Notification System
 * Provides non-intrusive notifications for real-time events
 */

class ToastManager {
    constructor() {
        this.toasts = [];
        this.container = null;
        this.maxToasts = 5;
        this.defaultDuration = 3000;
        this.init();
    }

    init() {
        // Create toast container
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className = 'toast-container';
        this.container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 10px;
            pointer-events: none;
        `;
        document.body.appendChild(this.container);
    }

    show(message, type = 'info', duration = null) {
        const toast = this.createToast(message, type);
        this.container.appendChild(toast);
        this.toasts.push(toast);

        // Remove oldest if limit reached
        if (this.toasts.length > this.maxToasts) {
            const oldest = this.toasts.shift();
            oldest.remove();
        }

        // Animate in
        setTimeout(() => {
            toast.classList.add('toast-visible');
        }, 10);

        // Auto-remove
        const removeDelay = duration || this.defaultDuration;
        setTimeout(() => {
            this.remove(toast);
        }, removeDelay);

        return toast;
    }

    createToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            background: rgba(26, 26, 46, 0.95);
            border: 1px solid rgba(255, 215, 0, 0.3);
            border-radius: 8px;
            padding: 12px 16px;
            min-width: 300px;
            max-width: 400px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            pointer-events: auto;
            cursor: pointer;
            transform: translateX(400px);
            opacity: 0;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 12px;
        `;

        const icon = this.getIcon(type);
        const colors = this.getColors(type);

        toast.innerHTML = `
            <div style="font-size: 20px;">${icon}</div>
            <div style="flex: 1;">
                <div style="font-weight: 500; color: ${colors.text}; margin-bottom: 4px;">${this.getTitle(type)}</div>
                <div style="font-size: 14px; color: rgba(255, 255, 255, 0.8);">${message}</div>
            </div>
            <button class="toast-close" style="
                background: none;
                border: none;
                color: rgba(255, 255, 255, 0.5);
                cursor: pointer;
                font-size: 18px;
                padding: 0;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
            " onclick="this.closest('.toast').remove()">×</button>
        `;

        toast.addEventListener('click', () => {
            this.remove(toast);
        });

        return toast;
    }

    getIcon(type) {
        const icons = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️',
            'websocket': '🔌',
            'message': '💬',
            'connection': '🔗'
        };
        return icons[type] || icons.info;
    }

    getTitle(type) {
        const titles = {
            'success': 'Success',
            'error': 'Error',
            'warning': 'Warning',
            'info': 'Info',
            'websocket': 'WebSocket',
            'message': 'New Message',
            'connection': 'Connection'
        };
        return titles[type] || 'Notification';
    }

    getColors(type) {
        const colors = {
            'success': { text: '#4ade80', border: '#22c55e' },
            'error': { text: '#f87171', border: '#ef4444' },
            'warning': { text: '#fbbf24', border: '#f59e0b' },
            'info': { text: '#60a5fa', border: '#3b82f6' },
            'websocket': { text: '#ffd700', border: '#ffd700' },
            'message': { text: '#a78bfa', border: '#8b5cf6' },
            'connection': { text: '#34d399', border: '#10b981' }
        };
        return colors[type] || colors.info;
    }

    remove(toast) {
        toast.classList.remove('toast-visible');
        toast.style.transform = 'translateX(400px)';
        toast.style.opacity = '0';
        setTimeout(() => {
            toast.remove();
            const index = this.toasts.indexOf(toast);
            if (index > -1) {
                this.toasts.splice(index, 1);
            }
        }, 300);
    }

    success(message, duration = null) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = null) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration = null) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = null) {
        return this.show(message, 'info', duration);
    }
}

// Add CSS for toast animations
const toastStyle = document.createElement('style');
toastStyle.textContent = `
    .toast-visible {
        transform: translateX(0) !important;
        opacity: 1 !important;
    }
    .toast-close:hover {
        color: rgba(255, 255, 255, 0.9) !important;
    }
`;
document.head.appendChild(toastStyle);

// Global toast manager instance
window.ToastManager = new ToastManager();
window.toast = window.ToastManager;

console.log('✅ Toast Notification System initialized');



