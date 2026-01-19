/**
 * Strategic Room Controls
 * Manages strategic planning dashboard, council integration, and decision tracking
 */

const StrategicRoom = {
    currentGoals: [],
    activeInitiatives: [],

    async init() {
        console.log('Initializing Strategic Room...');
        await this.loadGoals();
        await this.loadInitiatives();
        this.setupEventListeners();
        this.setupRealTimeUpdates();
    },

    async loadGoals() {
        try {
            const response = await fetch('/api/v1/strategic/goals');
            const data = await response.json();
            this.currentGoals = data.goals || [];
            this.renderGoals();
        } catch (error) {
            console.error('Failed to load goals:', error);
            this.currentGoals = [];
        }
    },

    async loadInitiatives() {
        try {
            const response = await fetch('/api/v1/strategic-assembly/initiatives');
            const data = await response.json();
            this.activeInitiatives = data.initiatives || [];
            this.renderInitiatives();
        } catch (error) {
            console.error('Failed to load initiatives:', error);
            this.activeInitiatives = [];
        }
    },

    renderGoals() {
        const container = document.getElementById('goals-container');
        if (!container) return;

        if (this.currentGoals.length === 0) {
            container.innerHTML = '<p style="color: #9CA3AF; padding: 20px; text-align: center;">No strategic goals</p>';
            return;
        }

        container.innerHTML = this.currentGoals.map(goal => `
            <div class="goal-card" data-goal-id="${goal.id}">
                <div class="goal-header">
                    <h3>${goal.title}</h3>
                    <span class="goal-status ${goal.status}">${goal.status}</span>
                </div>
                <p class="goal-description">${goal.description}</p>
                <div class="goal-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${goal.progress}%"></div>
                    </div>
                    <span>${goal.progress}% complete</span>
                </div>
                <div class="goal-meta">
                    <span><i class="fas fa-users"></i> ${goal.assigned_to}</span>
                    <span><i class="fas fa-calendar"></i> ${this.formatDate(goal.deadline)}</span>
                </div>
            </div>
        `).join('');
    },

    renderInitiatives() {
        const container = document.getElementById('initiatives-container');
        if (!container) return;

        if (this.activeInitiatives.length === 0) {
            container.innerHTML = '<p style="color: #9CA3AF; padding: 20px; text-align: center;">No active initiatives</p>';
            return;
        }

        container.innerHTML = this.activeInitiatives.map(initiative => `
            <div class="initiative-card" onclick="StrategicRoom.viewInitiativeDetail('${initiative.id}')">
                <h4>${initiative.name}</h4>
                <p>${initiative.description}</p>
                <div class="initiative-departments">
                    ${initiative.departments.map(dept => `
                        <span class="dept-badge" style="background: ${dept.color}20; color: ${dept.color};">
                            ${dept.name}
                        </span>
                    `).join('')}
                </div>
            </div>
        `).join('');
    },

    setupEventListeners() {
        // Add goal button
        const addGoalBtn = document.getElementById('add-goal-btn');
        if (addGoalBtn) {
            addGoalBtn.addEventListener('click', () => this.openAddGoalModal());
        }

        // Add initiative button
        const addInitiativeBtn = document.getElementById('add-initiative-btn');
        if (addInitiativeBtn) {
            addInitiativeBtn.addEventListener('click', () => this.openAddInitiativeModal());
        }
    },

    setupRealTimeUpdates() {
        // Subscribe to WebSocket updates if available
        if (window.WebSocketClient) {
            window.WebSocketClient.on('strategic_update', (data) => {
                console.log('Strategic update received:', data);
                this.handleRealTimeUpdate(data);
            });
        }
    },

    handleRealTimeUpdate(data) {
        if (data.type === 'goal_update') {
            this.loadGoals();
        } else if (data.type === 'initiative_update') {
            this.loadInitiatives();
        }
    },

    async openAddGoalModal() {
        // Show modal for adding new goal
        console.log('Opening add goal modal...');
        window.showToast?.('Add Goal feature - Coming soon', 'info');
    },

    async openAddInitiativeModal() {
        // Show modal for adding new initiative
        console.log('Opening add initiative modal...');
        window.showToast?.('Add Initiative feature - Coming soon', 'info');
    },

    async viewInitiativeDetail(initiativeId) {
        console.log('Viewing initiative:', initiativeId);
        window.location.href = `/ui/strategic-assembly/initiative/${initiativeId}`;
    },

    formatDate(dateStr) {
        if (!dateStr) return 'No deadline';
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    },

    async refreshAll() {
        await Promise.all([
            this.loadGoals(),
            this.loadInitiatives()
        ]);
        window.showToast?.('Strategic room refreshed', 'success');
    }
};

// Auto-initialize
if (typeof window !== 'undefined') {
    window.StrategicRoom = StrategicRoom;

    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('strategic-room-container')) {
            StrategicRoom.init();
        }
    });
}
