/**
 * UI Components Library
 * Standardized loading states, error messages, and connection indicators
 */

const UIComponents = {
    // Connection Status Indicator
    createConnectionIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'ws-connection-indicator';
        indicator.className = 'connection-indicator disconnected';
        indicator.innerHTML = `
            <div class="indicator-dot"></div>
            <span id="ws-status-text">Connecting...</span>
            <span id="ws-latency" style="font-size: 11px; opacity: 0.7; margin-left: 8px;"></span>
        `;

        // Add CSS if not already present
        if (!document.getElementById('ui-components-styles')) {
            const style = document.createElement('style');
            style.id = 'ui-components-styles';
            style.textContent = `
                .connection-indicator {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    background: rgba(0, 0, 0, 0.8);
                    backdrop-filter: blur(10px);
                    padding: 8px 16px;
                    border-radius: 20px;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 12px;
                    color: white;
                    z-index: 9999;
                    border: 1px solid rgba(255,255,255,0.1);
                }
                
                .indicator-dot {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #666;
                    animation: pulse 2s infinite;
                }
                
                .connection-indicator.connected .indicator-dot {
                    background: #22C55E;
                }
                
                .connection-indicator.disconnected .indicator-dot {
                    background: #EF4444;
                }
                
                .connection-indicator.error .indicator-dot {
                    background: #F59E0B;
                }
                
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                
                .loading-spinner {
                    display: inline-block;
                    width: 20px;
                    height: 20px;
                    border: 2px solid rgba(255,255,255,0.3);
                    border-radius: 50%;
                    border-top-color: var(--daena-gold, #FFD700);
                    animation: spin 0.8s linear infinite;
                }
                
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                
                .error-message {
                    background: rgba(239, 68, 68, 0.1);
                    border: 1px solid #EF4444;
                    color: #FEE2E2;
                    padding: 12px 16px;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin: 16px 0;
                }
                
                .success-message {
                    background: rgba(34, 197, 94, 0.1);
                    border: 1px solid #22C55E;
                    color: #D1FAE5;
                    padding: 12px 16px;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin: 16px 0;
                }
                
                .loading-state {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 40px;
                    color: #9CA3AF;
                }
                
                .empty-state {
                    text-align: center;
                    padding: 60px 20px;
                    color: #6B7280;
                }
                
                .empty-state-icon {
                    font-size: 48px;
                    opacity: 0.3;
                    margin-bottom: 16px;
                }
            `;
            document.head.appendChild(style);
        }

        return indicator;
    },

    // Loading Spinner
    createLoadingSpinner(text = 'Loading...') {
        const container = document.createElement('div');
        container.className = 'loading-state';
        container.innerHTML = `
            <div class="loading-spinner"></div>
            <p style="margin-top: 16px;">${text}</p>
        `;
        return container;
    },

    // Error Message
    createErrorMessage(message, onRetry = null) {
        const container = document.createElement('div');
        container.className = 'error-message';
        container.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
            ${onRetry ? '<button onclick="this.parentElement.retryFn()" style="margin-left: auto; padding: 6px 12px; background: transparent; border: 1px solid #EF4444; color: #FEE2E2; border-radius: 4px; cursor: pointer;">Retry</button>' : ''}
        `;
        if (onRetry) {
            container.retryFn = onRetry;
        }
        return container;
    },

    // Success Message
    createSuccessMessage(message, autoDismiss = true) {
        const container = document.createElement('div');
        container.className = 'success-message';
        container.innerHTML = `
            <i class="fas fa-check-circle"></i>
            <span>${message}</span>
        `;

        if (autoDismiss) {
            setTimeout(() => {
                container.style.opacity = '0';
                container.style.transition = 'opacity 0.3s';
                setTimeout(() => container.remove(), 300);
            }, 3000);
        }

        return container;
    },

    // Empty State
    createEmptyState(icon, title, description, action = null) {
        const container = document.createElement('div');
        container.className = 'empty-state';
        container.innerHTML = `
            <div class="empty-state-icon"><i class="${icon}"></i></div>
            <h3 style="color: #9CA3AF; margin-bottom: 8px;">${title}</h3>
            <p style="color: #6B7280; margin-bottom: 20px;">${description}</p>
            ${action ? `<button onclick="${action.onClick}" class="btn-primary">${action.label}</button>` : ''}
        `;
        return container;
    },

    // Show/hide loading overlay
    showLoading(container, text = 'Loading...') {
        const existing = container.querySelector('.loading-state');
        if (existing) existing.remove();

        container.appendChild(this.createLoadingSpinner(text));
    },

    hideLoading(container) {
        const loading = container.querySelector('.loading-state');
        if (loading) loading.remove();
    },

    // Initialize connection indicator
    initConnectionIndicator() {
        if (!document.getElementById('ws-connection-indicator')) {
            document.body.appendChild(this.createConnectionIndicator());
        }

        // Update latency display
        if (window.WebSocketClient) {
            window.WebSocketClient.on('latency_update', (data) => {
                const latencyEl = document.getElementById('ws-latency');
                if (latencyEl) {
                    latencyEl.textContent = `${data.latency}ms`;
                }
            });
        }
    }
};

// Auto-initialize
if (typeof window !== 'undefined') {
    window.UIComponents = UIComponents;

    document.addEventListener('DOMContentLoaded', () => {
        UIComponents.initConnectionIndicator();
    });
}
