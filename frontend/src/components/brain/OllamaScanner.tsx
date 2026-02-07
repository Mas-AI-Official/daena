import React, { useState } from 'react';
import { useUIStore } from '@/store/uiStore';
import { Scan, Loader2, AlertCircle } from 'lucide-react';

export const OllamaScanner: React.FC = () => {
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const addNotification = useUIStore((state) => state.addNotification);

  const handleScan = async () => {
    setIsScanning(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication required');
      }

      const response = await fetch('/api/v1/brain/models/scan', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired. Please login again.');
        }
        if (response.status === 503) {
          throw new Error('Ollama service unavailable. Is Ollama running?');
        }
        throw new Error(`Scan failed: ${response.statusText}`);
      }

      const data = await response.json();

      addNotification({
        type: 'success',
        title: 'Scan Complete',
        message: `Found ${data.count} models`,
        duration: 3000
      });
    } catch (err: any) {
      const errorMessage = err.message || 'Scan failed';
      setError(errorMessage);
      addNotification({
        type: 'error',
        title: 'Scan Failed',
        message: errorMessage,
        duration: 5000
      });
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <div className="ollama-scanner">
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg flex items-center gap-2 text-red-400">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      <button
        onClick={handleScan}
        disabled={isScanning}
        className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800/50 disabled:cursor-not-allowed rounded-lg transition-colors"
      >
        {isScanning ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Scan className="w-4 h-4" />
        )}
        <span>{isScanning ? 'Scanning...' : 'Scan Ollama'}</span>
      </button>
    </div>
  );
};
