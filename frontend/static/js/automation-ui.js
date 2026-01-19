/**
 * Automation UI Manager
 * Handles UI updates for agent automation, tool execution, and routing
 */

class AutomationUIManager {
    constructor() {
        this.status = {
            routing: false,
            ollama: false,
            deepseek: false
        };
        this.init();
    }

    async init() {
        await this.checkStatus();
        // Poll status every 30 seconds
        setInterval(() => this.checkStatus(), 30000);
    }

    async checkStatus() {
        try {
            const response = await fetch('/api/v1/automation/status');
            const data = await response.json();

            this.status = {
                routing: data.routing?.available || false,
                ollama: data.ollama?.available || false,
                deepseek: data.ollama?.has_reasoning || false
            };

            this.updateUI();
        } catch (e) {
            console.error('Failed to check automation status:', e);
        }
    }

    updateUI() {
        // Update any automation status indicators on the page
        const routingIndicator = document.getElementById('routing-status');
        if (routingIndicator) {
            this.updateIndicator(routingIndicator, this.status.routing, 'Intelligent Routing');
        }

        const deepseekIndicator = document.getElementById('reasoning-status');
        if (deepseekIndicator) {
            this.updateIndicator(deepseekIndicator, this.status.deepseek, 'DeepSeek Reasoning');
        }
    }

    updateIndicator(element, active, label) {
        if (active) {
            element.innerHTML = `
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 text-xs">
                    <div class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                    <span>${label}: Active</span>
                </div>
            `;
        } else {
            element.innerHTML = `
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-500/10 border border-gray-500/20 text-gray-400 text-xs">
                    <div class="w-1.5 h-1.5 rounded-full bg-gray-500"></div>
                    <span>${label}: Offline</span>
                </div>
            `;
        }
    }

    async executeTool(toolName, action, args) {
        try {
            const response = await fetch('/api/v1/automation/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: toolName,
                    action: action,
                    args: args
                })
            });
            return await response.json();
        } catch (e) {
            console.error('Tool execution failed:', e);
            return { success: false, error: e.message };
        }
    }
}

// Global instance
window.automationUI = new AutomationUIManager();
