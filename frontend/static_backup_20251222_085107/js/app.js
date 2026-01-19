/**
 * Daena Core Application Logic
 */

const App = {
    state: {
        sidebarCollapsed: localStorage.getItem('daena_sidebar_collapsed') === 'true',
        operatorOpen: false,
    },

    init() {
        this.bindEvents();
        this.applySidebarState();
        console.log('Daena App Initialized');
    },

    bindEvents() {
        const sidebarToggle = document.getElementById('sidebar-toggle');
        if (sidebarToggle) sidebarToggle.addEventListener('click', () => this.toggleSidebar());

        const operatorToggle = document.getElementById('operator-toggle');
        if (operatorToggle) operatorToggle.addEventListener('click', () => this.toggleOperator());

        const closeOperator = document.getElementById('close-operator');
        if (closeOperator) closeOperator.addEventListener('click', () => this.toggleOperator(false));
    },

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
        localStorage.setItem('daena_sidebar_collapsed', this.state.sidebarCollapsed);
        this.applySidebarState();
    },

    applySidebarState() {
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.getElementById('main-content');
        const labels = document.querySelectorAll('.sidebar-label');
        const icon = document.getElementById('sidebar-toggle-icon');

        if (this.state.sidebarCollapsed) {
            sidebar.classList.add('w-20');
            sidebar.classList.remove('w-64');
            mainContent.classList.remove('ml-64');
            mainContent.classList.add('ml-20');
            labels.forEach(el => el.classList.add('hidden'));
            if (icon) icon.classList.add('rotate-180');
        } else {
            sidebar.classList.remove('w-20');
            sidebar.classList.add('w-64');
            mainContent.classList.remove('ml-20');
            mainContent.classList.add('ml-64');
            labels.forEach(el => el.classList.remove('hidden'));
            if (icon) icon.classList.remove('rotate-180');
        }
    },

    toggleOperator(forceState = null) {
        this.state.operatorOpen = forceState !== null ? forceState : !this.state.operatorOpen;
        const operatorPanel = document.getElementById('operator-panel');
        if (this.state.operatorOpen) {
            operatorPanel.classList.remove('translate-x-full');
        } else {
            operatorPanel.classList.add('translate-x-full');
        }
    },

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast ${type} text-sm text-white`;
        let icon = type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle';
        toast.innerHTML = `<i class="fas fa-${icon}"></i><span>${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
