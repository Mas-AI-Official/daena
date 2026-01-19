"""
Frontend integration for Change Control V2 - Backup Management UI

Adds change history and backup controls to Founder Panel
"""

const ChangeControl = {
    async getStats() {
        try {
            const response = await fetch('/api/v1/changes/stats');
            const data = await response.json();
            return data.stats;
        } catch (error) {
            console.error('Failed to get backup stats:', error);
            return null;
        }
    },

    async getRecentChanges(limit = 10) {
        try {
            const response = await fetch(`/api/v1/changes/recent?limit=${limit}`);
            const data = await response.json();
            return data.recent_changes || [];
        } catch (error) {
            console.error('Failed to get recent changes:', error);
            return [];
        }
    },

    async getHistory(filters = {}) {
        try {
            const params = new URLSearchParams();
            if (filters.filePath) params.append('file_path', filters.filePath);
            if (filters.actor) params.append('actor', filters.actor);
            if (filters.limit) params.append('limit', filters.limit);

            const response = await fetch(`/api/v1/changes/history?${params}`);
            const data = await response.json();
            return data.changes || [];
        } catch (error) {
            console.error('Failed to get change history:', error);
            return [];
        }
    },

    async rollback(backupId) {
        try {
            const response = await fetch('/api/v1/changes/rollback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ backup_id: backupId })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            return data.success;
        } catch (error) {
            console.error('Failed to rollback:', error);
            return false;
        }
    },

    renderStats(stats, containerId) {
        const container = document.getElementById(containerId);
        if (!container || !stats) return;

        const sizeMB = stats.total_size_mb || 0;
        const total = stats.total_backups || 0;

        container.innerHTML = `
            <div class="backup-stats-grid">
                <div class="backup-stat-card">
                    <div class="stat-value">${total}</div>
                    <div class="stat-label">Total Backups</div>
                </div>
                <div class="backup-stat-card">
                    <div class="stat-value">${sizeMB.toFixed(2)} MB</div>
                    <div class="stat-label">Storage Used</div>
                </div>
                <div class="backup-stat-card">
                    <div class="stat-value">${Object.keys(stats.backups_by_actor || {}).length}</div>
                    <div class="stat-label">Contributors</div>
                </div>
            </div>
        `;
    },

    renderRecentChanges(changes, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (changes.length === 0) {
            container.innerHTML = '<p style="color: #9CA3AF; padding: 20px; text-align: center;">No recent changes</p>';
            return;
        }

        container.innerHTML = changes.map(change => {
            const fileName = change.file_path.split('/').pop() || change.file_path;
            const timeAgo = this.getTimeAgo(new Date(change.timestamp));
            const statusColor = change.status === 'complete' ? '#22C55E' : '#F59E0B';

            return `
                <div class="change-item" style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div style="flex: 1;">
                            <div style="font-size: 14px; font-weight: 600; color: white; margin-bottom: 4px;">
                                ${fileName}
                            </div>
                            <div style="font-size: 12px; color: #9CA3AF;">
                                <span style="color: var(--daena-gold);">${change.actor}</span> • 
                                ${change.change_type} • ${timeAgo}
                            </div>
                            <div style="font-size: 11px; color: #6B7280; margin-top: 4px;">
                                ${change.reason}
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <span style="padding: 4px 8px; border-radius: 12px; font-size: 10px; background: ${statusColor}20; color: ${statusColor};">
                                ${change.status}
                            </span>
                            ${change.rollback_available ? `
                                <button onclick="ChangeControl.confirmRollback('${change.backup_id}')" 
                                        style="padding: 4px 8px; background: rgba(255,100,100,0.1); border: 1px solid #FF6464; border-radius: 6px; color: #FF6464; font-size: 10px; cursor: pointer;">
                                    Rollback
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    },

    async confirmRollback(backupId) {
        if (!confirm('Are you sure you want to rollback this change? This will restore the file to its previous state.')) {
            return;
        }

        const success = await this.rollback(backupId);

        if (success) {
            window.showToast?.('File rolled back successfully!', 'success');
            // Reload the changes list
            this.loadAndRender();
        } else {
            window.showToast?.('Failed to rollback file', 'error');
        }
    },

    getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        if (seconds < 60) return `${seconds}s ago`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    },

    async loadAndRender() {
        // Load and render both stats and recent changes
        const stats = await this.getStats();
        const recent = await this.getRecentChanges(10);

        this.renderStats(stats, 'backup-stats-container');
        this.renderRecentChanges(recent, 'recent-changes-container');
    }
};

// Auto-initialize on page load
if (typeof window !== 'undefined') {
    window.ChangeControl = ChangeControl;

    // Auto-load if containers exist
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('backup-stats-container') ||
            document.getElementById('recent-changes-container')) {
            ChangeControl.loadAndRender();

            // Refresh every 30 seconds
            setInterval(() => ChangeControl.loadAndRender(), 30000);
        }
    });
}
