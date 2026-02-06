import api from './client';

export interface ChatSession {
    id: string;
    title: string;
    updated_at: string;
    message_count: number;
    last_message?: string;
}

export interface ChatHistoryResponse {
    sessions: ChatSession[];
    total: number;
    next_cursor?: string;
}

export const chatApi = {
    getHistory: async (params: { limit?: number; cursor?: string; search?: string } = {}): Promise<ChatHistoryResponse> => {
        const response = await api.get('/chat/history', { params });
        return response.data;
    },

    deleteSession: async (sessionId: string) => {
        const response = await api.delete(`/chat/sessions/${sessionId}`);
        return response.data;
    },

    renameSession: async (sessionId: string, title: string) => {
        const response = await api.patch(`/chat/sessions/${sessionId}`, { title });
        return response.data;
    },

    sendMessage: async (message: string, sessionId?: string) => {
        const response = await api.post('/daena/chat', { message, session_id: sessionId });
        return response.data;
    }
};
