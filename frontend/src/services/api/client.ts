import axios from 'axios';
import { useAuthStore } from '../../store/authStore';

const api = axios.create({
    baseURL: '/api/v1',
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to add token
api.interceptors.request.use(
    (config) => {
        const token = useAuthStore.getState().token;
        if (token) {
            // Use X-Execution-Token if it's the execution token, or Bearer if it's JWT
            // For now, assuming Founder mode uses Bearer or custom header.
            // Based on backend audit "X-Execution-Token" is preferred for tools.
            // We'll stick to standard Bearer for now, unless specific routes need otherwise.

            // However, the backend audit emphasized X-Execution-Token for tool execution.
            // Let's add it if we have it.
            // If the token is just a "daena-token", use Authorization header.
            config.headers.Authorization = `Bearer ${token}`;

            // Also helpful for some endpoints:
            // config.headers['X-Execution-Token'] = token; 
        }
        return config;
    },
    (error) => Promise.reject(error)
);

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401 || error.response?.status === 403) {
            console.error('Authentication Error:', error.response.data);
            // Optionally redirect to login or clear token
            // useAuthStore.getState().logout();
        }
        return Promise.reject(error);
    }
);

export default api;
