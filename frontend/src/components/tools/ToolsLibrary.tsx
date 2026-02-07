import React, { useState, useEffect, useCallback } from 'react';
import { useUIStore } from '@/store/uiStore';
import { Search, Link2, Check, AlertCircle, Loader2 } from 'lucide-react';

interface Tool {
  id: string;
  name: string;
  category: string;
  logo: string;
  description: string;
  connected: boolean;
  auth_type: string;
  popularity: number;
}

export const ToolsLibrary: React.FC = () => {
  const [tools, setTools] = useState<Tool[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectingId, setConnectingId] = useState<string | null>(null);

  const addNotification = useUIStore((state) => state.addNotification);

  const loadTools = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication required');
      }

      const response = await fetch(
        `/api/v1/tools/library?category=${category}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired. Please login again.');
        }
        throw new Error(`Failed to load tools: ${response.statusText}`);
      }

      const data = await response.json();
      setTools(data.tools || []);
      setCategories(data.categories || []);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to load tools';
      setError(errorMessage);
      addNotification({
        type: 'error',
        title: 'Error',
        message: errorMessage
      });
    } finally {
      setLoading(false);
    }
  }, [category, addNotification]);

  useEffect(() => {
    loadTools();
  }, [loadTools]);

  const connectTool = async (toolId: string) => {
    setConnectingId(toolId);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication required');
      }

      const response = await fetch('/api/v1/tools/connect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          tool_id: toolId,
          credentials: {} // In prod, collect actual credentials
        })
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired');
        }
        throw new Error(`Connection failed: ${response.statusText}`);
      }

      // Update local state
      setTools(prev => prev.map(t =>
        t.id === toolId ? { ...t, connected: true } : t
      ));

      addNotification({
        type: 'success',
        title: 'Connected',
        message: 'Tool connected successfully'
      });

    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'Connection Failed',
        message: err.message
      });
    } finally {
      setConnectingId(null);
    }
  };

  const filteredTools = tools.filter(tool =>
    tool.name.toLowerCase().includes(search.toLowerCase()) ||
    tool.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="tools-library p-6">
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg flex items-center gap-2 text-red-400">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
          <button
            onClick={loadTools}
            className="ml-auto text-xs underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-3 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search tools..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredTools.map(tool => (
            <div
              key={tool.id}
              className="border border-gray-700 bg-gray-800/50 rounded-lg p-4 hover:border-blue-500/50 transition-all hover:shadow-lg hover:shadow-blue-500/10"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center text-lg">
                  {tool.logo ? (
                    <img src={tool.logo} alt={tool.name} className="w-6 h-6 object-contain" />
                  ) : (
                    <span>🔧</span>
                  )}
                </div>
                <span className="px-2 py-1 text-xs bg-gray-700 rounded-full text-gray-300">
                  {tool.category}
                </span>
              </div>

              <h3 className="font-semibold text-gray-200 mb-1">{tool.name}</h3>
              <p className="text-sm text-gray-400 mb-4 line-clamp-2">{tool.description}</p>

              <button
                onClick={() => !tool.connected && connectTool(tool.id)}
                disabled={tool.connected || connectingId === tool.id}
                className={`
                  w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
                  ${tool.connected
                    ? 'bg-green-600/20 text-green-400 border border-green-600/50'
                    : connectingId === tool.id
                      ? 'bg-blue-600/50 text-blue-200 cursor-wait'
                      : 'bg-blue-600 hover:bg-blue-700 text-white'
                  }
                `}
              >
                {connectingId === tool.id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : tool.connected ? (
                  <>
                    <Check className="w-4 h-4" />
                    Connected
                  </>
                ) : (
                  <>
                    <Link2 className="w-4 h-4" />
                    Connect
                  </>
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      {!loading && filteredTools.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No tools found matching your search
        </div>
      )}
    </div>
  );
};
