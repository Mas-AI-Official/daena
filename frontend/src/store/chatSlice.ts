import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  actions?: any[];
}

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  sessions: any[];
  currentSessionId: string | null;
}

const initialState: ChatState = {
  messages: [],
  isStreaming: false,
  sessions: [],
  currentSessionId: null,
};

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    messageSent: (state, action: PayloadAction<string>) => {
      state.messages.push({
        id: Date.now().toString(),
        role: 'user',
        content: action.payload,
        timestamp: new Date().toISOString(),
      });
      state.isStreaming = true;
    },
    addChunk: (state, action: PayloadAction<string>) => {
      // Append chunk to the last assistant message or create new one
      const lastMessage = state.messages[state.messages.length - 1];
      if (lastMessage && lastMessage.role === 'assistant') {
        lastMessage.content += action.payload;
      } else {
        state.messages.push({
          id: Date.now().toString(),
          role: 'assistant',
          content: action.payload,
          timestamp: new Date().toISOString(),
        });
      }
    },
    actionsDetected: (state, action: PayloadAction<any[]>) => {
      // Update the last message with detected actions
      const lastMessage = state.messages[state.messages.length - 1];
      if (lastMessage) {
        lastMessage.actions = action.payload;
      }
    },
    actionsCompleted: (state, action: PayloadAction<any[]>) => {
      // Actions completed, update message
      const lastMessage = state.messages[state.messages.length - 1];
      if (lastMessage) {
        lastMessage.actions = action.payload;
      }
      state.isStreaming = false;
    },
    setStreaming: (state, action: PayloadAction<boolean>) => {
      state.isStreaming = action.payload;
    },
    setSessions: (state, action: PayloadAction<any[]>) => {
      state.sessions = action.payload;
    },
    loadSession: (state, action: PayloadAction<string>) => {
      state.currentSessionId = action.payload;
    },
    clearChat: (state) => {
      state.messages = [];
      state.currentSessionId = null;
    },
  },
});

export const {
  messageSent,
  addChunk,
  actionsDetected,
  actionsCompleted,
  setStreaming,
  setSessions,
  loadSession,
  clearChat,
} = chatSlice.actions;

export default chatSlice.reducer;
