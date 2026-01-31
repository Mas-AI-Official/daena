// Councils Page - Frontend Wiring
// Connects to backend /api/v1/councils endpoints

let councils = [];

async function loadCouncils() {
    try {
        const response = await fetch('/api/v1/councils');
        const data = await response.json();

        if (data.success && data.councils) {
            councils = data.councils;
            displayCouncils(councils);
        } else {
            console.error('Failed to load councils:', data);
            if (window.showToast) {
                window.showToast('Failed to load councils', 'error');
            }
        }
    } catch (error) {
        console.error('Error loading councils:', error);
        if (window.showToast) {
            window.showToast('Error connecting to backend', 'error');
        }
    }
}

function displayCouncils(councilsData) {
    const container = document.getElementById('councils-container');
    if (!container) return;

    container.innerHTML = '';

    councilsData.forEach(council => {
        const card = createCouncilCard(council);
        container.appendChild(card);
    });

    console.log(`Displayed ${councilsData.length} councils`);
}

function createCouncilCard(council) {
    const card = document.createElement('div');
    card.className = 'council-card';
    card.style.cssText = `
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        cursor: pointer;
        transition: all 0.3s;
    `;

    card.innerHTML = `
        <div style="display: flex; align-items: center; gap: 16px;">
            <div style="width: 50px; height: 50px; border-radius: 12px; background: linear-gradient(135deg, #D4AF37 0%, #F4C430 100%); display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 700; color: black;">
                ${council.name.charAt(0)}
            </div>
            <div style="flex: 1;">
                <h3 style="margin: 0; color: white; font-size: 18px; font-weight: 600;">${council.name}</h3>
                <p style="margin: 4px 0 0 0; color: #9CA3AF; font-size: 14px;">${council.description || 'No description'}</p>
            </div>
            <div style="text-align: right;">
                <span style="padding: 4px 12px; border-radius: 12px; background: ${council.is_active ? 'rgba(50, 205, 50, 0.2)' : 'rgba(255, 0, 0, 0.2)'}; color: ${council.is_active ? '#32CD32' : '#FF6464'}; font-size: 12px;">
                    ${council.is_active ? 'Active' : 'Inactive'}
                </span>
            </div>
        </div>
        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.1); display: flex; gap: 8px; font-size: 12px; color: #9CA3AF;">
            <span><i class="fas fa-users"></i> ${council.member_agent_ids ? council.member_agent_ids.length : 0} members</span>
            <span><i class="fas fa-calendar"></i> Created ${new Date(council.created_at).toLocaleDateString()}</span>
        </div>
    `;

    card.addEventListener('click', () => viewCouncilDetails(council.id));

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

async function viewCouncilDetails(councilId) {
    try {
        const response = await fetch(`/api/v1/councils/${councilId}`);
        const data = await response.json();

        if (data.success && data.council) {
            displayCouncilModal(data.council);
        }
    } catch (error) {
        console.error('Error loading council details:', error);
    }
}

function displayCouncilModal(council) {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.className = 'council-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    `;

    modal.innerHTML = `
        <div style="background: #1a1a1a; border: 1px solid rgba(212, 175, 55, 0.3); border-radius: 20px; padding: 32px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                <h2 style="margin: 0; color: white; font-size: 24px;">${council.name}</h2>
                <button onclick="this.closest('.council-modal').remove()" style="background: transparent; border: none; color: white; font-size: 24px; cursor: pointer;">&times;</button>
            </div>
            
            <p style="color: #9CA3AF; margin-bottom: 24px;">${council.description || 'No description'}</p>
            
            <h3 style="color: var(--daena-gold); margin-bottom: 16px; font-size: 18px;">Council Members</h3>
            <div id="council-members-${council.id}" style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px;">
                <p style="color: #9CA3AF;">Loading members...</p>
            </div>
            
            <button onclick="chatWithCouncil('${council.id}')" style="width: 100%; padding: 12px; background: linear-gradient(135deg, #D4AF37 0%, #F4C430 100%); border: none; border-radius: 12px; color: black; font-weight: 600; cursor: pointer;">
                💬 Chat with Council
            </button>
        </div>
    `;

    document.body.appendChild(modal);

    // Load members
    loadCouncilMembers(council.id);

    // Close on outside click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

async function loadCouncilMembers(councilId) {
    try {
        const response = await fetch(`/api/v1/councils/${councilId}/members`);
        const data = await response.json();

        const container = document.getElementById(`council-members-${councilId}`);
        if (!container) return;

        if (data.success && data.members) {
            container.innerHTML = '';
            data.members.forEach(member => {
                const memberCard = document.createElement('div');
                memberCard.style.cssText = `
                    background: rgba(255, 255, 255, 0.03);
                    padding: 12px;
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                `;
                memberCard.innerHTML = `
                    <div style="width: 40px; height: 40px; border-radius: 10px; background: rgba(212, 175, 55, 0.2); display: flex; align-items: center; justify-content: center; color: var(--daena-gold); font-weight: 700;">
                        ${member.name.charAt(0)}
                    </div>
                    <div>
                        <div style="color: white; font-weight: 600;">${member.name}</div>
                        <div style="color: #9CA3AF; font-size: 12px;">${member.role} • ${member.department}</div>
                    </div>
                `;
                container.appendChild(memberCard);
            });
        }
    } catch (error) {
        console.error('Error loading council members:', error);
    }
}

function chatWithCouncil(councilId) {
    // TODO: Implement council chat interface
    alert(`Council chat for ${councilId} - implement chat interface`);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadCouncils();

    // Listen for WebSocket updates (via Global Client)
    if (window.wsClient) {
        window.wsClient.on('council.updated', (data) => {
            console.log('Council updated, refreshing...', data);
            loadCouncils();
        });
        window.wsClient.on('council.created', loadCouncils);
        window.wsClient.on('council.deleted', loadCouncils);
    }
});
