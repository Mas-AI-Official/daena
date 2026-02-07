/**
 * React hooks for real-time data synchronization
 */
import { useEffect, useCallback, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { getWebSocketClient } from '@/services/websocket';
import { toast } from 'sonner';

// ============================================================
// Hook for real-time chat
// ============================================================
export function useRealtimeChat() {
  const dispatch = useDispatch();
  const messages = useSelector((state: any) => state.chat?.messages || []);
  const isStreaming = useSelector((state: any) => state.chat?.isStreaming || false);

  const sendMessage = useCallback((message: string) => {
    const ws = getWebSocketClient();
    ws.sendChatMessage(message);
    dispatch({ type: 'chat/messageSent', payload: message });
  }, [dispatch]);

  return { messages, isStreaming, sendMessage };
}

// ============================================================
// Hook for real-time skills
// ============================================================
export function useRealtimeSkills() {
  const dispatch = useDispatch();
  const skills = useSelector((state: any) => state.skills?.items || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleOperator = useCallback(async (skillId: string, operators: string[]) => {
    setLoading(true);
    setError(null);

    try {
      // Optimistic update
      dispatch({
        type: 'skills/updateOperatorsOptimistic',
        payload: { skillId, operators }
      });

      // API call
      const response = await fetch(`/api/v1/skills/${skillId}/operators`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(operators)
      });

      if (!response.ok) {
        throw new Error(`Failed to update operators: ${response.statusText}`);
      }

      toast.success('Skill operators updated');
    } catch (err: any) {
      setError(err.message);
      toast.error('Failed to update operators');
      // Revert optimistic update
      dispatch({ type: 'skills/revertOptimisticUpdate', payload: { skillId } });
    } finally {
      setLoading(false);
    }
  }, [dispatch]);

  return { skills, toggleOperator, loading, error };
}

// ============================================================
// Hook for real-time brain/models
// ============================================================
export function useRealtimeModels() {
  const dispatch = useDispatch();
  const models = useSelector((state: any) => state.brain?.models || []);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scanOllama = useCallback(async () => {
    setIsScanning(true);
    setError(null);

    try {
      dispatch({ type: 'brain/setScanning', payload: true });

      const response = await fetch('/api/v1/brain/models/scan', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error(`Scan failed: ${response.statusText}`);
      }

      const data = await response.json();
      dispatch({ type: 'brain/modelsScanned', payload: data.models });

      toast.success(`Found ${data.count} models`);
      return data;
    } catch (err: any) {
      setError(err.message);
      toast.error('Scan failed');
      throw err;
    } finally {
      setIsScanning(false);
      dispatch({ type: 'brain/setScanning', payload: false });
    }
  }, [dispatch]);

  const toggleModel = useCallback(async (modelId: string, enabled: boolean) => {
    try {
      // Optimistic update
      dispatch({
        type: 'brain/updateModelStatus',
        payload: { modelId, enabled }
      });

      // API call
      const endpoint = enabled ? 'enable' : 'disable';
      const response = await fetch(`/api/v1/brain/models/${modelId}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error(`Toggle failed: ${response.statusText}`);
      }

      toast.success(`${enabled ? 'Enabled' : 'Disabled'} model`);
    } catch (err: any) {
      setError(err.message);
      toast.error('Failed to toggle model');
      // Revert optimistic update
      dispatch({
        type: 'brain/updateModelStatus',
        payload: { modelId, enabled: !enabled }
      });
    }
  }, [dispatch]);

  return { models, scanOllama, toggleModel, isScanning, error };
}

// ============================================================
// Hook for real-time projects
// ============================================================
export function useRealtimeProjects(projectId?: string) {
  const dispatch = useDispatch();
  const project = useSelector((state: any) =>
    projectId ? state.projects?.byId?.[projectId] : null
  );
  const projects = useSelector((state: any) => state.projects?.items || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addComment = useCallback(async (text: string) => {
    if (!projectId) return;

    try {
      // Optimistic update
      const tempComment = {
        id: `temp-${Date.now()}`,
        text,
        created_at: new Date().toISOString(),
        pending: true
      };

      dispatch({
        type: 'projects/addCommentOptimistic',
        payload: { projectId, comment: tempComment }
      });

      // API call
      const response = await fetch(`/api/v1/projects/${projectId}/comments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ text })
      });

      if (!response.ok) {
        throw new Error(`Failed to add comment: ${response.statusText}`);
      }

    } catch (err: any) {
      setError(err.message);
      toast.error('Failed to add comment');
      // Revert optimistic update
      dispatch({ type: 'projects/revertComment', payload: { projectId, tempId: `temp-${Date.now()}` } });
    }
  }, [dispatch, projectId]);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/projects', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch projects: ${response.statusText}`);
      }

      const data = await response.json();
      dispatch({ type: 'projects/setProjects', payload: data.projects });
    } catch (err: any) {
      setError(err.message);
      toast.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [dispatch]);

  const createProject = useCallback(async (name: string, description: string = '') => {
    try {
      const response = await fetch('/api/v1/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ name, description })
      });

      if (!response.ok) {
        throw new Error(`Failed to create project: ${response.statusText}`);
      }

      toast.success('Project created');
      fetchProjects();
    } catch (err: any) {
      setError(err.message);
      toast.error('Failed to create project');
    }
  }, [fetchProjects]);

  return { project, projects, addComment, fetchProjects, createProject, loading, error };
}

// ============================================================
// Hook for project list
// ============================================================
export function useProjectList() {
  const dispatch = useDispatch();
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/projects', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`);
      }

      const data = await response.json();
      setProjects(data.projects || []);
    } catch (err: any) {
      setError(err.message);
      toast.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return { projects, loading, error, refetch: fetchProjects };
}
