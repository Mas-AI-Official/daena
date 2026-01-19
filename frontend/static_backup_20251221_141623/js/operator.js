/**
 * Daena Operator Logic (Manus-style)
 * Handles the right-hand panel for complex tasks, plans, and CMP connectors.
 */

const Operator = {
    state: {
        activeTab: 'plan', // 'plan', 'connectors', 'logs'
        currentPlan: [],
        isRunning: false
    },

    init() {
        this.bindEvents();
        this.renderConnectors(); // Initial render
    },

    bindEvents() {
        // Tab Switching
        document.querySelectorAll('.operator-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // New Plan Input
        const planInput = document.getElementById('operator-input');
        if (planInput) {
            planInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.submitPlan(planInput.value);
                    planInput.value = '';
                }
            });
        }
    },

    switchTab(tabName) {
        this.state.activeTab = tabName;

        // Update Tab UI
        document.querySelectorAll('.operator-tab').forEach(tab => {
            if (tab.dataset.tab === tabName) {
                tab.classList.add('text-daena-gold', 'border-b-2', 'border-daena-gold');
                tab.classList.remove('text-gray-400');
            } else {
                tab.classList.remove('text-daena-gold', 'border-b-2', 'border-daena-gold');
                tab.classList.add('text-gray-400');
            }
        });

        // Show/Hide Content
        document.getElementById('tab-content-plan').classList.toggle('hidden', tabName !== 'plan');
        document.getElementById('tab-content-connectors').classList.toggle('hidden', tabName !== 'connectors');
        document.getElementById('tab-content-logs').classList.toggle('hidden', tabName !== 'logs');
    },

    async submitPlan(text) {
        if (!text.trim()) return;

        // Add user message
        this.addMessage('user', text);

        // Simulate processing
        this.addMessage('system', 'Analyzing request...');

        // Mock Plan Generation (Replace with real API call later)
        setTimeout(() => {
            this.addMessage('system', 'I have created a plan for this task:');
            this.renderPlan([
                { id: 1, title: 'Analyze Requirements', status: 'completed' },
                { id: 2, title: 'Search Knowledge Base', status: 'running' },
                { id: 3, title: 'Draft Response', status: 'pending' }
            ]);
        }, 1000);
    },

    addMessage(role, text) {
        const container = document.getElementById('operator-chat');
        if (!container) return;

        const msgDiv = document.createElement('div');
        msgDiv.className = `mb-4 p-3 rounded-lg ${role === 'user' ? 'bg-white/10 ml-8' : 'bg-daena-panel border border-daena-border mr-8'}`;
        msgDiv.innerHTML = `<p class="text-sm text-gray-200">${text}</p>`;

        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
    },

    renderPlan(steps) {
        const container = document.getElementById('operator-chat');
        const planDiv = document.createElement('div');
        planDiv.className = 'mb-4 p-4 bg-black/30 rounded-lg border border-daena-border';

        let html = '<h4 class="text-xs font-bold text-gray-400 uppercase mb-3">Execution Plan</h4><div class="space-y-3">';

        steps.forEach(step => {
            let icon = 'circle';
            let color = 'text-gray-500';

            if (step.status === 'completed') {
                icon = 'check-circle';
                color = 'text-green-400';
            } else if (step.status === 'running') {
                icon = 'spinner fa-spin';
                color = 'text-daena-gold';
            }

            html += `
                <div class="flex items-center gap-3">
                    <i class="fas fa-${icon} ${color} text-sm"></i>
                    <span class="text-sm ${step.status === 'completed' ? 'text-gray-400 line-through' : 'text-gray-200'}">${step.title}</span>
                </div>
            `;
        });

        html += '</div>';
        planDiv.innerHTML = html;
        container.appendChild(planDiv);
        container.scrollTop = container.scrollHeight;
    },

    async renderConnectors() {
        const container = document.getElementById('tab-content-connectors');
        if (!container) return;

        try {
            const connectors = await window.DaenaAPI.getConnectors();

            container.innerHTML = connectors.map(c => `
                <div class="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5 hover:border-daena-gold/30 transition-colors">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded bg-black flex items-center justify-center">
                            <i class="fas fa-plug text-gray-400"></i>
                        </div>
                        <div>
                            <div class="text-sm font-medium text-white">${c.name}</div>
                            <div class="text-xs text-gray-500 capitalize">${c.type}</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full ${c.status === 'connected' ? 'bg-green-500' : 'bg-red-500'}"></span>
                        <span class="text-xs text-gray-400 capitalize">${c.status}</span>
                    </div>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load connectors', e);
            container.innerHTML = '<div class="text-red-400 text-sm p-4">Failed to load connectors.</div>';
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Operator.init();
});
