/**
 * React hooks for real-time data synchronization
 * Works with Zustand stores and WebSocket events
 */
import { useEffect, useCallback, useState } from 'react';
import { getWebSocketClient } from '@/services/websocket';
import { useUIStore } from '@/store/uiStore';

// ============================================================
// Hook for real-time chat
// ============================================================
export function useRealtimeChat() {
  const [messages, setMessages] = useState<any[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const addNotification = useUIStore((state) => state.addNotification);

  useEffect(() => {
    const ws = getWebSocketClient();

    const handleChatChunk = (data: any) => {
      setMessages(prev => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage && lastMessage.role === 'assistant') {
          return [...prev.slice(0, -1), { ...lastMessage, content: lastMessage.content + data.content }];
        }
        return [...prev, { id: Date.now().toString(), role: 'assistant', content: data.content, timestamp: new Date().toISOString() }];
      });
    };

    const handleActionsCompleted = (data: any) => {
      setIsStreaming(false);
    };

    ws.on('chat.chunk', handleChatChunk);
    ws.on('actions.completed', handleActionsCompleted);

    return () => {
      ws.off('chat.chunk', handleChatChunk);
      ws.off('actions.completed', handleActionsCompleted);
    };
  }, []);

  const sendMessage = useCallback((message: string) => {
    const ws = getWebSocketClient();
    setMessages(prev => [...prev, { id: Date.now().toString(), role: 'user', content: message, timestamp: new Date().toISOString() }]);
    setIsStreaming(true);
    ws.sendChatMessage(message);
  }, []);

  return { messages, isStreaming, sendMessage, setMessages };
}

// ============================================================
// Hook for real-time skills
// ============================================================
export function useRealtimeSkills() {
  const [skills, setSkills] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const addNotification = useUIStore((state) => state.addNotification);

  useEffect(() => {
    const ws = getWebSocketClient();

    const handleOperatorsUpdated = (data: any) => {
      setSkills(prev => prev.map(skill =>
        skill.id === data.skill_id ? { ...skill, operators: data.operators } : skill
      ));
    };

    ws.on('skill.operators_updated', handleOperatorsUpdated);

    return () => {
      ws.off('skill.operators_updated', handleOperatorsUpdated);
    };
  }, []);

  const toggleOperator = useCallback(async (skillId: string, operators: string[]) => {
    setLoading(true);
    setError(null);

    try {
      // Optimistic update
      setSkills(prev => prev.map(skill =>
        skill.id === skillId ? { ...skill, operators } : skill
      ));

      // API call
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/v1/skills/${skillId}/operators`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(operators)
      });

      if (!response.ok) {
        throw new Error(`Failed to update operators: ${response.statusText}`);
      }

      addNotification({
        type: 'success',
        title: 'Success',
        message: 'Skill operators updated'
      });
    } catch (err: any) {
      setError(err.message);
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to update operators'
      });
      // Revert optimistic update would happen via WebSocket event
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  const fetchSkills = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/skills', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setSkills(data.skills || []);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  return { skills, toggleOperator, fetchSkills, loading, error, setSkills };
}

// ============================================================
// Hook for real-time brain/models
// ============================================================
export function useRealtimeModels() {
  const [models, setModels] = useState<any[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const addNotification = useUIStore((state) => state.addNotification);

  useEffect(() => {
    const ws = getWebSocketClient();

    const handleModelEnabled = (data: any) => {
      setModels(prev => prev.map(m =>
        m.id === data.model_id ? { ...m, enabled: true } : m
      ));
    };

    const handleModelDisabled = (data: any) => {
      setModels(prev => prev.map(m =>
        m.id === data.model_id ? { ...m, enabled: false } : m
      ));
    };

    ws.on('model.enabled', handleModelEnabled);
    ws.on('model.disabled', handleModelDisabled);

    return () => {
      ws.off('model.enabled', handleModelEnabled);
      ws.off('model.disabled', handleModelDisabled);
    };
  }, []);

  const scanOllama = useCallback(async () => {
    setIsScanning(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/brain/models/scan', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error(`Scan failed: ${response.statusText}`);
      }

      const data = await response.json();
      setModels(data.models || []);

      addNotification({
        type: 'success',
        title: 'Scan Complete',
        message: `Found ${data.count} models`
      });

      return data;
    } catch (err: any) {
      setError(err.message);
      addNotification({
        type: 'error',
        title: 'Scan Failed',
        message: err.message
      });
      throw err;
    } finally {
      setIsScanning(false);
    }
  }, [addNotification]);

  const toggleModel = useCallback(async (modelId: string, enabled: boolean) => {
    try {
      // Optimistic update
      setModels(prev => prev.map(m =>
        m.id === modelId ? { ...m, enabled } : m
      ));

      const token = localStorage.getItem('token');
      const endpoint = enabled ? 'enable' : 'disable';
      const response = await fetch(`/api/v1/brain/models/${modelId}/${endpoint}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error(`Toggle failed: ${response.statusText}`);
      }
    } catch (err: any) {
      setError(err.message);
      // Revert
      setModels(prev => prev.map(m =>
        m.id === modelId ? { ...m, enabled: !enabled } : m
      ));
    }
  }, []);

  return { models, scanOllama, toggleModel, isScanning, error, setModels };
}

// ============================================================
// Hook for real-time projects
// ============================================================
export function useRealtimeProjects(projectId?: string) {
  const [project, setProject] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const addNotification = useUIStore((state) => state.addNotification);

  useEffect(() => {
    const ws = getWebSocketClient();

    const handleProjectCreated = (data: any) => {
      setProjects(prev => [data.project, ...prev]);
    };

    const handleProjectUpdated = (data: any) => {
      setProjects(prev => prev.map(p =>
        p.id === data.project?.id ? data.project : p
      ));
      if (projectId && data.project?.id === projectId) {
        setProject(data.project);
      }
    };

    const handleCommentAdded = (data: any) => {
      if (projectId === data.project_id) {
        setProject((prev: any) => ({
          ...prev,
          comments: [data.comment, ...(prev?.comments || [])]
        }));
      }
    };

    ws.on('project.created', handleProjectCreated);
    ws.on('project.updated', handleProjectUpdated);
    ws.on('project.comment_added', handleCommentAdded);

    return () => {
      ws.off('project.created', handleProjectCreated);
      ws.off('project.updated', handleProjectUpdated);
      ws.off('project.comment_added', handleCommentAdded);
    };
  }, [projectId]);

  const addComment = useCallback(async (text: string) => {
    if (!projectId) return;

    try {
      const token = localStorage.getItem('token');
      await fetch(`/api/v1/projects/${projectId}/comments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text })
      });
    } catch (err: any) {
      setError(err.message);
    }
  }, [projectId]);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/projects', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setProjects(data.projects || []);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const createProject = useCallback(async (name: string, description: string = '') => {
    try {
      const token = localStorage.getItem('token');
      await fetch('/api/v1/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ name, description })
      });
      addNotification({
        type: 'success',
        title: 'Success',
        message: 'Project created'
      });
    } catch (err: any) {
      setError(err.message);
    }
  }, [addNotification]);

  return { project, projects, addComment, fetchProjects, createProject, loading, error, setProject, setProjects };
}

// ============================================================
// Hook for project list
// ============================================================
export function useProjectList() {
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const addNotification = useUIStore((state) => state.addNotification);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/projects', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`);
      }

      const data = await response.json();
      setProjects(data.projects || []);
    } catch (err: any) {
      setError(err.message);
      addNotification({
        type: 'error',
        title: 'Error',
        message: err.message
      });
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  return { projects, loading, error, refetch: fetchProjects, setProjects };
}

// ============================================================
// Hook for real-time CMP integrations
// ============================================================
export function useRealtimeIntegrations() {
  const [instances, setInstances] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const addNotification = useUIStore((state) => state.addNotification);

  useEffect(() => {
    const ws = getWebSocketClient();

    const handleIntegrationConnected = (data: any) => {
      setInstances(prev => [...prev, data.instance]);
      addNotification({
        type: 'success',
        title: 'Integration Connected',
        message: `${data.instance?.name || 'Integration'} is now connected`
      });
    };

    const handleIntegrationDisconnected = (data: any) => {
      setInstances(prev => prev.filter(i => i.id !== data.instance_id));
      addNotification({
        type: 'info',
        title: 'Integration Disconnected',
        message: `Integration has been disconnected`
      });
    };

    const handleIntegrationStatusChanged = (data: any) => {
      setInstances(prev => prev.map(i =>
        i.id === data.instance_id ? { ...i, status: data.status } : i
      ));
    };

    const handleIntegrationError = (data: any) => {
      setInstances(prev => prev.map(i =>
        i.id === data.instance_id ? { ...i, status: 'error', last_error: data.error } : i
      ));
      addNotification({
        type: 'error',
        title: 'Integration Error',
        message: data.error || 'An integration error occurred'
      });
    };

    const handleIntegrationActionExecuted = (data: any) => {
      addNotification({
        type: 'success',
        title: 'Action Executed',
        message: `${data.action} completed on ${data.integration_name}`
      });
    };

    ws.on('integration.connected', handleIntegrationConnected);
    ws.on('integration.disconnected', handleIntegrationDisconnected);
    ws.on('integration.status_changed', handleIntegrationStatusChanged);
    ws.on('integration.error', handleIntegrationError);
    ws.on('integration.action_executed', handleIntegrationActionExecuted);

    return () => {
      ws.off('integration.connected', handleIntegrationConnected);
      ws.off('integration.disconnected', handleIntegrationDisconnected);
      ws.off('integration.status_changed', handleIntegrationStatusChanged);
      ws.off('integration.error', handleIntegrationError);
      ws.off('integration.action_executed', handleIntegrationActionExecuted);
    };
  }, [addNotification]);

  const fetchInstances = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/integrations/instances', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`);
      }

      const data = await response.json();
      setInstances(data.instances || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const connectIntegration = useCallback(async (catalogKey: string, name: string, credentials: any) => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/integrations/connect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ catalog_key: catalogKey, name, credentials })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Connection failed');
      }

      const data = await response.json();
      // Instance will be added via WebSocket event
      return data;
    } catch (err: any) {
      setError(err.message);
      addNotification({
        type: 'error',
        title: 'Connection Failed',
        message: err.message
      });
      throw err;
    } finally {
      setLoading(false);
    }
  }, [addNotification]);

  const disconnectIntegration = useCallback(async (instanceId: string) => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`/api/v1/integrations/${instanceId}/disconnect`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      // Instance removal will happen via WebSocket event
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const executeAction = useCallback(async (instanceId: string, action: string, params: any = {}) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/v1/integrations/${instanceId}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ action, params })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Action failed');
      }

      return await response.json();
    } catch (err: any) {
      setError(err.message);
      addNotification({
        type: 'error',
        title: 'Action Failed',
        message: err.message
      });
      throw err;
    }
  }, [addNotification]);

  return {
    instances,
    loading,
    error,
    fetchInstances,
    connectIntegration,
    disconnectIntegration,
    executeAction,
    setInstances
  };
}
