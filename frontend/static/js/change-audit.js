/**
 * Change Audit Advanced UI
 * Extended backup management with advanced filtering, visualization, and bulk operations
 * Builds on change-control.js with additional features
 */

const ChangeAudit = {
    filters: {
        actor: null,
        filePath: null,
        dateRange: { start: null, end: null },
        changeType: null
    },

    selectedChanges: new Set(),

    async init() {
        console.log('Initializing Change Audit...');
        this.setupFilters();
        this.setupBulkActions();
        await this.loadFilteredHistory();
        this.renderVisualization();
    },

    setup Filters() {
        // Actor filter
        const actorSelect = document.getElementById('filter-actor');
        if (actorSelect) {
            actorSelect.addEventListener('change', (e) => {
                this.filters.actor = e.target.value || null;
                this.loadFilteredHistory();
            });
        }

        // File path filter
        const fileInput = document.getElementById('filter-file-path');
        if (fileInput) {
            fileInput.addEventListener('input', (e) => {
                this.filters.filePath = e.target.value || null;
                this.loadFilteredHistory();
            });
        }

        // Date range
        const startDate = document.getElementById('filter-start-date');
        const endDate = document.getElementById('filter-end-date');
        if (startDate && endDate) {
            startDate.addEventListener('change', (e) => {
                this.filters.dateRange.start = e.target.value || null;
                this.loadFilteredHistory();
            });
            endDate.addEventListener('change', (e) => {
                this.filters.dateRange.end = e.target.value || null;
                this.loadFilteredHistory();
            });
        }

        // Change type filter
        const typeSelect = document.getElementById('filter-change-type');
        if (typeSelect) {
            typeSelect.addEventListener('change', (e) => {
                this.filters.changeType = e.target.value || null;
                this.loadFilteredHistory();
            });
        }

        // Reset filters button
        const resetBtn = document.getElementById('reset-filters-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetFilters());
        }
    },

    async loadFilteredHistory() {
        try {
            const params = new URLSearchParams();
            if (this.filters.actor) params.append('actor', this.filters.actor);
            if (this.filters.filePath) params.append('file_path', this.filters.filePath);
            if (this.filters.changeType) params.append('change_type', this.filters.changeType);
            params.append('limit', '100');

            const response = await fetch(`/api/v1/changes/history?${params}`);
            const data = await response.json();

            let changes = data.changes || [];

            // Apply date filtering (client-side)
            if (this.filters.dateRange.start || this.filters.dateRange.end) {
                changes = changes.filter(change => {
                    const changeDate = new Date(change.timestamp);
                    if (this.filters.dateRange.start) {
                        const start = new Date(this.filters.dateRange.start);
                        if (changeDate < start) return false;
                    }
                    if (this.filters.dateRange.end) {
                        const end = new Date(this.filters.dateRange.end);
                        if (changeDate > end) return false;
                    }
                    return true;
                });
            }

            this.renderAdvancedHistory(changes);
            this.updateStats(changes);
        } catch (error) {
            console.error('Failed to load filtered history:', error);
            window.showToast?.('Failed to load change history', 'error');
        }
    },

    renderAdvancedHistory(changes) {
        const container = document.getElementById('audit-history-table');
        if (!container) return;

        if (changes.length === 0) {
            container.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #9CA3AF;">No changes found</td></tr>';
            return;
        }

        container.innerHTML = changes.map(change => `
            <tr class="audit-row" data-change-id="${change.backup_id}">
                <td>
                    <input type="checkbox" 
                           onchange="ChangeAudit.toggleSelection('${change.backup_id}', this.checked)"
                           ${this.selectedChanges.has(change.backup_id) ? 'checked' : ''}>
                </td>
                <td>${this.formatDateTime(change.timestamp)}</td>
                <td><code>${this.truncate(change.file_path, 40)}</code></td>
                <td><span class="change-type-badge ${change.change_type}">${change.change_type}</span></td>
                <td><span class="actor-badge">${change.actor}</span></td>
                <td class="reason-cell">${change.reason}</td>
                <td>
                    <button class="action-btn" onclick="ChangeAudit.viewDiff('${change.backup_id}')" title="View Diff">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn" onclick="ChangeAudit.downloadBackup('${change.backup_id}')" title="Download">
                        <i class="fas fa-download"></i>
                    </button>
                    ${change.rollback_available ? `
                        <button class="action-btn rollback" onclick="ChangeAudit.confirmRollback('${change.backup_id}')" title="Rollback">
                            <i class="fas fa-undo"></i>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `).join('');
    },

    updateStats(changes) {
        const statsContainer = document.getElementById('audit-stats');
        if (!statsContainer) return;

        const byType = {};
        const byActor = {};
        let totalSize = 0;

        changes.forEach(change => {
            byType[change.change_type] = (byType[change.change_type] || 0) + 1;
            byActor[change.actor] = (byActor[change.actor] || 0) + 1;
            totalSize += change.diff_size || 0;
        });

        statsContainer.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${changes.length}</div>
                <div class="stat-label">Total Changes</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${Object.keys(byActor).length}</div>
                <div class="stat-label">Contributors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${(totalSize / 1024 / 1024).toFixed(2)} MB</div>
                <div class="stat-label">Storage Used</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${byType.modify || 0}</div>
                <div class="stat-label">Modifications</div>
            </div>
        `;
    },

    setupBulkActions() {
        const selectAllBtn = document.getElementById('select-all-changes-btn');
        const deselectAllBtn = document.getElementById('deselect-all-changes-btn');
        const exportBtn = document.getElementById('export-selected-btn');
        const compareBtn = document.getElementById('compare-selected-btn');

        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => this.selectAll());
        }

        if (deselectAllBtn) {
            deselectAllBtn.addEventListener('click', () => this.deselectAll());
        }

        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportSelected());
        }

        if (compareBtn) {
            compareBtn.addEventListener('click', () => this.compareSelected());
        }
    },

    toggleSelection(changeId, selected) {
        if (selected) {
            this.selectedChanges.add(changeId);
        } else {
            this.selectedChanges.delete(changeId);
        }
        this.updateSelectionCount();
    },

    selectAll() {
        document.querySelectorAll('.audit-row').forEach(row => {
            const checkbox = row.querySelector('input[type="checkbox"]');
            if (checkbox) {
                checkbox.checked = true;
                const changeId = row.dataset.changeId;
                this.selectedChanges.add(changeId);
            }
        });
        this.updateSelectionCount();
    },

    deselectAll() {
        document.querySelectorAll('.audit-row input[type="checkbox"]').forEach(cb => {
            cb.checked = false;
        });
        this.selectedChanges.clear();
        this.updateSelectionCount();
    },

    updateSelectionCount() {
        const counter = document.getElementById('selected-count');
        if (counter) {
            counter.textContent = this.selectedChanges.size;
        }
    },

    async viewDiff(backupId) {
        try {
            const response = await fetch(`/api/v1/changes/${backupId}`);
            const data = await response.json();

            // Open modal with diff visualization
            this.showDiffModal(data.change);
        } catch (error) {
            console.error('Failed to load diff:', error);
            window.showToast?.('Failed to load diff', 'error');
        }
    },

    showDiffModal(change) {
        const modal = document.getElementById('diff-modal');
        if (!modal) return;

        const diffContainer = modal.querySelector('.diff-content');
        if (diffContainer) {
            diffContainer.innerHTML = `
                <div class="diff-header">
                    <h3>${change.file_path}</h3>
                    <p>Changed by <strong>${change.actor}</strong> on ${this.formatDateTime(change.timestamp)}</p>
                    <p>${change.reason}</p>
                </div>
                <div class="diff-body">
                    <pre><code>${this.escapeHtml(change.diff || 'No diff available')}</code></pre>
                </div>
            `;
        }

        modal.style.display = 'flex';
    },

    async downloadBackup(backupId) {
        try {
            const response = await fetch(`/api/v1/changes/${backupId}/download`);
            const blob = await response.blob();

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `backup_${backupId}.gz`;
            a.click();
            window.URL.revokeObjectURL(url);

            window.showToast?.('Backup downloaded', 'success');
        } catch (error) {
            console.error('Failed to download backup:', error);
            window.showToast?.('Download failed', 'error');
        }
    },

    async confirmRollback(backupId) {
        if (confirm('Are you sure you want to rollback this change? This will restore the file to its previous state.')) {
            try {
                const response = await fetch('/api/v1/changes/rollback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ backup_id: backupId })
                });

                if (response.ok) {
                    window.showToast?.('Rollback successful!', 'success');
                    this.loadFilteredHistory();
                } else {
                    throw new Error('Rollback failed');
                }
            } catch (error) {
                console.error('Rollback failed:', error);
                window.showToast?.('Rollback failed', 'error');
            }
        }
    },

    async exportSelected() {
        if (this.selectedChanges.size === 0) {
            window.showToast?.('No changes selected', 'warning');
            return;
        }

        const changeIds = Array.from(this.selectedChanges);
        console.log('Exporting selected changes:', changeIds);
        window.showToast?.(`Exporting ${changeIds.length} changes...`, 'info');

        // Implement export logic
        window.showToast?.('Export feature - Coming soon', 'info');
    },

    compareSelected() {
        if (this.selectedChanges.size !== 2) {
            window.showToast?.('Please select exactly 2 changes to compare', 'warning');
            return;
        }

        const [id1, id2] = Array.from(this.selectedChanges);
        console.log('Comparing changes:', id1, id2);
        window.showToast?.('Comparison feature - Coming soon', 'info');
    },

    renderVisualization() {
        // Render timeline or chart visualization
        const vizContainer = document.getElementById('change-visualization');
        if (vizContainer) {
            vizContainer.innerHTML = '<p style="padding: 20px; text-align: center; color: #9CA3AF;">Visualization - Coming soon</p>';
        }
    },

    resetFilters() {
        this.filters = {
            actor: null,
            filePath: null,
            dateRange: { start: null, end: null },
            changeType: null
        };

        // Reset form inputs
        document.getElementById('filter-actor')?.setValue('');
        document.getElementById('filter-file-path')?.setValue('');
        document.getElementById('filter-start-date')?.setValue('');
        document.getElementById('filter-end-date')?.setValue('');
        document.getElementById('filter-change-type')?.setValue('');

        this.loadFilteredHistory();
        window.showToast?.('Filters reset', 'info');
    },

    formatDateTime(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    truncate(str, maxLen) {
        if (str.length <= maxLen) return str;
        return '...' + str.slice(-(maxLen - 3));
    },

    escapeHTML(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }
};

// Auto-initialize
if (typeof window !== 'undefined') {
    window.ChangeAudit = ChangeAudit;

    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('change-audit-container')) {
            ChangeAudit.init();
        }
    });
}
