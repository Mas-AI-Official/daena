/**
 * File System and Terminal API Services
 * Provides file operations, terminal execution, and code execution.
 */

import api from './client';

export interface FileNode {
    id: string;
    path: string;
    name: string;
    type: 'file' | 'directory';
    children?: FileNode[];
    extension?: string;
    size?: number;
    modified?: number;
}

export interface ExecutionResult {
    success: boolean;
    output?: string;
    error?: string;
    execution_time_ms?: number;
    exit_code?: number;
}

export const fileSystemApi = {
    /**
     * Get file/directory structure.
     * Tries new IDE endpoint first, then legacy endpoint.
     */
    getStructure: async (): Promise<any> => {
        try {
            // Try new IDE endpoint first
            const response = await api.get('/api/v1/ide/tree');
            return {
                directories: response.data.tree || [],
                root_path: response.data.root || ''
            };
        } catch (error) {
            // Fallback to legacy endpoint
            try {
                const response = await api.get('/files/structure');
                return response.data;
            } catch (fallbackError) {
                console.error('Failed to load file system:', fallbackError);
                return { directories: [], root_path: '' };
            }
        }
    },

    /**
     * Read file contents.
     */
    readFile: async (path: string): Promise<string> => {
        try {
            const response = await api.get(`/files/read/${encodeURIComponent(path)}`);
            return response.data.content;
        } catch (error) {
            // Fallback to new IDE endpoint
            const response = await api.get(`/api/v1/ide/files/${encodeURIComponent(path)}`);
            return response.data.content;
        }
    },

    /**
     * Write/save file contents.
     */
    writeFile: async (path: string, content: string): Promise<void> => {
        try {
            await api.post('/files/write', { file_path: path, content });
        } catch (error) {
            // Fallback to new IDE endpoint
            await api.put(`/api/v1/ide/files/${encodeURIComponent(path)}`, { content });
        }
    },

    /**
     * Create a new file.
     */
    createFile: async (path: string, content: string = ''): Promise<void> => {
        await api.post('/api/v1/ide/files', { path, content });
    },

    /**
     * Delete a file.
     */
    deleteFile: async (path: string): Promise<void> => {
        await api.delete(`/api/v1/ide/files/${encodeURIComponent(path)}`);
    },

    /**
     * Search files by name pattern.
     */
    searchFiles: async (query: string, path: string = ''): Promise<FileNode[]> => {
        const response = await api.get('/api/v1/ide/search', { params: { query, path } });
        return response.data.results || [];
    }
};

export const terminalApi = {
    /**
     * Execute a terminal command.
     */
    execute: async (command: string, cwd?: string): Promise<{ stdout: string; stderr: string; cwd: string }> => {
        try {
            const response = await api.post('/terminal/execute', { command, cwd });
            return response.data;
        } catch (error) {
            // Fallback to new IDE endpoint
            const response = await api.post('/api/v1/ide/terminal', { command, cwd });
            return {
                stdout: response.data.output || '',
                stderr: response.data.error || '',
                cwd: cwd || ''
            };
        }
    }
};

export const codeExecutionApi = {
    /**
     * Execute code in a specific language.
     * Supported: python, javascript, typescript, bash
     */
    execute: async (language: string, code: string): Promise<ExecutionResult> => {
        const response = await api.post('/api/v1/ide/execute', { language, code });
        return response.data;
    },

    /**
     * Get supported languages.
     */
    getSupportedLanguages: (): string[] => {
        return ['python', 'javascript', 'typescript', 'bash'];
    }
};

