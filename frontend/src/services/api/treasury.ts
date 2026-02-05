import api from './client';

export interface TreasuryTransaction {
    id: string;
    type: 'MINT' | 'SPEND' | 'REWARD' | 'DEPOSIT';
    amount: string;
    entity: string;
    date: string;
}

export interface TreasuryStatus {
    success: boolean;
    daena_balance: string;
    nft_minted: number;
    eth_held: string;
    total_supply: string;
    treasury_address: string;
    network: string;
    monthly_spend: string;
    transactions: TreasuryTransaction[];
}

export const treasuryApi = {
    getStatus: async (): Promise<TreasuryStatus> => {
        const response = await api.get('/treasury/status');
        return response.data;
    }
};
