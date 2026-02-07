import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface Skill {
  id: string;
  name: string;
  enabled: boolean;
  operators: string[];
  risk?: string;
  category?: string;
}

interface SkillsState {
  items: Skill[];
  loading: boolean;
  error: string | null;
  optimisticUpdates: Record<string, any>;
}

const initialState: SkillsState = {
  items: [],
  loading: false,
  error: null,
  optimisticUpdates: {},
};

const skillsSlice = createSlice({
  name: 'skills',
  initialState,
  reducers: {
    setSkills: (state, action: PayloadAction<Skill[]>) => {
      state.items = action.payload;
    },
    updateOperatorsOptimistic: (state, action: PayloadAction<{ skillId: string; operators: string[] }>) => {
      const { skillId, operators } = action.payload;
      state.optimisticUpdates[skillId] = { operators };
      const skill = state.items.find(s => s.id === skillId);
      if (skill) {
        skill.operators = operators;
      }
    },
    updateOperators: (state, action: PayloadAction<{ skillId: string; operators: string[] }>) => {
      const { skillId, operators } = action.payload;
      const skill = state.items.find(s => s.id === skillId);
      if (skill) {
        skill.operators = operators;
      }
      delete state.optimisticUpdates[skillId];
    },
    revertOptimisticUpdate: (state, action: PayloadAction<{ skillId: string }>) => {
      const { skillId } = action.payload;
      delete state.optimisticUpdates[skillId];
      // In real implementation, would need original values stored
    },
    toggleSkill: (state, action: PayloadAction<string>) => {
      const skill = state.items.find(s => s.id === action.payload);
      if (skill) {
        skill.enabled = !skill.enabled;
      }
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const {
  setSkills,
  updateOperatorsOptimistic,
  updateOperators,
  revertOptimisticUpdate,
  toggleSkill,
  setLoading,
  setError,
} = skillsSlice.actions;

export default skillsSlice.reducer;
