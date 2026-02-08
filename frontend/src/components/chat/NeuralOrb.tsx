import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../../utils/cn';

interface NeuralOrbProps {
    active: boolean;
    mode: 'daena' | 'autopilot';
}

/**
 * Radial Energy Orb Component
 * Blue/Cyan theme for "Command" mode
 * Golden/Amber theme for "Auto" mode
 * Creates a pulsing, data-particle effect like a neural core
 */
export function NeuralOrb({ active, mode }: NeuralOrbProps) {
    const isAutopilot = mode === 'autopilot';

    // Color schemes
    const colors = {
        command: {
            primary: 'from-cyan-400 via-blue-500 to-indigo-600',
            glow: 'bg-cyan-500',
            border: 'border-cyan-500/30',
            text: 'text-cyan-400',
            ring: 'from-cyan-500/20 via-blue-500/10 to-transparent',
            particle: 'bg-cyan-400',
            core: 'bg-gradient-to-br from-white via-cyan-200 to-blue-400',
        },
        auto: {
            primary: 'from-amber-400 via-orange-500 to-red-500',
            glow: 'bg-amber-500',
            border: 'border-amber-500/30',
            text: 'text-amber-400',
            ring: 'from-amber-500/20 via-orange-500/10 to-transparent',
            particle: 'bg-amber-400',
            core: 'bg-gradient-to-br from-white via-amber-200 to-orange-400',
        }
    };

    const theme = isAutopilot ? colors.auto : colors.command;

    // Generate particle positions
    const particles = Array.from({ length: 60 }, (_, i) => ({
        id: i,
        angle: (i / 60) * Math.PI * 2,
        radius: 80 + Math.random() * 60,
        size: 1 + Math.random() * 2,
        duration: 3 + Math.random() * 4,
        delay: Math.random() * 2,
    }));

    // Generate orbit rings
    const rings = [
        { radius: 120, duration: 20, opacity: 0.3, dots: 24 },
        { radius: 160, duration: 30, opacity: 0.2, dots: 32 },
        { radius: 200, duration: 40, opacity: 0.1, dots: 40 },
    ];

    return (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none overflow-hidden z-0">
            <AnimatePresence>
                {!active && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 1.2, filter: "blur(20px)" }}
                        transition={{ duration: 0.8, ease: "easeOut" }}
                        className="flex flex-col items-center justify-center relative"
                    >
                        {/* Deep Background Glow */}
                        <div className={cn(
                            "absolute w-[600px] h-[600px] rounded-full blur-[120px] opacity-30",
                            theme.glow
                        )} />

                        {/* Data Particle Field */}
                        <div className="absolute w-[500px] h-[500px]">
                            {particles.map((p) => (
                                <motion.div
                                    key={p.id}
                                    className={cn("absolute w-1 h-1 rounded-full", theme.particle)}
                                    style={{
                                        left: '50%',
                                        top: '50%',
                                        width: p.size,
                                        height: p.size,
                                    }}
                                    initial={{
                                        x: Math.cos(p.angle) * p.radius,
                                        y: Math.sin(p.angle) * p.radius,
                                        opacity: 0,
                                    }}
                                    animate={{
                                        x: [
                                            Math.cos(p.angle) * p.radius,
                                            Math.cos(p.angle + Math.PI) * (p.radius * 0.8),
                                            Math.cos(p.angle) * p.radius,
                                        ],
                                        y: [
                                            Math.sin(p.angle) * p.radius,
                                            Math.sin(p.angle + Math.PI) * (p.radius * 0.8),
                                            Math.sin(p.angle) * p.radius,
                                        ],
                                        opacity: [0.2, 0.8, 0.2],
                                        scale: [0.8, 1.2, 0.8],
                                    }}
                                    transition={{
                                        duration: p.duration,
                                        delay: p.delay,
                                        repeat: Infinity,
                                        ease: "easeInOut",
                                    }}
                                />
                            ))}
                        </div>

                        {/* Orbital Rings with Dotted Pattern */}
                        {rings.map((ring, idx) => (
                            <motion.div
                                key={idx}
                                className="absolute"
                                style={{ width: ring.radius * 2, height: ring.radius * 2 }}
                                animate={{ rotate: idx % 2 === 0 ? 360 : -360 }}
                                transition={{ duration: ring.duration, repeat: Infinity, ease: "linear" }}
                            >
                                {Array.from({ length: ring.dots }).map((_, i) => {
                                    const angle = (i / ring.dots) * Math.PI * 2;
                                    const x = Math.cos(angle) * ring.radius + ring.radius;
                                    const y = Math.sin(angle) * ring.radius + ring.radius;
                                    return (
                                        <div
                                            key={i}
                                            className={cn("absolute w-1 h-1 rounded-full", theme.particle)}
                                            style={{
                                                left: x,
                                                top: y,
                                                opacity: ring.opacity,
                                                transform: 'translate(-50%, -50%)',
                                            }}
                                        />
                                    );
                                })}
                            </motion.div>
                        ))}

                        {/* Inner Rotating Ring */}
                        <motion.div
                            animate={{ rotate: -360 }}
                            transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
                            className={cn(
                                "absolute w-48 h-48 rounded-full border-2 border-dashed",
                                theme.border
                            )}
                        />

                        {/* Core Ring Glow */}
                        <motion.div
                            animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.5, 0.3] }}
                            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                            className={cn(
                                "absolute w-40 h-40 rounded-full",
                                `bg-gradient-radial ${theme.ring}`
                            )}
                            style={{
                                background: `radial-gradient(circle, ${isAutopilot ? 'rgba(251,191,36,0.4)' : 'rgba(34,211,238,0.4)'} 0%, transparent 70%)`,
                            }}
                        />

                        {/* Radial Light Beams */}
                        <div className="absolute w-60 h-60">
                            {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
                                <motion.div
                                    key={angle}
                                    className={cn(
                                        "absolute h-0.5 origin-left",
                                        isAutopilot ? "bg-gradient-to-r from-amber-400/60 to-transparent" : "bg-gradient-to-r from-cyan-400/60 to-transparent"
                                    )}
                                    style={{
                                        width: '100px',
                                        left: '50%',
                                        top: '50%',
                                        transform: `rotate(${angle}deg)`,
                                    }}
                                    animate={{ opacity: [0.3, 0.7, 0.3], scaleX: [0.8, 1, 0.8] }}
                                    transition={{ duration: 2, delay: angle / 360, repeat: Infinity, ease: "easeInOut" }}
                                />
                            ))}
                        </div>

                        {/* Core Sphere */}
                        <motion.div
                            animate={{ scale: [1, 1.05, 1] }}
                            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                            className={cn(
                                "relative w-28 h-28 rounded-full shadow-2xl flex items-center justify-center overflow-hidden",
                                theme.border,
                                "border-2"
                            )}
                            style={{
                                background: `radial-gradient(circle at 30% 30%, ${isAutopilot ? 'rgba(255,255,255,0.9), rgba(251,191,36,0.8), rgba(249,115,22,0.6)' : 'rgba(255,255,255,0.9), rgba(34,211,238,0.8), rgba(59,130,246,0.6)'})`,
                                boxShadow: isAutopilot
                                    ? '0 0 60px rgba(251,191,36,0.5), 0 0 120px rgba(249,115,22,0.3), inset 0 0 40px rgba(255,255,255,0.5)'
                                    : '0 0 60px rgba(34,211,238,0.5), 0 0 120px rgba(59,130,246,0.3), inset 0 0 40px rgba(255,255,255,0.5)',
                            }}
                        >
                            {/* Inner Core Light */}
                            <motion.div
                                animate={{ opacity: [0.6, 1, 0.6] }}
                                transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                                className="absolute w-8 h-8 rounded-full bg-white blur-sm"
                            />
                            <div className="absolute w-4 h-4 rounded-full bg-white shadow-[0_0_20px_10px_rgba(255,255,255,0.8)]" />
                        </motion.div>

                        {/* Horizontal Light Streak */}
                        <motion.div
                            animate={{ opacity: [0.3, 0.6, 0.3], scaleX: [0.9, 1.1, 0.9] }}
                            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                            className={cn(
                                "absolute h-[2px] w-[400px]",
                                isAutopilot
                                    ? "bg-gradient-to-r from-transparent via-amber-400/80 to-transparent"
                                    : "bg-gradient-to-r from-transparent via-cyan-400/80 to-transparent"
                            )}
                        />

                        {/* Mode Label */}
                        <div className="mt-16 text-center space-y-3 z-10">
                            <motion.h1
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.3 }}
                                className={cn(
                                    "text-3xl font-display font-bold tracking-[0.2em] uppercase",
                                    isAutopilot ? "text-amber-100" : "text-cyan-100"
                                )}
                                style={{
                                    textShadow: isAutopilot
                                        ? '0 0 30px rgba(251,191,36,0.5)'
                                        : '0 0 30px rgba(34,211,238,0.5)',
                                }}
                            >
                                {isAutopilot ? 'NEURAL AUTO' : 'NEURAL COMMAND'}
                            </motion.h1>
                            <motion.p
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 0.7 }}
                                transition={{ delay: 0.5 }}
                                className={cn(
                                    "text-[10px] font-mono uppercase tracking-[0.5em]",
                                    theme.text
                                )}
                            >
                                {isAutopilot ? 'Autonomous Execution Active' : 'Founder-Directed Interface'}
                            </motion.p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Ambient Background when chat is active */}
            <motion.div
                animate={{ opacity: active ? 0.08 : 0 }}
                transition={{ duration: 1 }}
                className={cn(
                    "absolute w-[800px] h-[800px] rounded-full blur-[200px]",
                    theme.glow
                )}
            />
        </div>
    );
}

/**
 * Mini Orb for status bar
 */
export function MiniNeuralOrb({ mode }: { mode: 'daena' | 'autopilot' }) {
    const isAutopilot = mode === 'autopilot';

    return (
        <div className="relative w-6 h-6 flex items-center justify-center">
            {/* Outer Glow */}
            <motion.div
                animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.5, 0.3] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                className={cn(
                    "absolute inset-0 rounded-full blur-sm",
                    isAutopilot ? "bg-amber-500" : "bg-cyan-500"
                )}
            />

            {/* Rotating Ring */}
            <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                className={cn(
                    "absolute inset-0 rounded-full border border-dashed scale-125",
                    isAutopilot ? "border-amber-500/40" : "border-cyan-500/40"
                )}
            />

            {/* Core */}
            <div
                className={cn(
                    "w-3 h-3 rounded-full shadow-lg",
                    isAutopilot
                        ? "bg-gradient-to-br from-white via-amber-300 to-orange-400"
                        : "bg-gradient-to-br from-white via-cyan-300 to-blue-400"
                )}
                style={{
                    boxShadow: isAutopilot
                        ? '0 0 12px rgba(251,191,36,0.8)'
                        : '0 0 12px rgba(34,211,238,0.8)',
                }}
            />

            {/* Dot particles */}
            {[0, 90, 180, 270].map((angle) => (
                <motion.div
                    key={angle}
                    className={cn(
                        "absolute w-0.5 h-0.5 rounded-full",
                        isAutopilot ? "bg-amber-400" : "bg-cyan-400"
                    )}
                    style={{
                        left: '50%',
                        top: '50%',
                    }}
                    animate={{
                        x: [
                            Math.cos((angle * Math.PI) / 180) * 10,
                            Math.cos(((angle + 90) * Math.PI) / 180) * 10,
                            Math.cos((angle * Math.PI) / 180) * 10,
                        ],
                        y: [
                            Math.sin((angle * Math.PI) / 180) * 10,
                            Math.sin(((angle + 90) * Math.PI) / 180) * 10,
                            Math.sin((angle * Math.PI) / 180) * 10,
                        ],
                        opacity: [0.3, 0.8, 0.3],
                    }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                />
            ))}
        </div>
    );
}
