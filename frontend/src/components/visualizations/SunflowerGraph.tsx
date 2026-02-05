import React, { useEffect, useRef, useState } from 'react';
import { awarenessApi, type AwarenessGraph, type AwarenessNode } from '../../services/api/awareness';

interface SunflowerGraphProps {
    className?: string;
}

export const SunflowerGraph: React.FC<SunflowerGraphProps> = ({ className = '' }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [graphData, setGraphData] = useState<AwarenessGraph | null>(null);
    const [selectedNode, setSelectedNode] = useState<AwarenessNode | null>(null);
    const [loading, setLoading] = useState(true);
    const [hoveredNode, setHoveredNode] = useState<AwarenessNode | null>(null);
    const animationFrameRef = useRef<number | null>(null);

    // Theme colors matching globals.css
    const COLORS = {
        bg: '#020408', // midnight-900
        nodeDefault: '#6366f1', // primary-500
        nodeHover: '#8b5cf6', // accent
        nodeSelected: '#10b981', // status-success
        edge: 'rgba(99, 102, 241, 0.2)', // primary-500 with opacity
        text: '#f8f9fa' // starlight-100
    };

    useEffect(() => {
        fetchGraphData();
        return () => {
            if (animationFrameRef.current) {
                cancelAnimationFrame(animationFrameRef.current);
            }
        };
    }, []);

    useEffect(() => {
        if (graphData && canvasRef.current) {
            drawGraph();
        }
    }, [graphData, hoveredNode, selectedNode]);

    const fetchGraphData = async () => {
        try {
            setLoading(true);
            const data = await awarenessApi.getGraph();
            setGraphData(data);
        } catch (error) {
            console.error("Failed to fetch awareness graph:", error);
        } finally {
            setLoading(false);
        }
    };

    const drawGraph = () => {
        const canvas = canvasRef.current;
        if (!canvas || !graphData) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Resize canvas to parent
        const parent = canvas.parentElement;
        if (parent) {
            canvas.width = parent.clientWidth;
            canvas.height = parent.clientHeight;
        }

        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        // Scale factor to fit graph
        const scale = Math.min(width, height) / 2.5;

        // Draw Edges
        graphData.edges.forEach(edge => {
            const source = graphData.nodes.find(n => n.id === edge.source);
            const target = graphData.nodes.find(n => n.id === edge.target);

            if (source && target) {
                ctx.beginPath();
                ctx.moveTo(centerX + source.coordinates.x * scale, centerY + source.coordinates.y * scale);
                ctx.lineTo(centerX + target.coordinates.x * scale, centerY + target.coordinates.y * scale);

                ctx.strokeStyle = COLORS.edge;
                ctx.lineWidth = edge.weight * 2; // Thicker lines for stronger connections
                ctx.stroke();
            }
        });

        // Draw Nodes
        graphData.nodes.forEach(node => {
            const x = centerX + node.coordinates.x * scale;
            const y = centerY + node.coordinates.y * scale;
            const isHovered = hoveredNode?.id === node.id;
            const isSelected = selectedNode?.id === node.id;

            // Node circle
            ctx.beginPath();
            const radius = isHovered ? 12 : 8;
            ctx.arc(x, y, radius, 0, Math.PI * 2);

            // Color logic
            if (isSelected) ctx.fillStyle = COLORS.nodeSelected;
            else if (isHovered) ctx.fillStyle = COLORS.nodeHover;
            else ctx.fillStyle = node.color || COLORS.nodeDefault;

            ctx.fill();

            // Glow effect for active nodes
            if (isHovered || isSelected) {
                ctx.shadowColor = ctx.fillStyle;
                ctx.shadowBlur = 15;
            } else {
                ctx.shadowBlur = 0;
            }

            // Node border
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();

            // Reset shadow
            ctx.shadowBlur = 0;

            // Draw Label on hover
            if (isHovered) {
                ctx.font = '12px Inter, sans-serif';
                ctx.fillStyle = COLORS.text;
                ctx.textAlign = 'center';
                ctx.fillText(node.name, x, y - 20);

                // Draw role below
                ctx.font = '10px Inter, sans-serif';
                ctx.fillStyle = 'rgba(248, 249, 250, 0.7)';
                ctx.fillText(node.role, x, y + 25);
            }
        });
    };

    const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!graphData || !canvasRef.current) return;

        const canvas = canvasRef.current;
        const rect = canvas.getBoundingClientRect();
        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const scale = Math.min(width, height) / 2.5;

        const cursorX = (e.clientX - rect.left) * (width / rect.width);
        const cursorY = (e.clientY - rect.top) * (height / rect.height);

        let found: AwarenessNode | null = null;

        // Find node under cursor
        for (const node of graphData.nodes) {
            const x = centerX + node.coordinates.x * scale;
            const y = centerY + node.coordinates.y * scale;
            const dist = Math.sqrt(Math.pow(x - cursorX, 2) + Math.pow(y - cursorY, 2));

            if (dist < 15) { // Hit radius
                found = node;
                break;
            }
        }

        setHoveredNode(found);

        // Change cursor
        canvas.style.cursor = found ? 'pointer' : 'default';
    };

    const handleClick = () => {
        if (hoveredNode) {
            setSelectedNode(hoveredNode);
            // Optionally open agent detail modal here
        } else {
            setSelectedNode(null);
        }
    };

    return (
        <div className={`relative flex flex-col h-full glass-card p-4 ${className}`}>
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-display font-medium text-starlight-100 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-primary-500 animate-pulse"></span>
                    Awareness Graph
                </h3>
                <div className="flex gap-2 text-xs text-starlight-400">
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-primary-500"></span> Active
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full bg-status-success"></span> Selected
                    </span>
                </div>
            </div>

            <div className="flex-1 relative min-h-[400px] w-full bg-midnight-900/50 rounded-xl overflow-hidden border border-white/5">
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center z-10 bg-midnight-900/80">
                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-500"></div>
                    </div>
                )}
                <canvas
                    ref={canvasRef}
                    className="w-full h-full"
                    onMouseMove={handleMouseMove}
                    onClick={handleClick}
                    onMouseLeave={() => setHoveredNode(null)}
                />
            </div>

            {selectedNode && (
                <div className="mt-4 p-4 glass-panel rounded-lg animate-fade-in-up">
                    <div className="flex justify-between items-start">
                        <div>
                            <h4 className="text-starlight-100 font-medium">{selectedNode.name}</h4>
                            <p className="text-primary-400 text-sm">{selectedNode.role}</p>
                        </div>
                        <span className="text-xs px-2 py-1 rounded-full bg-midnight-500 text-starlight-300">
                            {selectedNode.department_name}
                        </span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-4 text-xs">
                        <div className="bg-midnight-900/50 p-2 rounded">
                            <span className="block text-starlight-400 mb-1">Knowledge Context</span>
                            <span className="text-starlight-100 font-mono">{selectedNode.knowledge_count} items</span>
                        </div>
                        <div className="bg-midnight-900/50 p-2 rounded">
                            <span className="block text-starlight-400 mb-1">Awareness Score</span>
                            <span className="text-starlight-100 font-mono">{selectedNode.awareness_count}%</span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
