import { useSkillsStore } from '../../store/skillsStore';
import type { ToolExecution } from '../../store/skillsStore';
import {
    CheckCircle2,
    XCircle,
    Loader2,
    ChevronDown,
    ChevronUp,
    Clock,
    Cpu
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '../../utils/cn';
import { motion, AnimatePresence } from 'framer-motion';

export function ToolTimeline() {
    const { activeExecutions, executionHistory } = useSkillsStore();
    const allExecutions = [...activeExecutions, ...executionHistory.slice(0, 5)];

    if (allExecutions.length === 0) return null;

    return (
        <div className="space-y-3 p-4 bg-midnight-900/50 rounded-2xl border border-white/5 mx-4 my-2">
            <h3 className="text-[10px] text-starlight-300 uppercase tracking-[0.2em] font-bold flex items-center gap-2 px-1">
                <Cpu className="w-3 h-3 text-primary-400" /> Neural Operations
            </h3>
            <div className="space-y-2">
                {allExecutions.map((exec) => (
                    <ToolItem key={exec.id} exec={exec} />
                ))}
            </div>
        </div>
    );
}

function ToolItem({ exec }: { exec: ToolExecution }) {
    const [expanded, setExpanded] = useState(false);

    const statusIcons = {
        running: <Loader2 className="w-4 h-4 text-primary-400 animate-spin" />,
        completed: <CheckCircle2 className="w-4 h-4 text-status-success" />,
        failed: <XCircle className="w-4 h-4 text-status-error" />,
        pending: <Clock className="w-4 h-4 text-starlight-300" />
    };

    return (
        <div className={cn(
            "group rounded-xl border transition-all duration-300 overflow-hidden",
            exec.status === 'running'
                ? "bg-primary-500/5 border-primary-500/20"
                : "bg-white/5 border-transparent hover:border-white/10"
        )}>
            <div
                className="p-3 flex items-center justify-between cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-3">
                    <div className="shrink-0">{statusIcons[exec.status]}</div>
                    <div>
                        <p className="text-xs font-medium text-white">{exec.toolName}</p>
                        <p className="text-[10px] text-starlight-400 font-mono opacity-60">
                            {exec.id} • {new Date(exec.startTime).toLocaleTimeString()}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {exec.status === 'running' && (
                        <div className="w-20 h-1 bg-midnight-200 rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-primary-500"
                                initial={{ width: 0 }}
                                animate={{ width: `${exec.progress}%` }}
                            />
                        </div>
                    )}
                    {expanded ? <ChevronUp className="w-3 h-3 opacity-40" /> : <ChevronDown className="w-3 h-3 opacity-40" />}
                </div>
            </div>

            <AnimatePresence>
                {expanded && (
                    <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: 'auto' }}
                        exit={{ height: 0 }}
                        className="overflow-hidden bg-black/20"
                    >
                        <div className="p-3 pt-0 space-y-2">
                            <div className="p-2 bg-midnight-900/80 rounded-lg border border-white/5 font-mono text-[10px] text-starlight-300 max-h-32 overflow-y-auto scrollbar-hide">
                                {exec.logs.map((log, i) => (
                                    <div key={i} className="flex gap-2">
                                        <span className="opacity-30">[{i}]</span>
                                        <span>{log}</span>
                                    </div>
                                ))}
                                {exec.error && (
                                    <div className="text-status-error mt-2 border-t border-status-error/20 pt-2">
                                        ERROR: {exec.error}
                                    </div>
                                )}
                                {exec.result && (
                                    <div className="text-status-success mt-2 border-t border-status-success/20 pt-2">
                                        RESULT: {JSON.stringify(exec.result, null, 2)}
                                    </div>
                                )}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
