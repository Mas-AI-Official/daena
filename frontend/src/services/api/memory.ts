import api from './client';

export interface MemoryStats {
    hot: {
        item_count: number;
        size_bytes: number;
        cache_hits: number;
    };
    warm: {
        item_count: number;
        size_bytes: number;
        compression_ratio: number;
    };
    cold: {
        item_count: number;
        size_bytes: number;
        summaries_count: number;
    };
    router: {
        total_requests: number;
        policy_hits: Record<string, number>;
    };
}

export interface MemoryItem {
    id: string;
    content: string;
    data_class: string;
    tier: 'hot' | 'warm' | 'cold';
    timestamp: string;
    metadata?: any;
}

export const memoryApi = {
    getStats: async (): Promise<MemoryStats> => {
        const response = await api.get('/memory/stats');
        return response.data;
    },
    search: async (query: string, topK: number = 10): Promise<{ results: MemoryItem[] }> => {
        const response = await api.post('/memory/search', { query, top_k: topK });
        return response.data;
    },
    runAging: async (): Promise<{ items_demoted: number }> => {
        const response = await api.post('/memory/age');
        return response.data;
    }
};
