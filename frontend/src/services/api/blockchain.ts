import api from './client';

export interface TokenBalance {
    address: string;
    balance: string;
    symbol: string;
    staked: string;
}

export interface NFTSlot {
    slot_id: number;
    occupied: boolean;
    agent_id: string | null;
    cost: string;
}

export const blockchainApi = {
    getBalance: async (address: string) => {
        const response = await api.get<TokenBalance>(`/token/balance/${address}`);
        return response.data;
    },
    getSupply: async () => {
        const response = await api.get('/token/supply');
        return response.data;
    },
    getSlots: async () => {
        const response = await api.get<NFTSlot[]>('/nft/slots');
        return response.data;
    },
    mintAgent: async (name: string, department: string) => {
        const response = await api.post('/nft/mint', { name, department });
        return response.data;
    }
};
