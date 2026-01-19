/**
 * Enhanced Dashboard - Agent Activity + Real-time Updates
 */

let activityRefreshInterval = null;
let lastActivityData = null;

async function loadAgentActivity() {
    try {
        const activities = await window.api.request('/agents/activity');
        lastActivityData = activities;
        renderActivityFeed(activities);
    } catch (e) {
        console.error('Failed to load agent activity:', e);
        document.getElementById('activity-feed').innerHTML = `
            <div class="text-center py-8 text-red-400 text-sm">
                <i class="fas fa-exclamation-triangle mb-2"></i>
                <p>Failed to load activity feed</p>
            </div>
        `;
    }
}

async function loadGovernanceQueue() {
    try {
        const response = await window.api.request('/brain/queue');
        renderGovernanceQueue(response.queue || []);
    } catch (e) {
        console.error('Failed to load governance queue:', e);
    }
}

function renderActivityFeed(activities) {
    const feed = document.getElementById('activity-feed');
    if (!feed) return;

    if (!activities || activities.length === 0) {
        feed.innerHTML = `
            <div class="text-center py-8 text-gray-500 text-sm">
                <i class="fas fa-robot text-3xl mb-2"></i>
                <p>No active agents</p>
            </div>
        `;
        return;
    }

    // Group by department
    const byDepartment = {};
    activities.forEach(activity => {
        if (!byDepartment[activity.department]) {
            byDepartment[activity.department] = [];
        }
        byDepartment[activity.department].push(activity);
    });

    feed.innerHTML = Object.entries(byDepartment).map(([dept, agents]) => `
        <div class="mb-6">
            <h4 class="text-xs font-bold text-gray-400 uppercase mb-3 flex items-center gap-2">
                <span>${dept}</span>
                <span class="text-daena-gold">(${agents.length})</span>
            </h4>
            ${agents.map(agent => renderAgentCard(agent)).join('')}
        </div>
    `).join('');
}

function renderAgentCard(agent) {
    const statusConfig = {
        'idle': { color: 'gray', icon: 'fa-circle', label: 'Idle', bgColor: 'bg-gray-500/10', textColor: 'text-gray-400' },
        'working': { color: 'blue', icon: 'fa-cog fa-spin', label: 'Working', bgColor: 'bg-blue-500/10', textColor: 'text-blue-400' },
        'waiting': { color: 'yellow', icon: 'fa-clock', label: 'Waiting', bgColor: 'bg-yellow-500/10', textColor: 'text-yellow-400' },
        'offline': { color: 'red', icon: 'fa-power-off', label: 'Offline', bgColor: 'bg-red-500/10', textColor: 'text-red-400' }
    };

    const config = statusConfig[agent.status] || statusConfig['offline'];

    return `
        <div class="p-4 bg-white/5 rounded-lg border-l-4 border-${config.color}-500 mb-3 hover:bg-white/10 transition-all cursor-pointer group"
             onclick="showAgentDetails('${agent.agent_id}')">
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg ${config.bgColor} flex items-center justify-center">
                        <i class="fas ${config.icon} text-lg ${config.textColor}"></i>
                    </div>
                    <div>
                        <h3 class="text-sm font-semibold text-white group-hover:text-daena-gold transition-colors">${agent.agent_name}</h3>
                        <p class="text-xs text-gray-500">${agent.department}</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs ${config.textColor} px-2 py-1 rounded ${config.bgColor}">
                        ${config.label}
                    </span>
                    <div class="w-2 h-2 rounded-full bg-${config.color}-500 ${agent.status === 'working' ? 'animate-pulse' : ''}"></div>
                </div>
            </div>
            
            ${agent.current_task ? `
                <div class="space-y-2">
                    <div class="text-xs text-gray-300 flex items-start gap-2">
                        <i class="fas fa-tasks mt-0.5 text-daena-gold"></i>
                        <span class="flex-1">${agent.current_task.description}</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <div class="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                            <div class="h-full bg-gradient-to-r from-${config.color}-500 to-daena-gold transition-all duration-500" 
                                 style="width: ${agent.current_task.progress * 100}%"></div>
                        </div>
                        <span class="text-xs font-mono ${config.textColor}">${Math.round(agent.current_task.progress * 100)}%</span>
                    </div>
                    <div class="text-xs text-gray-500">
                        <i class="far fa-clock mr-1"></i>
                        Started ${window.formatTimestamp(agent.current_task.started_at)}
                    </div>
                </div>
            ` : `
                <p class="text-xs text-gray-500">
                    <i class="fas fa-check-circle mr-1 text-green-500"></i>
                    No active tasks
                </p>
            `}
            
            ${agent.metrics ? `
                <div class="flex gap-4 mt-3 pt-3 border-t border-white/10">
                    <div class="text-xs">
                        <span class="text-gray-500">Completed:</span>
                        <span class="text-white font-semibold ml-1">${agent.metrics.tasks_completed || 0}</span>
                    </div>
                    <div class="text-xs">
                        <span class="text-gray-500">Success Rate:</span>
                        <span class="text-green-400 font-semibold ml-1">${Math.round((agent.metrics.success_rate || 0) * 100)}%</span>
                    </div>
                </div>
            ` : ''}
        </div>
    `;
}

function renderGovernanceQueue(queue) {
    const container = document.getElementById('governance-queue');
    if (!container) return;

    if (!queue || queue.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-gray-500 text-xs">
                No pending proposals
            </div>
        `;
        return;
    }

    // Show latest 5
    const latest = queue.slice(0, 5);

    container.innerHTML = latest.map(proposal => `
        <div class="p-3 bg-white/5 rounded-lg border-l-2 border-purple-500 mb-2 hover:bg-white/10 transition-colors cursor-pointer"
             onclick="showProposalDetails('${proposal.id}')">
            <div class="flex items-center justify-between mb-2">
                <span class="font-medium text-white text-sm">${proposal.source_agent_id}</span>
                <span class="text-purple-400 px-2 py-0.5 rounded bg-purple-500/10 text-[10px]">
                    ${proposal.state}
                </span>
            </div>
            <p class="text-xs text-gray-400 line-clamp-2">${proposal.reason}</p>
            <div class="flex items-center gap-3 mt-2 text-xs text-gray-500">
                <span><i class="far fa-clock mr-1"></i>${window.formatTimestamp(proposal.created_at)}</span>
                ${proposal.reviews ? `<span><i class="fas fa-users mr-1"></i>${proposal.reviews.length} reviews</span>` : ''}
            </div>
        </div>
    `).join('');
}

function showAgentDetails(agentId) {
    // Find agent in last data
    if (!lastActivityData) return;

    const agent = lastActivityData.find(a => a.agent_id === agentId);
    if (!agent) return;

    // Show modal with full details (implement later)
    console.log('Agent details:', agent);
    window.showToast(`Agent: ${agent.agent_name} (${agent.status})`, 'info');
}

function showProposalDetails(proposalId) {
    console.log('Proposal details:', proposalId);
    window.showToast('Proposal details coming soon', 'info');
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboardActivity);
} else {
    initDashboardActivity();
}

function initDashboardActivity() {
    // Only run on dashboard page
    if (!document.getElementById('activity-feed')) return;

    // Initial load
    loadAgentActivity();
    loadGovernanceQueue();

    // Refresh every 5 seconds (fallback)
    activityRefreshInterval = setInterval(() => {
        loadAgentActivity();
        loadGovernanceQueue();
    }, 5000);

    // Listen for WebSocket events (preferred)
    if (window.wsClient) {
        window.wsClient.on('agent.activity.updated', (data) => {
            console.log('Agent activity updated via WebSocket:', data);
            loadAgentActivity(); // Refresh immediately
        });

        window.wsClient.on('governance.proposal.created', (data) => {
            console.log('New governance proposal via WebSocket:', data);
            loadGovernanceQueue(); // Refresh immediately
            window.showToast('New proposal in governance queue', 'info');
        });

        window.wsClient.on('governance.proposal.approved', (data) => {
            console.log('Proposal approved via WebSocket:', data);
            loadGovernanceQueue();
            window.showToast(`Proposal ${data.proposal_id} approved!`, 'success');
        });
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (activityRefreshInterval) {
        clearInterval(activityRefreshInterval);
    }
});

console.log('✅ Enhanced dashboard.js loaded');
