import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface Model {
  id: string;
  name: string;
  size_gb: number;
  provider: string;
  enabled: boolean;
  status: string;
}

interface BrainState {
  models: Model[];
  isScanning: boolean;
  scanning: boolean;
  loading: boolean;
  error: string | null;
}

const initialState: BrainState = {
  models: [],
  isScanning: false,
  scanning: false,
  loading: false,
  error: null,
};

const brainSlice = createSlice({
  name: 'brain',
  initialState,
  reducers: {
    modelsScanned: (state, action: PayloadAction<Model[]>) => {
      // Merge with existing to preserve 'enabled' status
      const newModels = action.payload.map(newModel => {
        const existing = state.models.find(m => m.id === newModel.id);
        return {
          ...newModel,
          enabled: existing ? existing.enabled : newModel.enabled,
        };
      });
      state.models = newModels;
    },
    updateModelStatus: (state, action: PayloadAction<{ modelId: string; enabled: boolean }>) => {
      const { modelId, enabled } = action.payload;
      const model = state.models.find(m => m.id === modelId);
      if (model) {
        model.enabled = enabled;
      }
    },
    setScanning: (state, action: PayloadAction<boolean>) => {
      state.isScanning = action.payload;
      state.scanning = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
    addModel: (state, action: PayloadAction<Model>) => {
      state.models.push(action.payload);
    },
    removeModel: (state, action: PayloadAction<string>) => {
      state.models = state.models.filter(m => m.id !== action.payload);
    },
  },
});

export const {
  modelsScanned,
  updateModelStatus,
  setScanning,
  setLoading,
  setError,
  addModel,
  removeModel,
} = brainSlice.actions;

export default brainSlice.reducer;
