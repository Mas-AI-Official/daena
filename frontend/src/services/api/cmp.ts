import api from './client';

export const cmpApi = {
    getGraph: async () => {
        const response = await api.get('/cmp/graph');
        return response.data;
    },
    saveGraph: async (graph: any) => {
        const response = await api.post('/cmp/graph/save', graph);
        return response.data;
    },
    executeGraph: async (startNodeId: string) => {
        const response = await api.post('/cmp/graph/execute', { start_node: startNodeId });
        return response.data;
    }
};
