// Agents List Page - Frontend Wiring
// Connects to backend /api/v1/agents endpoints

let agents = [];
let currentFilter = 'all';

async function loadAgents(departmentFilter = null) {
    try {
        let url = '/api/v1/agents/';
        if (departmentFilter && departmentFilter !== 'all') {
            url += `?department_id=${departmentFilter}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        if (data.success && data.agents) {
            agents = data.agents;
            displayAgents(agents);
            updateStats(agents);
        } else {
            console.error('Failed to load agents:', data);
        }
    } catch (error) {
        console.error('Error loading agents:', error);
    }
}

function displayAgents(agentsData) {
    const container = document.getElementById('agents-container') || document.getElementById('agents-grid');
    if (!container) return;

    container.innerHTML = '';

    if (!agentsData || agentsData.length === 0) {
        container.innerHTML = '<p style="color: #9CA3AF; padding: 40px; text-align: center;">No agents found</p>';
        return;
    }

    agentsData.forEach(agent => {
        const card = createAgentCard(agent);
        container.appendChild(card);
    });

    console.log(`Displayed ${agentsData.length} agents`);
}

function createAgentCard(agent) {
    const card = document.createElement('div');
    card.className = 'agent-card';
    card.style.cssText = `
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        transition: all 0.3s;
        cursor: pointer;
    `;

    const isActive = agent.is_active !== false && agent.status !== 'offline';
    const statusColor = isActive ? '#32CD32' : '#9CA3AF';
    const statusText = isActive ? 'Online' : 'Offline';

    card.innerHTML = `
        <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 16px;">
            <div style="width: 50px; height: 50px; border-radius: 12px; background: linear-gradient(135deg, #D4AF37 0%, #F4C430 100%); display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; color: black;">
                ${agent.name ? agent.name.substring(0, 2).toUpperCase() : 'AG'}
            </div>
            <div style="flex: 1;">
                <h3 style="margin: 0 0 4px 0; color: white; font-size: 16px; font-weight: 600;">${agent.name}</h3>
                <p style="margin: 0; color: var(--daena-gold); font-size: 13px;">${agent.role || 'Agent'}</p>
                <p style="margin: 2px 0 0 0; color: #9CA3AF; font-size: 12px;">${agent.department_id || 'No Department'}</p>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 12px; background: ${statusColor}20; color: ${statusColor}; font-size: 12px;">
                <span style="width: 6px; height: 6px; border-radius: 50%; background: ${statusColor};"></span>
                ${statusText}
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
            <div style="text-align: center; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 8px;">
                <div style="font-size: 18px; font-weight: 700; color: #32CD32;">${agent.efficiency || '95.00'}%</div>
                <div style="font-size: 10px; color: #9CA3AF; text-transform: uppercase;">Efficiency</div>
            </div>
            <div style="text-align: center; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 8px;">
                <div style="font-size: 18px; font-weight: 700; color: white;">${agent.tasks || 0}</div>
                <div style="font-size: 10px; color: #9CA3AF; text-transform: uppercase;">Tasks</div>
            </div>
            <div style="text-align: center; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 8px;">
                <div style="font-size: 18px; font-weight: 700; color: white;">${agent.uptime || '2h'}</div>
                <div style="font-size: 10px; color: #9CA3AF; text-transform: uppercase;">Uptime</div>
            </div>
        </div>
        
        <button onclick="viewAgent('${agent.id}')" style="width: 100%; padding: 10px; background: linear-gradient(135deg, #D4AF37 0%, #F4C430 100%); border: none; border-radius: 8px; color: black; font-weight: 600; cursor: pointer; font-size: 13px;">
            View Details
        </button>
    `;

    card.addEventListener('mouseenter', () => {
        card.style.background = 'rgba(255, 255, 255, 0.05)';
        card.style.borderColor = 'rgba(212, 175, 55, 0.3)';
    });

    card.addEventListener('mouseleave', () => {
        card.style.background = 'rgba(255, 255, 255, 0.03)';
        card.style.borderColor = 'rgba(255, 255, 255, 0.1)';
    });

    return card;
}

function viewAgent(agentId) {
    window.location.href = `/ui/agents/${agentId}`;
}

function updateStats(agentsData) {
    const totalAgents = agentsData.length;
    const activeAgents = agentsData.filter(a => a.is_active !== false).length;

    const totalEl = document.getElementById('total-agents');
    const activeEl = document.getElementById('active-agents');

    if (totalEl) totalEl.textContent = totalAgents;
    if (activeEl) activeEl.textContent = activeAgents;
}

function filterAgents(departmentId) {
    currentFilter = departmentId;
    loadAgents(departmentId);
}

function searchAgents(query) {
    if (!query) {
        displayAgents(agents);
        return;
    }

    const filtered = agents.filter(agent =>
        agent.name.toLowerCase().includes(query.toLowerCase()) ||
        (agent.role && agent.role.toLowerCase().includes(query.toLowerCase())) ||
        (agent.department_id && agent.department_id.toLowerCase().includes(query.toLowerCase()))
    );

    displayAgents(filtered);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAgents();

    // Attach search handler if input exists
    const searchInput = document.getElementById('agent-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => searchAgents(e.target.value));
    }
});
