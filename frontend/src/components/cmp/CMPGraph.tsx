import {
    ReactFlow,
    Background,
    Controls,
    Panel,
    BackgroundVariant
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCMPStore } from '../../store/cmpStore';
import {
    Play,
    Save,
    Plus,
    Trash2,
    Settings2,
    Zap,
    Brain,
    Shield,
    Database,
    LayoutGrid
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';

export function CMPGraph() {
    const {
        nodes,
        edges,
        onNodesChange,
        onEdgesChange,
        onConnect,
        addWorkflowNode
    } = useCMPStore();

    return (
        <div className="h-[calc(100vh-120px)] w-full bg-midnight-950 rounded-3xl border border-white/5 overflow-hidden shadow-2xl relative">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                colorMode="dark"
                fitView
            >
                <Background
                    variant={BackgroundVariant.Dots}
                    gap={20}
                    size={1}
                    color="rgba(255,255,255,0.05)"
                />
                <Controls className="!bg-midnight-900 !border-white/5 !fill-white" />

                <Panel position="top-left" className="flex flex-col gap-2">
                    <div className="glass-panel p-4 rounded-2xl border-white/5 space-y-4 min-w-[200px]">
                        <h3 className="text-[10px] text-starlight-300 uppercase tracking-widest font-bold">Node Library</h3>
                        <div className="grid grid-cols-1 gap-2">
                            <NodeTemplateButton
                                icon={Zap}
                                label="Action"
                                color="text-primary-400"
                                onClick={() => addWorkflowNode('default', { label: 'Tool Dispatch' })}
                            />
                            <NodeTemplateButton
                                icon={Shield}
                                label="Condition"
                                color="text-status-warning"
                                onClick={() => addWorkflowNode('default', { label: 'Policy Check' })}
                            />
                            <NodeTemplateButton
                                icon={Brain}
                                label="Intelligence"
                                color="text-accent"
                                onClick={() => addWorkflowNode('default', { label: 'LLM Analysis' })}
                            />
                            <NodeTemplateButton
                                icon={Database}
                                label="Storage"
                                color="text-status-info"
                                onClick={() => addWorkflowNode('default', { label: 'NBMF Write' })}
                            />
                        </div>
                    </div>
                </Panel>

                <Panel position="top-right">
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" className="rounded-xl bg-midnight-900/50 backdrop-blur-md">
                            <Save className="w-4 h-4 mr-2" /> Save Workflow
                        </Button>
                        <Button variant="primary" size="sm" className="rounded-xl shadow-glow-success border-status-success/20">
                            <Play className="w-4 h-4 mr-2" /> Deploy CMP
                        </Button>
                    </div>
                </Panel>

                <Panel position="bottom-center" className="mb-4">
                    <div className="glass-card px-6 py-3 rounded-full border-white/10 flex items-center gap-6 shadow-2xl">
                        <div className="flex items-center gap-2">
                            <span className="text-[10px] text-starlight-300 uppercase tracking-tighter">Status:</span>
                            <Badge className="bg-status-success/10 text-status-success border-none text-[9px]">DRAFT_V12</Badge>
                        </div>
                        <div className="w-px h-4 bg-white/10" />
                        <button className="text-starlight-300 hover:text-white transition-colors">
                            <Settings2 className="w-4 h-4" />
                        </button>
                        <button className="text-starlight-300 hover:text-white transition-colors">
                            <LayoutGrid className="w-4 h-4" />
                        </button>
                        <button className="text-status-error/60 hover:text-status-error transition-colors">
                            <Trash2 className="w-4 h-4" />
                        </button>
                    </div>
                </Panel>
            </ReactFlow>

            {/* Ambient Background Glows */}
            <div className="absolute top-0 left-0 w-1/3 h-1/3 bg-primary-500/5 blur-[120px] pointer-events-none" />
            <div className="absolute bottom-0 right-0 w-1/3 h-1/3 bg-accent/5 blur-[120px] pointer-events-none" />
        </div>
    );
}

function NodeTemplateButton({ icon: Icon, label, color, onClick }: any) {
    return (
        <button
            onClick={onClick}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white/5 border border-white/5 hover:border-white/20 hover:bg-white/10 transition-all text-left group"
        >
            <div className={cn("p-1.5 rounded-lg bg-midnight-400 group-hover:scale-110 transition-transform", color)}>
                <Icon className="w-3.5 h-3.5" />
            </div>
            <span className="text-xs text-starlight-100 font-medium">{label}</span>
            <Plus className="w-3 h-3 ml-auto opacity-20 group-hover:opacity-100" />
        </button>
    );
}

function cn(...classes: any[]) {
    return classes.filter(Boolean).join(' ');
}
