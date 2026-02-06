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

        // Animation loop
        let animationFrameId: number;

        const render = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear

            const time = Date.now() / 1000;
            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const goldenAngle = 137.5 * (Math.PI / 180);
            const scale = Math.min(canvas.width, canvas.height) / 22; // Slightly smaller scale

            const agentList = agents.length > 0 ? agents : Array.from({ length: 48 }).map((_, i) => ({ id: `agent-${i}`, status: Math.random() > 0.8 ? 'active' : 'idle' }));

            // First pass: Calculate positions
            const tempPositions: AgentPosition[] = [];
            agentList.forEach((agent, i) => {
                const r = scale * Math.sqrt(i + 1);
                const theta = i * goldenAngle + (time * 0.05); // Slow rotation
                const x = centerX + r * Math.cos(theta);
                const y = centerY + r * Math.sin(theta);
                tempPositions.push({ id: (agent as any).id, x, y, r: 6 });
            });
            positionsRef.current = tempPositions;

            // Second pass: Draw Connections (Neural web)
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(99, 102, 241, 0.08)'; // Indigo trace
            ctx.lineWidth = 0.5;

            // connect to nearest neighbors (simple distance check for visual effect)
            // In real sunflower, neighbors are i+1, i-1, i+8, i-8 roughly
            for (let i = 0; i < tempPositions.length; i++) {
                const p1 = tempPositions[i];
                // Connect to center just a bit
                if (i < 5) {
                    ctx.moveTo(centerX, centerY);
                    ctx.lineTo(p1.x, p1.y);
                }

                // Connect to nearby nodes
                for (let j = i + 1; j < tempPositions.length; j++) {
                    const p2 = tempPositions[j];
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < scale * 4.5) { // Threshold for connection
                        ctx.moveTo(p1.x, p1.y);
                        ctx.lineTo(p2.x, p2.y);
                    }
                }
            }
            ctx.stroke();

            // Third pass: Draw Nodes
            tempPositions.forEach((pos, i) => {
                const agent = agentList[i];
                const status = (agent as any).status || 'idle';

                // Glow
                const pulse = Math.sin(time * 2 + i) * 0.5 + 0.5; // Individual pulse phase

                if (status === 'active') {
                    // Core
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, 4, 0, 2 * Math.PI);
                    ctx.fillStyle = '#818CF8'; // Indigo-400
                    ctx.fill();

                    // Glow spread
                    const glowRadius = 8 + pulse * 6;
                    const gradient = ctx.createRadialGradient(pos.x, pos.y, 2, pos.x, pos.y, glowRadius);
                    gradient.addColorStop(0, 'rgba(129, 140, 248, 0.8)');
                    gradient.addColorStop(1, 'rgba(129, 140, 248, 0)');
                    ctx.fillStyle = gradient;
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, glowRadius, 0, 2 * Math.PI);
                    ctx.fill();

                } else if (status === 'error') {
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, 4, 0, 2 * Math.PI);
                    ctx.fillStyle = '#EF4444';
                    ctx.fill();
                } else {
                    // Idle nodes (Starlight dots)
                    ctx.beginPath();
                    ctx.arc(pos.x, pos.y, 2, 0, 2 * Math.PI);
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
                    ctx.fill();
                }
            });

            animationFrameId = requestAnimationFrame(render);
        };

        render();

        return () => cancelAnimationFrame(animationFrameId);
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
