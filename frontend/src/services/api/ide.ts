/**
 * IDE API Service
 * Provides endpoints for file operations, code execution, and terminal commands.
 */

import api from './client';

export interface FileInfo {
    path: string;
    name: string;
    type: 'file' | 'directory';
    size?: number;
    modified?: string;
    extension?: string;
}

export interface FileTreeNode {
    id: string;
    name: string;
    type: 'file' | 'directory';
    path: string;
    children?: FileTreeNode[];
    extension?: string;
}

export interface ExecutionResult {
    success: boolean;
    output?: string;
    error?: string;
    execution_time_ms?: number;
    exit_code?: number;
}

export const ideApi = {
    // File Operations
    async createFile(path: string, content: string = ''): Promise<{ path: string; message: string }> {
        const response = await api.post('/api/v1/ide/files', { path, content });
        return response.data;
    },

    async readFile(path: string): Promise<{ path: string; content: string; language?: string }> {
        const response = await api.get(`/api/v1/ide/files/${encodeURIComponent(path)}`);
        return response.data;
    },

    async updateFile(path: string, content: string): Promise<{ path: string; message: string }> {
        const response = await api.put(`/api/v1/ide/files/${encodeURIComponent(path)}`, { content });
        return response.data;
    },

    async deleteFile(path: string): Promise<{ path: string; message: string }> {
        const response = await api.delete(`/api/v1/ide/files/${encodeURIComponent(path)}`);
        return response.data;
    },

    // File Tree
    async getFileTree(path: string = ''): Promise<FileTreeNode> {
        const response = await api.get('/api/v1/ide/tree', { params: { path } });
        return response.data;
    },

    async searchFiles(query: string, path: string = ''): Promise<FileInfo[]> {
        const response = await api.get('/api/v1/ide/search', { params: { query, path } });
        return response.data.results;
    },

    // Code Execution
    async executeCode(language: string, code: string): Promise<ExecutionResult> {
        const response = await api.post('/api/v1/ide/execute', { language, code });
        return response.data;
    },

    // Terminal Commands
    async runTerminalCommand(command: string, cwd?: string): Promise<ExecutionResult> {
        const response = await api.post('/api/v1/ide/terminal', { command, cwd });
        return response.data;
    },

    // Workspace Info
    async getWorkspaceInfo(): Promise<{
        root: string;
        total_files: number;
        total_size: number;
    }> {
        const response = await api.get('/api/v1/ide/workspace');
        return response.data;
    }
};
