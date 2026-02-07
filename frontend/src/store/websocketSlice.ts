import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface WebSocketState {
  connected: boolean;
  lastPing: number | null;
  reconnectAttempts: number;
}

const initialState: WebSocketState = {
  connected: false,
  lastPing: null,
  reconnectAttempts: 0,
};

const websocketSlice = createSlice({
  name: 'websocket',
  initialState,
  reducers: {
    connected: (state) => {
      state.connected = true;
      state.reconnectAttempts = 0;
    },
    disconnected: (state) => {
      state.connected = false;
    },
    pingReceived: (state, action: PayloadAction<number>) => {
      state.lastPing = action.payload;
    },
    reconnectAttempted: (state) => {
      state.reconnectAttempts += 1;
    },
  },
});

export const { connected, disconnected, pingReceived, reconnectAttempted } = websocketSlice.actions;
export default websocketSlice.reducer;
