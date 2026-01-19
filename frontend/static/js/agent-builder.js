/**
 * Agent Builder Wizard
 * Handles agent creation workflow, template selection, and customization
 */

const AgentBuilder = {
    currentStep: 1,
    selectedTemplate: null,
    agentConfig: {},

    async init() {
        console.log('Initializing Agent Builder...');
        await this.loadTemplates();
        this.setupWizard();
        this.setupEventListeners();
    },

    async loadTemplates() {
        try {
            const response = await fetch('/agent-builder/api/v1/templates');
            const data = await response.json();
            this.renderTemplates(data.templates || []);
        } catch (error) {
            console.error('Failed to load templates:', error);
            window.showToast?.('Failed to load agent templates', 'error');
        }
    },

    renderTemplates(templates) {
        const container = document.getElementById('templates-gallery');
        if (!container) return;

        container.innerHTML = templates.map(template => `
            <div class="template-card" data-template-id="${template.id}" onclick="AgentBuilder.selectTemplate('${template.id}')">
                <div class="template-icon" style="background: ${template.color || '#0066cc'}20;">
                    <i class="${template.icon || 'fas fa-robot'}"></i>
                </div>
                <h3>${template.name}</h3>
                <p>${template.description}</p>
                <div class="template-meta">
                    <span><i class="fas fa-cog"></i> ${template.capabilities?.length || 0} capabilities</span>
                    <span><i class="fas fa-users"></i> ${template.usage_count || 0} uses</span>
                </div>
                <button class="select-btn">Select Template</button>
            </div>
        `).join('');
    },

    setupWizard() {
        this.updateStepIndicator();
    },

    setupEventListeners() {
        // Next/Previous buttons
        const nextBtn = document.getElementById('wizard-next-btn');
        const prevBtn = document.getElementById('wizard-prev-btn');
        const createBtn = document.getElementById('create-agent-btn');

        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.nextStep());
        }

        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.previousStep());
        }

        if (createBtn) {
            createBtn.addEventListener('click', () => this.createAgent());
        }
    },

    async selectTemplate(templateId) {
        try {
            const response = await fetch(`/agent-builder/api/v1/templates/${templateId}`);
            const data = await response.json();

            this.selectedTemplate = data.template;
            this.agentConfig = {
                template_id: templateId,
                name: '',
                description: '',
                capabilities: [...this.selectedTemplate.default_capabilities]
            };

            // Highlight selected template
            document.querySelectorAll('.template-card').forEach(card => {
                card.classList.remove('selected');
            });
            document.querySelector(`[data-template-id="${templateId}"]`)?.classList.add('selected');

            window.showToast?.(`Selected template: ${this.selectedTemplate.name}`, 'success');

            // Auto-advance to next step
            setTimeout(() => this.nextStep(), 500);
        } catch (error) {
            console.error('Failed to select template:', error);
            window.showToast?.('Failed to load template details', 'error');
        }
    },

    nextStep() {
        if (this.currentStep === 1 && !this.selectedTemplate) {
            window.showToast?.('Please select a template first', 'warning');
            return;
        }

        if (this.currentStep < 3) {
            this.currentStep++;
            this.showStep(this.currentStep);
            this.updateStepIndicator();
        }
    },

    previousStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.showStep(this.currentStep);
            this.updateStepIndicator();
        }
    },

    showStep(step) {
        // Hide all steps
        document.querySelectorAll('.wizard-step').forEach(stepEl => {
            stepEl.classList.remove('active');
        });

        // Show current step
        const currentStepEl = document.getElementById(`step-${step}`);
        if (currentStepEl) {
            currentStepEl.classList.add('active');
        }

        // Update button visibility
        const prevBtn = document.getElementById('wizard-prev-btn');
        const nextBtn = document.getElementById('wizard-next-btn');
        const createBtn = document.getElementById('create-agent-btn');

        if (prevBtn) prevBtn.style.display = step === 1 ? 'none' : 'inline-block';
        if (nextBtn) nextBtn.style.display = step === 3 ? 'none' : 'inline-block';
        if (createBtn) createBtn.style.display = step === 3 ? 'inline-block' : 'none';

        // Populate step content
        if (step === 2) {
            this.populateConfigurationStep();
        } else if (step === 3) {
            this.populateReviewStep();
        }
    },

    populateConfigurationStep() {
        const nameInput = document.getElementById('agent-name-input');
        const descInput = document.getElementById('agent-description-input');

        if (nameInput) {
            nameInput.value = this.agentConfig.name || '';
            nameInput.addEventListener('input', (e) => {
                this.agentConfig.name = e.target.value;
            });
        }

        if (descInput) {
            descInput.value = this.agentConfig.description || '';
            descInput.addEventListener('input', (e) => {
                this.agentConfig.description = e.target.value;
            });
        }

        // Render capabilities checklist
        this.renderCapabilities();
    },

    renderCapabilities() {
        const container = document.getElementById('capabilities-list');
        if (!container || !this.selectedTemplate) return;

        const allCapabilities = this.selectedTemplate.available_capabilities || [];

        container.innerHTML = allCapabilities.map(capability => `
            <label class="capability-checkbox">
                <input type="checkbox" 
                       value="${capability.id}" 
                       ${this.agentConfig.capabilities.includes(capability.id) ? 'checked' : ''}
                       onchange="AgentBuilder.toggleCapability('${capability.id}', this.checked)">
                <div class="capability-info">
                    <strong>${capability.name}</strong>
                    <p>${capability.description}</p>
                </div>
            </label>
        `).join('');
    },

    toggleCapability(capabilityId, enabled) {
        if (enabled) {
            if (!this.agentConfig.capabilities.includes(capabilityId)) {
                this.agentConfig.capabilities.push(capabilityId);
            }
        } else {
            this.agentConfig.capabilities = this.agentConfig.capabilities.filter(
                id => id !== capabilityId
            );
        }
    },

    populateReviewStep() {
        const container = document.getElementById('review-content');
        if (!container) return;

        container.innerHTML = `
            <div class="review-section">
                <h3>Template</h3>
                <p>${this.selectedTemplate.name}</p>
            </div>
            <div class="review-section">
                <h3>Agent Name</h3>
                <p>${this.agentConfig.name || '<em>Not set</em>'}</p>
            </div>
            <div class="review-section">
                <h3>Description</h3>
                <p>${this.agentConfig.description || '<em>Not set</em>'}</p>
            </div>
            <div class="review-section">
                <h3>Capabilities (${this.agentConfig.capabilities.length})</h3>
                <ul>
                    ${this.agentConfig.capabilities.map(capId => {
            const cap = this.selectedTemplate.available_capabilities.find(c => c.id === capId);
            return `<li>${cap?.name || capId}</li>`;
        }).join('')}
                </ul>
            </div>
        `;
    },

    async createAgent() {
        // Validation
        if (!this.agentConfig.name) {
            window.showToast?.('Please provide an agent name', 'warning');
            this.currentStep = 2;
            this.showStep(2);
            return;
        }

        try {
            const response = await fetch('/agent-builder/api/v1/agents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.agentConfig)
            });

            if (!response.ok) throw new Error('Creation failed');

            const data = await response.json();

            window.showToast?.('Agent created successfully!', 'success');

            // Redirect to agent detail page
            setTimeout(() => {
                window.location.href = `/ui/agent-builder/agents/${data.agent.id}`;
            }, 1000);

        } catch (error) {
            console.error('Failed to create agent:', error);
            window.showToast?.('Failed to create agent', 'error');
        }
    },

    updateStepIndicator() {
        document.querySelectorAll('.step-indicator').forEach((indicator, index) => {
            const stepNum = index + 1;
            if (stepNum < this.currentStep) {
                indicator.classList.add('completed');
                indicator.classList.remove('active');
            } else if (stepNum === this.currentStep) {
                indicator.classList.add('active');
                indicator.classList.remove('completed');
            } else {
                indicator.classList.remove('active', 'completed');
            }
        });
    }
};

// Auto-initialize
if (typeof window !== 'undefined') {
    window.AgentBuilder = AgentBuilder;

    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('agent-builder-container')) {
            AgentBuilder.init();
        }
    });
}
