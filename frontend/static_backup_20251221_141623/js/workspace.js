/**
 * Daena Workspace Logic
 * Handles file explorer and project management.
 */

const Workspace = {
    state: {
        currentPath: '/',
        projects: [],
        files: []
    },

    async init() {
        console.log('Workspace Initialized');
        await this.loadProjects();
        this.renderExplorer();
    },

    async loadProjects() {
        try {
            // Mock data for now, replace with API call
            // const projects = await window.DaenaAPI.getProjects();
            this.state.projects = [
                { id: 'p1', name: 'Project Alpha', type: 'folder' },
                { id: 'p2', name: 'Marketing Campaign', type: 'folder' },
                { id: 'p3', name: 'Q4 Financials', type: 'folder' }
            ];

            this.state.files = [
                { id: 'f1', name: 'brief.pdf', type: 'file', size: '2.4 MB' },
                { id: 'f2', name: 'budget.xlsx', type: 'file', size: '1.1 MB' }
            ];
        } catch (e) {
            console.error('Failed to load projects', e);
            App.showToast('Failed to load projects', 'error');
        }
    },

    renderExplorer() {
        const container = document.getElementById('file-explorer');
        if (!container) return;

        let html = '';

        // Render Projects (Folders)
        this.state.projects.forEach(p => {
            html += `
                <div class="p-4 bg-white/5 rounded-lg border border-white/5 hover:bg-white/10 cursor-pointer transition-colors group">
                    <div class="flex items-center gap-3 mb-2">
                        <i class="fas fa-folder text-daena-gold text-2xl group-hover:scale-110 transition-transform"></i>
                        <span class="font-medium text-white">${p.name}</span>
                    </div>
                    <div class="text-xs text-gray-500">Project Folder</div>
                </div>
            `;
        });

        // Render Files
        this.state.files.forEach(f => {
            html += `
                <div class="p-4 bg-white/5 rounded-lg border border-white/5 hover:bg-white/10 cursor-pointer transition-colors group">
                    <div class="flex items-center gap-3 mb-2">
                        <i class="fas fa-file-alt text-gray-400 text-2xl group-hover:text-white transition-colors"></i>
                        <span class="font-medium text-gray-300 group-hover:text-white">${f.name}</span>
                    </div>
                    <div class="text-xs text-gray-500">${f.size}</div>
                </div>
            `;
        });

        container.innerHTML = html;
    }
};

if (document.getElementById('file-explorer')) {
    document.addEventListener('DOMContentLoaded', () => {
        Workspace.init();
    });
}
