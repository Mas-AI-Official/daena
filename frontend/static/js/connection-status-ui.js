/**
 * Connection Status UI
 * Shows WebSocket connection status with retry feedback
 */

class ConnectionStatusUI {
    constructor() {
        this.statusElements = new Map();
        this.init();
    }

    init() {
        // Create status indicator if it doesn't exist
        this.createStatusIndicator();
        
        // Listen to WebSocket events
        if (window.WebSocketClient) {
            window.WebSocketClient.on('connected', (data) => {
                this.updateStatus(data.id, 'connected');
                if (window.toast) {
                    window.toast.success(`Connected to ${data.id}`, 2000);
                }
            });
            
            window.WebSocketClient.on('disconnected', (data) => {
                this.updateStatus(data.id, 'disconnected');
            });
            
            window.WebSocketClient.on('error', (data) => {
                this.updateStatus(data.id, 'error');
                if (window.toast) {
                    window.toast.error(`Connection error: ${data.id}`, 3000);
                }
            });
            
            window.WebSocketClient.on('connectionStatus', (data) => {
                this.updateStatus(data.connectionId, data.status, data);
            });
        }
    }

    createStatusIndicator() {
        // Check if status bar exists
        const statusBar = document.getElementById('status-bar') || 
                         document.querySelector('.status-bar') ||
                         document.querySelector('[data-status-bar]');
        
        if (!statusBar) {
            // Create status bar
            const bar = document.createElement('div');
            bar.id = 'websocket-status-bar';
            bar.className = 'websocket-status-bar';
            bar.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: rgba(26, 26, 46, 0.95);
                border: 1px solid rgba(255, 215, 0, 0.3);
                border-radius: 8px;
                padding: 12px 16px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 200px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            `;
            
            bar.innerHTML = `
                <div style="font-weight: 600; color: #ffd700; margin-bottom: 4px;">Connection Status</div>
                <div id="ws-status-events" class="ws-status-item">
                    <span class="ws-status-dot"></span>
                    <span class="ws-status-text">Events: Connecting...</span>
                </div>
            `;
            
            document.body.appendChild(bar);
        }
    }

    updateStatus(connectionId, status, data = {}) {
        const element = document.getElementById(`ws-status-${connectionId}`);
        if (!element) {
            // Create new status item
            const statusBar = document.getElementById('websocket-status-bar');
            if (statusBar) {
                const item = document.createElement('div');
                item.id = `ws-status-${connectionId}`;
                item.className = 'ws-status-item';
                item.style.cssText = `
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 14px;
                `;
                
                const dot = document.createElement('span');
                dot.className = 'ws-status-dot';
                dot.style.cssText = `
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    display: inline-block;
                `;
                
                const text = document.createElement('span');
                text.className = 'ws-status-text';
                
                item.appendChild(dot);
                item.appendChild(text);
                statusBar.appendChild(item);
            }
        }
        
        const statusItem = document.getElementById(`ws-status-${connectionId}`);
        if (statusItem) {
            const dot = statusItem.querySelector('.ws-status-dot');
            const text = statusItem.querySelector('.ws-status-text');
            
            const statusConfig = this.getStatusConfig(status, data);
            
            if (dot) {
                dot.style.backgroundColor = statusConfig.color;
                dot.style.boxShadow = `0 0 8px ${statusConfig.color}`;
            }
            
            if (text) {
                text.textContent = `${connectionId}: ${statusConfig.text}`;
                text.style.color = statusConfig.textColor;
            }
        }
    }

    getStatusConfig(status, data = {}) {
        const configs = {
            'connected': {
                color: '#10b981',
                text: 'Connected',
                textColor: '#10b981'
            },
            'connecting': {
                color: '#f59e0b',
                text: 'Connecting...',
                textColor: '#f59e0b'
            },
            'disconnected': {
                color: '#6b7280',
                text: 'Disconnected',
                textColor: '#6b7280'
            },
            'reconnecting': {
                color: '#f59e0b',
                text: `Reconnecting... (${data.attempts || 0})`,
                textColor: '#f59e0b'
            },
            'error': {
                color: '#ef4444',
                text: 'Error',
                textColor: '#ef4444'
            },
            'failed': {
                color: '#ef4444',
                text: 'Connection Failed',
                textColor: '#ef4444'
            }
        };
        
        return configs[status] || configs['disconnected'];
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.ConnectionStatusUI = new ConnectionStatusUI();
    });
} else {
    window.ConnectionStatusUI = new ConnectionStatusUI();
}

console.log('✅ Connection Status UI initialized');



