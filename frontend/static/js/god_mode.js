/**
 * God Mode JavaScript Client
 * Connects to God Mode API endpoints for NBMF, Router, Verifier, DCP, and Change Control
 */

class GodModeClient {
    constructor() {
        this.baseUrl = '/api/v1/god-mode';
    }

    // ===== Status =====
    async getStatus() {
        const response = await fetch(`${this.baseUrl}/status`);
        return await response.json();
    }

    // ===== NBMF Memory Tiers =====
    async getMemoryTiers() {
        const response = await fetch(`${this.baseUrl}/memory/tiers`);
        return await response.json();
    }

    async storeMemory(tier, content, source, metadata = null, tags = null, evidence = null) {
        const response = await fetch(`${this.baseUrl}/memory/store`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tier, content, source, metadata, tags, evidence })
        });
        return await response.json();
    }

    async retrieveMemory(tier = null, tags = null, limit = 100) {
        let url = `${this.baseUrl}/memory/retrieve?limit=${limit}`;
        if (tier) url += `&tier=${tier}`;
        if (tags) url += `&tags=${tags}`;
        const response = await fetch(url);
        return await response.json();
    }

    async promoteToT2(entryId, agentType, verificationScore, evidence) {
        const response = await fetch(`${this.baseUrl}/memory/promote-to-t2`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                entry_id: entryId,
                agent_type: agentType,
                verification_score: verificationScore,
                evidence
            })
        });
        return await response.json();
    }

    // ===== Router Agent =====
    async dispatchTask(taskType, prompt, constraints = null) {
        const response = await fetch(`${this.baseUrl}/router/dispatch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_type: taskType, prompt, constraints })
        });
        return await response.json();
    }

    async getRouterModels() {
        const response = await fetch(`${this.baseUrl}/router/models`);
        return await response.json();
    }

    // ===== Verifier Agent =====
    async verifyClaim(claim, source, context = null, additionalSources = null) {
        const response = await fetch(`${this.baseUrl}/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claim,
                source,
                context,
                additional_sources: additionalSources
            })
        });
        return await response.json();
    }

    // ===== DCP Profiles =====
    async listDCPProfiles() {
        const response = await fetch(`${this.baseUrl}/dcp/profiles`);
        return await response.json();
    }

    async getDCPProfile(profileName) {
        const response = await fetch(`${this.baseUrl}/dcp/profiles/${profileName}`);
        return await response.json();
    }

    async evaluateDecision(decision, councilType = 'default', advisorCount = 5) {
        const response = await fetch(`${this.baseUrl}/dcp/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decision, council_type: councilType, advisor_count: advisorCount })
        });
        return await response.json();
    }

    // ===== Change Control =====
    async proposeChange(proposal) {
        const response = await fetch(`${this.baseUrl}/change-control/propose`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(proposal)
        });
        return await response.json();
    }

    async approveChange(proposalId, approver, notes = null) {
        const response = await fetch(`${this.baseUrl}/change-control/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ proposal_id: proposalId, approver, notes })
        });
        return await response.json();
    }

    async getPendingApprovals() {
        const response = await fetch(`${this.baseUrl}/change-control/pending`);
        return await response.json();
    }

    async getProposal(proposalId) {
        const response = await fetch(`${this.baseUrl}/change-control/proposals/${proposalId}`);
        return await response.json();
    }

    async getHardPolicies() {
        const response = await fetch(`${this.baseUrl}/change-control/hard-policies`);
        return await response.json();
    }
}

// Global instance
const godMode = new GodModeClient();

// ===== UI Functions for Founder Panel =====

async function loadGodModeStatus() {
    try {
        const status = await godMode.getStatus();

        // Update status indicator
        const indicator = document.getElementById('god-mode-status-indicator');
        const statusText = document.getElementById('god-mode-status-text');

        if (status.success) {
            indicator.style.background = '#32CD32';
            statusText.textContent = 'Active';
            statusText.style.color = '#32CD32';
        } else {
            indicator.style.background = '#FF6464';
            statusText.textContent = 'Error';
            statusText.style.color = '#FF6464';
        }

        // Load NBMF tiers summary
        const tiersData = await godMode.getMemoryTiers();
        if (tiersData.success) {
            const summary = document.getElementById('nbmf-tiers-summary');
            summary.innerHTML = `
                <div style="margin-bottom: 4px;"><strong>${tiersData.total_entries}</strong> total entries</div>
                ${Object.entries(tiersData.tiers).slice(0, 3).map(([tier, data]) =>
                `<div style="font-size: 10px; margin: 2px 0;">• ${tier}: ${data.count} entries</div>`
            ).join('')}
            `;
        }

        // Load pending changes count
        const pendingChanges = await godMode.getPendingApprovals();
        if (pendingChanges.success) {
            document.getElementById('pending-changes-count').textContent = pendingChanges.count || 0;
        }

        // Load router models count
        const models = await godMode.getRouterModels();
        if (models.success) {
            document.getElementById('router-models-count').textContent = models.count || 0;
        }

    } catch (error) {
        console.error('Failed to load God Mode status:', error);
        const indicator = document.getElementById('god-mode-status-indicator');
        const statusText = document.getElementById('god-mode-status-text');
        indicator.style.background = '#FF6464';
        statusText.textContent = 'Error';
        statusText.style.color = '#FF6464';
    }
}

// View Memory Tiers Modal
async function viewMemoryTiers() {
    try {
        const tiersData = await godMode.getMemoryTiers();

        const modalHtml = `
            <div class="modal-overlay" id="memory-tiers-modal" onclick="closeGodModeModal('memory-tiers-modal')" 
                style="display: flex; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center;">
                <div class="modal-content" onclick="event.stopPropagation()" 
                    style="width: 90%; max-width: 700px; background: #0f1729; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;">
                    <div class="modal-header" style="padding: 24px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: space-between; align-items: center;">
                        <h2 style="color: white; font-size: 20px; margin: 0;">NBMF Memory Tiers</h2>
                        <div onclick="closeGodModeModal('memory-tiers-modal')" 
                            style="width: 36px; height: 36px; border-radius: 50%; background: rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: center; cursor: pointer; color: white;">
                            <i class="fas fa-times"></i>
                        </div>
                    </div>
                    <div class="modal-body" style="padding: 24px;">
                        <div style="margin-bottom: 20px;">
                            <div style="color: var(--daena-gold); font-size: 24px; font-weight: 700;">${tiersData.total_entries || 0}</div>
                            <div style="color: #9CA3AF; font-size: 12px;">Total Memory Entries</div>
                        </div>
                        ${Object.entries(tiersData.tiers || {}).map(([tier, data]) => `
                            <div style="padding: 16px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                    <div style="color: white; font-weight: 600;">${tier.replace('_', ' ')}</div>
                                    <div style="color: var(--daena-gold); font-size: 18px; font-weight: 700;">${data.count}</div>
                                </div>
                                <div style="font-size: 11px; color: #9CA3AF;">
                                    <div>• Verified: ${data.verified_count || 0}</div>
                                    <div>• Retention: ${data.retention}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
    } catch (error) {
        console.error('Failed to load memory tiers:', error);
        alert('Failed to load memory tiers');
    }
}

// View Change Control Modal
async function viewChangeControl() {
    try {
        const pendingData = await godMode.getPendingApprovals();

        const modalHtml = `
            <div class="modal-overlay" id="change-control-modal" onclick="closeGodModeModal('change-control-modal')" 
                style="display: flex; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center;">
                <div class="modal-content" onclick="event.stopPropagation()" 
                    style="width: 90%; max-width: 800px; background: #0f1729; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;">
                    <div class="modal-header" style="padding: 24px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: space-between; align-items: center;">
                        <h2 style="color: white; font-size: 20px; margin: 0;">Change Control Queue</h2>
                        <div onclick="closeGodModeModal('change-control-modal')" 
                            style="width: 36px; height: 36px; border-radius: 50%; background: rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: center; cursor: pointer; color: white;">
                            <i class="fas fa-times"></i>
                        </div>
                    </div>
                    <div class="modal-body" style="padding: 24px; max-height: 500px; overflow-y: auto;">
                        <div style="margin-bottom: 20px;">
                            <div style="color: var(--daena-gold); font-size: 24px; font-weight: 700;">${pending Data.count || 0
    }</div >
        <div style="color: #9CA3AF; font-size: 12px;">Pending Founder Approval</div>
                        </div >
        ${
            (pendingData.proposals || []).length === 0
            ? '<div style="text-align: center; color: #9CA3AF; padding: 40px;">No pending approvals</div>'
            : (pendingData.proposals || []).map(proposal => `
                                <div style="padding: 16px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; margin-bottom: 12px;">
                                    <div style="color: white; font-weight: 600; margin-bottom: 8px;">${proposal.title}</div>
                                    <div style="font-size: 11px; color: #9CA3AF; margin-bottom: 12px;">
                                        <div>Proposed by: ${proposal.proposed_by}</div>
                                        <div>Risks: ${proposal.risks_count || 0}</div>
                                    </div>
                                    <div style="display: flex; gap: 8px;">
                                        <button onclick="approveChangeProposal('${proposal.id}')" 
                                            style="flex: 1; padding: 8px; background: var(--daena-gold); color: black; border: none; border-radius: 6px; font-weight: 600; cursor: pointer;">
                                            <i class="fas fa-check"></i> Approve
                                        </button>
                                        <button onclick="viewProposalDetails('${proposal.id}')" 
                                            style="flex: 1; padding: 8px; background: rgba(255,255,255,0.1); color: white; border: none; border-radius: 6px; cursor: pointer;">
                                            <i class="fas fa-info-circle"></i> Details
                                        </button>
                                    </div>
                                </div>
                            `).join('')
    }
                    </div >
                </div >
            </div >
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    } catch (error) {
        console.error('Failed to load change control:', error);
        alert('Failed to load change control queue');
    }
}

// View Router Status Modal
async function viewRouterStatus() {
    try {
        const modelsData = await godMode.getRouterModels();
        
        const modalHtml = `
        < div class="modal-overlay" id = "router-status-modal" onclick = "closeGodModeModal('router-status-modal')"
    style = "display: flex; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center;" >
        <div class="modal-content" onclick="event.stopPropagation()"
            style="width: 90%; max-width: 700px; background: #0f1729; border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;">
            <div class="modal-header" style="padding: 24px; border-bottom: 1px solid rgba(255,255,255,0.1); display: flex; justify-content: space-between; align-items: center;">
                <h2 style="color: white; font-size: 20px; margin: 0;">Router Agent Models</h2>
                <div onclick="closeGodModeModal('router-status-modal')"
                    style="width: 36px; height: 36px; border-radius: 50%; background: rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: center; cursor: pointer; color: white;">
                    <i class="fas fa-times"></i>
                </div>
            </div>
            <div class="modal-body" style="padding: 24px; max-height: 500px; overflow-y: auto;">
                <div style="margin-bottom: 20px;">
                    <div style="color: var(--daena-gold); font-size: 24px; font-weight: 700;">${modelsData.count || 0}</div>
                    <div style="color: #9CA3AF; font-size: 12px;">Available Models</div>
                </div>
                ${(modelsData.models || []).map(model => `
                            <div style="padding: 16px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; margin-bottom: 12px;">
                                <div style="color: white; font-weight: 600; margin-bottom: 8px;">${model.name}</div>
                                <div style="font-size: 11px; color: #9CA3AF;">
                                    <div>• Provider: ${model.provider}</div>
                                    <div>• Capabilities: ${(model.capabilities || []).join(', ')}</div>
                                    <div>• Context Limit: ${model.context_limit?.toLocaleString()} tokens</div>
                                    <div>• Speed: ${model.speed}</div>
                                    <div>• Hallucination: ${model.hallucination_tendency}</div>
                                </div>
                            </div>
                        `).join('')}
            </div>
        </div>
            </div >
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    } catch (error) {
        console.error('Failed to load router status:', error);
        alert('Failed to load router models');
    }
}

function closeGodModeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.remove();
}

async function approveChangeProposal(proposalId) {
    if (confirm('Approve this change proposal? This will apply HARD-CODE policy changes.')) {
        try {
            const result = await godMode.approveChange(proposalId, 'masoud', 'Approved via Founder Panel');
            if (result.success) {
                alert('Change approved successfully!');
                closeGodModeModal('change-control-modal');
                loadGodModeStatus(); // Refresh
            } else {
                alert('Failed to approve change: ' + (result.detail || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error approving change:', error);
            alert('Error approving change');
        }
    }
}

async function viewProposalDetails(proposalId) {
    try {
        const proposalData = await godMode.getProposal(proposalId);
        alert(JSON.stringify(proposalData.proposal, null, 2));
    } catch (error) {
        console.error('Error loading proposal details:', error);
        alert('Failed to load proposal details');
    }
}

// Load God Mode status on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadGodModeStatus);
} else {
    loadGodModeStatus();
}
