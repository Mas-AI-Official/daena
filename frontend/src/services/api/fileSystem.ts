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

export const fileSystemApi = {
    getStructure: async (): Promise<any> => {
        const response = await api.get('/files/structure');
        return response.data;
    },

    readFile: async (path: string): Promise<string> => {
        const response = await api.get(`/files/read/${encodeURIComponent(path)}`);
        // Handle base64 if needed, but for now assuming text or handled by backend
        return response.data.content;
    },

    writeFile: async (path: string, content: string): Promise<void> => {
        await api.post('/files/write', { file_path: path, content });
    }
};

export const terminalApi = {
    execute: async (command: string, cwd?: string): Promise<{ stdout: string, stderr: string, cwd: string }> => {
        const response = await api.post('/terminal/execute', { command, cwd });
        return response.data;
    }
};
