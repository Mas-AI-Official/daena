import CryptoJS from 'crypto-js';

// In a real production app, the master key would be derived from 
// user password or a secure hardware enclave.
// For this architecture, we use a constant founder key if not provided.
const FALLBACK_KEY = 'daena-founder-secure-enclave-key-v1';

export const encryptSecret = (value: string, key: string = FALLBACK_KEY): string => {
    return CryptoJS.AES.encrypt(value, key).toString();
};

export const decryptSecret = (cipherText: string, key: string = FALLBACK_KEY): string => {
    try {
        const bytes = CryptoJS.AES.decrypt(cipherText, key);
        return bytes.toString(CryptoJS.enc.Utf8);
    } catch (e) {
        console.error('Decryption failed:', e);
        return '[DECRYPTION_ERROR]';
    }
};

export const hashIdentifier = (value: string): string => {
    return CryptoJS.SHA256(value).toString(CryptoJS.enc.Hex).substring(0, 12);
};
