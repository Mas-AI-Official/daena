import { useEffect, useRef } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';
import { terminalApi } from '../../services/api/fileSystem';

interface TerminalEmulatorProps {
    onData?: (data: string) => void;
    initialCommand?: string | null;
    onCommandExecuted?: () => void;
}

export function TerminalEmulator({ onData, initialCommand, onCommandExecuted }: TerminalEmulatorProps) {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<Terminal | null>(null);
    const commandBuffer = useRef('');

    useEffect(() => {
        if (!terminalRef.current) return;

        const term = new Terminal({
            cursorBlink: true,
            fontSize: 12,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            theme: {
                background: '#0a0a0f',
                foreground: '#e2e8f0',
                cursor: '#6366f1', // primary-500
                selectionBackground: 'rgba(99, 102, 241, 0.3)', // primary-500/30
                black: '#1e293b',
                red: '#ef4444',
                green: '#22c55e',
                yellow: '#f59e0b',
                blue: '#6366f1', // primary-500
                magenta: '#a5b4fc', // primary-300
                cyan: '#06b6d4',
                white: '#f1f5f9',
            },
            allowTransparency: true,
            rows: 10,
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        term.loadAddon(new WebLinksAddon());

        term.open(terminalRef.current);
        fitAddon.fit();

        // Welcome message
        term.writeln('\x1b[1;34mDaena Neural Terminal v2.5.0\x1b[0m');
        term.writeln('Secure node session established at ' + new Date().toLocaleString());

        const prompt = () => {
            term.write('\r\n\x1b[32mdaena@founder\x1b[0m:\x1b[34m~\x1b[0m$ ');
        };

        prompt();

        term.onData(async (data) => {
            if (data === '\r') { // Enter
                const cmd = commandBuffer.current.trim();
                term.write('\r\n');

                if (cmd) {
                    if (cmd === 'clear') {
                        term.clear();
                        commandBuffer.current = '';
                        prompt();
                        return;
                    }

                    try {
                        const result = await terminalApi.execute(cmd);
                        if (result.stdout) term.write(result.stdout.replace(/\n/g, '\r\n'));
                        if (result.stderr) term.write(`\x1b[31m${result.stderr.replace(/\n/g, '\r\n')}\x1b[0m`);
                    } catch (error) {
                        term.write(`\r\n\x1b[31mError executing command: ${error}\x1b[0m`);
                    }
                }

                commandBuffer.current = '';
                prompt();
            } else if (data === '\u007f') { // Backspace
                if (commandBuffer.current.length > 0) {
                    commandBuffer.current = commandBuffer.current.slice(0, -1);
                    term.write('\b \b');
                }
            } else {
                commandBuffer.current += data;
                term.write(data);
            }
            onData?.(data);
        });

        xtermRef.current = term;

        const handleResize = () => fitAddon.fit();
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            term.dispose();
        };
    }, []); // Run once on mount

    // Handle initialCommand specific effect
    useEffect(() => {
        if (initialCommand && xtermRef.current) {
            const term = xtermRef.current;
            // Write command to terminal
            term.write(initialCommand);
            // Simulate Enter
            term.onData('\r' as any); // This triggers the onData handler? No, onData is an event listener.
            // We need to trigger the logic manually or simulate input. 
            // Better: just execute it directly.

            const executeInitial = async () => {
                term.write('\r\n');
                try {
                    const result = await terminalApi.execute(initialCommand);
                    if (result.stdout) term.write(result.stdout.replace(/\n/g, '\r\n'));
                    if (result.stderr) term.write(`\x1b[31m${result.stderr.replace(/\n/g, '\r\n')}\x1b[0m`);
                } catch (error) {
                    term.write(`\r\n\x1b[31mError executing command: ${error}\x1b[0m`);
                }
                term.write('\r\n\x1b[32mdaena@founder\x1b[0m:\x1b[34m~\x1b[0m$ ');
                onCommandExecuted?.();
            };

            executeInitial();
        }
    }, [initialCommand, onCommandExecuted]);

    return (
        <div className="h-full w-full bg-[#0a0a0f] p-2">
            <div ref={terminalRef} className="h-full w-full" />
        </div>
    );
}
