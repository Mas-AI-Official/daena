/**
 * Cryptographic utilities for client-side encryption
 * 
 * Uses AES-256-CBC with PBKDF2 key derivation for secure vault secrets.
 * All secrets are encrypted on the client before being sent to the server.
 */
import CryptoJS from 'crypto-js';

// Salt for key derivation - in production, this could be user-specific
const DERIVATION_SALT = 'daena-vault-salt-v2';
const KEY_SIZE = 256 / 32; // 256-bit key
const ITERATIONS = 100000;

// Fallback master key - should be provided by user in production
const FALLBACK_KEY = 'daena-founder-secure-enclave-key-v1';

/**
 * Encrypt a secret using AES-256-CBC with a random IV
 * Returns both ciphertext and IV for storage
 */
export function encryptSecretSecure(
    plaintext: string,
    masterKey: string = FALLBACK_KEY
): { ciphertext: string; iv: string } {
    // Generate random IV
    const iv = CryptoJS.lib.WordArray.random(16);

    // Derive key using PBKDF2
    const key = CryptoJS.PBKDF2(masterKey, DERIVATION_SALT, {
        keySize: KEY_SIZE,
        iterations: ITERATIONS
    });

    // Encrypt using AES-256-CBC
    const encrypted = CryptoJS.AES.encrypt(plaintext, key, {
        iv: iv,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    });

    return {
        ciphertext: encrypted.ciphertext.toString(CryptoJS.enc.Base64),
        iv: iv.toString(CryptoJS.enc.Base64)
    };
}

/**
 * Decrypt a secret using AES-256-CBC with the provided IV
 */
export function decryptSecretSecure(
    ciphertext: string,
    iv: string,
    masterKey: string = FALLBACK_KEY
): string {
    try {
        // Derive key
        const key = CryptoJS.PBKDF2(masterKey, DERIVATION_SALT, {
            keySize: KEY_SIZE,
            iterations: ITERATIONS
        });

        // Decrypt
        const decrypted = CryptoJS.AES.decrypt(
            { ciphertext: CryptoJS.enc.Base64.parse(ciphertext) } as CryptoJS.lib.CipherParams,
            key,
            {
                iv: CryptoJS.enc.Base64.parse(iv),
                mode: CryptoJS.mode.CBC,
                padding: CryptoJS.pad.Pkcs7
            }
        );

        return decrypted.toString(CryptoJS.enc.Utf8);
    } catch (e) {
        console.error('Secure decryption failed:', e);
        return '[DECRYPTION_ERROR]';
    }
}

/**
 * Simple encryption (legacy) - for quick encrypt/decrypt without IV
 * Less secure but compatible with existing stored secrets
 */
export const encryptSecret = (value: string, key: string = FALLBACK_KEY): string => {
    return CryptoJS.AES.encrypt(value, key).toString();
};

/**
 * Simple decryption (legacy) - for quick encrypt/decrypt without IV
 */
export const decryptSecret = (cipherText: string, key: string = FALLBACK_KEY): string => {
    try {
        const bytes = CryptoJS.AES.decrypt(cipherText, key);
        return bytes.toString(CryptoJS.enc.Utf8);
    } catch (e) {
        console.error('Decryption failed:', e);
        return '[DECRYPTION_ERROR]';
    }
};

/**
 * Generate a SHA-256 hash truncated to 12 characters
 */
export const hashIdentifier = (value: string): string => {
    return CryptoJS.SHA256(value).toString(CryptoJS.enc.Hex).substring(0, 12);
};

/**
 * Generate a cryptographically random ID
 */
export function generateSecureId(length: number = 16): string {
    const randomWords = CryptoJS.lib.WordArray.random(length);
    return randomWords.toString(CryptoJS.enc.Hex).substring(0, length * 2);
}

/**
 * Verify data integrity using HMAC-SHA256
 */
export function generateHmac(data: string, secret: string): string {
    return CryptoJS.HmacSHA256(data, secret).toString(CryptoJS.enc.Hex);
}

/**
 * Verify HMAC signature
 */
export function verifyHmac(data: string, signature: string, secret: string): boolean {
    const expected = generateHmac(data, secret);
    return expected === signature;
}
