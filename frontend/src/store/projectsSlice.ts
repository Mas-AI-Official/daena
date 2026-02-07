import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface Comment {
  id: string;
  text: string;
  created_at: string;
  user_id?: string;
  pending?: boolean;
}

interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  progress: number;
  created_at: string;
  comments?: Comment[];
}

interface ProjectsState {
  items: Project[];
  byId: Record<string, Project>;
  loading: boolean;
  error: string | null;
  cacheInvalidated: boolean;
}

const initialState: ProjectsState = {
  items: [],
  byId: {},
  loading: false,
  error: null,
  cacheInvalidated: false,
};

const projectsSlice = createSlice({
  name: 'projects',
  initialState,
  reducers: {
    setProjects: (state, action: PayloadAction<Project[]>) => {
      state.items = action.payload;
      state.byId = action.payload.reduce((acc, project) => {
        acc[project.id] = project;
        return acc;
      }, {} as Record<string, Project>);
      state.cacheInvalidated = false;
    },
    addProject: (state, action: PayloadAction<Project>) => {
      state.items.unshift(action.payload);
      state.byId[action.payload.id] = action.payload;
    },
    updateProject: (state, action: PayloadAction<Project>) => {
      const index = state.items.findIndex(p => p.id === action.payload.id);
      if (index !== -1) {
        state.items[index] = action.payload;
      }
      state.byId[action.payload.id] = action.payload;
    },
    deleteProject: (state, action: PayloadAction<string>) => {
      state.items = state.items.filter(p => p.id !== action.payload);
      delete state.byId[action.payload];
    },
    addCommentOptimistic: (state, action: PayloadAction<{ projectId: string; comment: Comment }>) => {
      const { projectId, comment } = action.payload;
      const project = state.byId[projectId];
      if (project) {
        if (!project.comments) project.comments = [];
        project.comments.unshift(comment);
      }
    },
    addComment: (state, action: PayloadAction<{ projectId: string; comment: Comment }>) => {
      const { projectId, comment } = action.payload;
      const project = state.byId[projectId];
      if (project && project.comments) {
        // Replace pending comment with real one
        const index = project.comments.findIndex(c => c.pending);
        if (index !== -1) {
          project.comments[index] = { ...comment, pending: false };
        } else {
          project.comments.unshift(comment);
        }
      }
    },
    revertComment: (state, action: PayloadAction<{ projectId: string; tempId: string }>) => {
      const { projectId, tempId } = action.payload;
      const project = state.byId[projectId];
      if (project && project.comments) {
        project.comments = project.comments.filter(c => c.id !== tempId);
      }
    },
    invalidateCache: (state) => {
      state.cacheInvalidated = true;
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
  setProjects,
  addProject,
  updateProject,
  deleteProject,
  addCommentOptimistic,
  addComment,
  revertComment,
  invalidateCache,
  setLoading,
  setError,
} = projectsSlice.actions;

export default projectsSlice.reducer;
