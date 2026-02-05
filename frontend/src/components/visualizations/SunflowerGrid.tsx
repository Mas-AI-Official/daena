import { useRef, useEffect, useCallback } from 'react';
import { useAgentStore } from '../../store/agentStore';

interface AgentPosition {
    id: string;
    x: number;
    y: number;
    r: number;
}

export function SunflowerGrid() {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const { agents, setSelectedAgent } = useAgentStore();
    const positionsRef = useRef<AgentPosition[]>([]);

    const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Find clicked agent
        const clickedAgent = positionsRef.current.find(pos => {
            const dist = Math.sqrt((pos.x - x) ** 2 + (pos.y - y) ** 2);
            return dist < 12; // Radius of detection
        });

        if (clickedAgent) {
            setSelectedAgent(clickedAgent.id);
        }
    }, [setSelectedAgent]);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const resizeObserver = new ResizeObserver(() => {
            if (canvas.parentElement) {
                canvas.width = canvas.parentElement.clientWidth;
                canvas.height = canvas.parentElement.clientHeight;
                draw();
            }
        });
        resizeObserver.observe(canvas.parentElement!);

        function draw() {
            if (!canvas || !ctx) return;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const goldenAngle = 137.5 * (Math.PI / 180);
            const scale = Math.min(canvas.width, canvas.height) / 20;

            const newPositions: AgentPosition[] = [];

            const agentList = agents.length > 0 ? agents : Array.from({ length: 48 }).map((_, i) => ({ id: `agent-${i}`, status: 'idle' }));

            agentList.forEach((agent, i) => {
                const r = scale * Math.sqrt(i + 1);
                const theta = i * goldenAngle;

                const x = centerX + r * Math.cos(theta);
                const y = centerY + r * Math.sin(theta);

                newPositions.push({ id: (agent as any).id, x, y, r: 8 });

                // Draw link
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(x, y);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
                ctx.lineWidth = 0.5;
                ctx.stroke();

                // Draw Hub
                ctx.beginPath();
                ctx.arc(x, y, 7, 0, 2 * Math.PI);

                const status = (agent as any).status || 'idle';
                if (status === 'active') {
                    ctx.fillStyle = '#4F46E5';
                    ctx.shadowBlur = 15;
                    ctx.shadowColor = 'rgba(79, 70, 229, 0.4)';
                } else if (status === 'error') {
                    ctx.fillStyle = '#EF4444';
                    ctx.shadowBlur = 15;
                    ctx.shadowColor = 'rgba(239, 68, 68, 0.4)';
                } else {
                    ctx.fillStyle = '#0f172a'; // midnight-900
                    ctx.shadowBlur = 0;
                }

                ctx.fill();
                ctx.strokeStyle = 'rgba(255,255,255,0.1)';
                ctx.lineWidth = 1;
                ctx.stroke();

                // Secondary ring for active
                if (status === 'active') {
                    ctx.beginPath();
                    ctx.arc(x, y, 10, 0, 2 * Math.PI);
                    ctx.strokeStyle = 'rgba(79, 70, 229, 0.2)';
                    ctx.stroke();
                }

                ctx.shadowBlur = 0;
            });

            positionsRef.current = newPositions;
        }

        draw();
        return () => resizeObserver.disconnect();
    }, [agents]);

    return (
        <div className="w-full h-full min-h-[400px] relative group cursor-crosshair">
            <canvas
                ref={canvasRef}
                onClick={handleCanvasClick}
                className="absolute inset-0 w-full h-full animate-fade-in"
            />
            {/* Ambient Background Aura */}
            <div className="absolute inset-0 bg-gradient-radial from-primary-500/5 to-transparent pointer-events-none" />
        </div>
    );
}
