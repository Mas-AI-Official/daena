import React, { useState } from 'react';
import { Switch } from '@/components/common/Switch';
import { useUIStore } from '@/store/uiStore';

interface ModelToggleProps {
  modelId: string;
  name: string;
  enabled: boolean;
}

export const ModelToggle: React.FC<ModelToggleProps> = ({
  modelId,
  name,
  enabled
}) => {
  const [isEnabled, setIsEnabled] = useState(enabled);
  const [isLoading, setIsLoading] = useState(false);
  const addNotification = useUIStore((state) => state.addNotification);

  const handleToggle = async (checked: boolean) => {
    setIsLoading(true);

    // Optimistic update
    setIsEnabled(checked);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Authentication required');
      }

      const endpoint = checked ? 'enable' : 'disable';
      const response = await fetch(`/api/v1/brain/models/${modelId}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired. Please login again.');
        }
        if (response.status === 404) {
          throw new Error('Model not found');
        }
        throw new Error(`Failed to toggle: ${response.statusText}`);
      }

      addNotification({
        type: 'success',
        title: 'Model Updated',
        message: `${name} ${checked ? 'enabled' : 'disabled'}`,
        duration: 2000
      });
    } catch (err: any) {
      // Revert optimistic update
      setIsEnabled(!checked);

      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: err.message || 'Failed to toggle model',
        duration: 4000
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="model-toggle flex items-center justify-between p-3 border border-gray-700 rounded-lg bg-gray-800/50">
      <div>
        <div className="font-medium text-gray-200">{name}</div>
        <div className="text-sm text-gray-500">{modelId}</div>
      </div>
      <Switch
        checked={isEnabled}
        onCheckedChange={handleToggle}
        disabled={isLoading}
      />
    </div>
  );
};
