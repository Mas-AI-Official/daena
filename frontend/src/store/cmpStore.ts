import { create } from 'zustand';
import {
    type Edge,
    type Node,
    addEdge,
    type OnNodesChange,
    type OnEdgesChange,
    type OnConnect,
    applyNodeChanges,
    applyEdgeChanges
} from '@xyflow/react';

interface CMPState {
    nodes: Node[];
    edges: Edge[];
    onNodesChange: OnNodesChange;
    onEdgesChange: OnEdgesChange;
    onConnect: OnConnect;
    setNodes: (nodes: Node[]) => void;
    setEdges: (edges: Edge[]) => void;
    addWorkflowNode: (type: string, data?: any) => void;
}

export const useCMPStore = create<CMPState>((set, get) => ({
    nodes: [
        {
            id: 'trigger-1',
            type: 'input',
            data: { label: 'User Trigger' },
            position: { x: 250, y: 5 },
            className: 'bg-primary-500/10 border-primary-500/30 text-white rounded-xl p-4 shadow-glow-sm',
        },
    ],
    edges: [],
    onNodesChange: (changes) => {
        set({
            nodes: applyNodeChanges(changes, get().nodes) as Node[],
        });
    },
    onEdgesChange: (changes) => {
        set({
            edges: applyEdgeChanges(changes, get().edges),
        });
    },
    onConnect: (connection) => {
        set({
            edges: addEdge({ ...connection, animated: true, style: { stroke: '#0070F3' } }, get().edges),
        });
    },
    setNodes: (nodes) => set({ nodes }),
    setEdges: (edges) => set({ edges }),
    addWorkflowNode: (type, data = {}) => {
        const id = `${type}-${Date.now()}`;
        const newNode: Node = {
            id,
            type,
            data: { label: `${type.charAt(0).toUpperCase() + type.slice(1)} Node`, ...data },
            position: { x: Math.random() * 400, y: Math.random() * 400 },
            className: 'bg-midnight-200 border-white/5 text-starlight-100 rounded-xl p-4',
        };
        set({ nodes: [...get().nodes, newNode] });
    }
}));
