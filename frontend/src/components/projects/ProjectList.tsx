import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUIStore } from '@/store/uiStore';
import { Plus, Clock, Loader2, AlertCircle, MoreVertical } from 'lucide-react';

interface Project {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'completed' | 'archived' | 'paused';
  progress: number;
  created_at: string;
}

export const ProjectList: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const addNotification = useUIStore((state) => state.addNotification);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication required');
      }

      const response = await fetch('/api/v1/projects', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired. Please login again.');
        }
        throw new Error(`Failed to load projects: ${response.statusText}`);
      }

      const data = await response.json();
      setProjects(data.projects || []);
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to load projects';
      setError(errorMessage);
      addNotification({
        type: 'error',
        title: 'Error',
        message: errorMessage
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const createProject = async () => {
    if (!newProjectName.trim()) return;

    setCreating(true);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication required');
      }

      const response = await fetch('/api/v1/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          name: newProjectName,
          description: ''
        })
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired');
        }
        throw new Error(`Failed to create: ${response.statusText}`);
      }

      const data = await response.json();

      addNotification({
        type: 'success',
        title: 'Project Created',
        message: `${newProjectName} has been created`
      });

      setNewProjectName('');
      setShowCreateModal(false);

      // Navigate to new project
      if (data.project?.id || data.id) {
        navigate(`/projects/${data.project?.id || data.id}`);
      } else {
        // Refresh list
        loadProjects();
      }

    } catch (err: any) {
      addNotification({
        type: 'error',
        title: 'Creation Failed',
        message: err.message
      });
    } finally {
      setCreating(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.round(diffMs / 60000);
    const diffHours = Math.round(diffMs / 3600000);
    const diffDays = Math.round(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 30) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-500/20 text-green-400 border-green-500/50';
      case 'paused': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50';
      case 'completed': return 'bg-blue-500/20 text-blue-400 border-blue-500/50';
      case 'archived': return 'bg-gray-500/20 text-gray-400 border-gray-500/50';
      default: return 'bg-gray-500/20 text-gray-400';
    }
  };

  return (
    <div className="project-list p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Projects</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg flex items-center gap-2 text-red-400">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
          <button
            onClick={loadProjects}
            className="ml-auto text-sm underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map(project => (
            <div
              key={project.id}
              onClick={() => navigate(`/projects/${project.id}`)}
              className="group border border-gray-700 bg-gray-800/50 rounded-lg p-4 hover:border-blue-500/50 hover:bg-gray-800 transition-all cursor-pointer"
            >
              <div className="flex justify-between items-start mb-3">
                <h3 className="text-lg font-semibold text-gray-200 group-hover:text-blue-400 transition-colors">
                  {project.name}
                </h3>
                <span className={`px-2 py-1 text-xs border rounded-full ${getStatusColor(project.status)}`}>
                  {project.status}
                </span>
              </div>

              <p className="text-sm text-gray-400 mb-4 line-clamp-2">
                {project.description || 'No description'}
              </p>

              <div className="space-y-2">
                <div className="flex justify-between text-sm text-gray-400">
                  <span>Progress</span>
                  <span>{project.progress || 0}%</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all"
                    style={{ width: `${project.progress || 0}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center mt-4 text-sm text-gray-500">
                <Clock className="w-4 h-4 mr-1" />
                {formatDate(project.created_at)}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && projects.length === 0 && !error && (
        <div className="text-center py-12">
          <div className="text-gray-500 mb-4">No projects yet</div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="text-blue-400 hover:text-blue-300 underline"
          >
            Create your first project
          </button>
        </div>
      )}

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 w-full max-w-md mx-4">
            <h2 className="text-xl font-semibold text-gray-200 mb-4">Create New Project</h2>

            <input
              type="text"
              placeholder="Project name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && createProject()}
              className="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 mb-4"
              autoFocus
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createProject}
                disabled={!newProjectName.trim() || creating}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800/50 disabled:cursor-not-allowed rounded-lg text-white font-medium transition-colors"
              >
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Create'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
