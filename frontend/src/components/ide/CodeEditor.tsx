import Editor, { loader } from '@monaco-editor/react';
import { Loader2 } from 'lucide-react';

interface CodeEditorProps {
    value: string;
    language?: string;
    onChange?: (value: string | undefined) => void;
    readOnly?: boolean;
    fileName?: string;
}

export function CodeEditor({ value, language = 'javascript', onChange, readOnly = false }: CodeEditorProps) {

    const handleEditorChange = (val: string | undefined) => {
        onChange?.(val);
    };

    return (
        <div className="h-full w-full bg-[#0D0D15] relative overflow-hidden">
            <Editor
                height="100%"
                defaultLanguage={language}
                language={language}
                value={value}
                theme="vs-dark"
                onChange={handleEditorChange}
                options={{
                    minimap: { enabled: true },
                    fontSize: 13,
                    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    readOnly,
                    lineNumbers: 'on',
                    glyphMargin: true,
                    folding: true,
                    lineDecorationsWidth: 10,
                    lineNumbersMinChars: 3,
                    padding: { top: 20 },
                    cursorBlinking: 'smooth',
                    smoothScrolling: true,
                    contextmenu: true,
                    renderLineHighlight: 'all',
                }}
                loading={
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-midnight-900 gap-4">
                        <Loader2 className="w-8 h-8 animate-spin text-primary-400" />
                        <p className="text-[10px] text-starlight-300 uppercase tracking-widest animate-pulse">Initializing Neural Editor...</p>
                    </div>
                }
            />
        </div>
    );
}

// Pre-define custom theme if needed
loader.config({
    paths: {
        vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.43.0/min/vs'
    }
});
