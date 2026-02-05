import { useState, useEffect } from 'react';
import { FileTree, type FileNode } from './FileTree';
import { CodeEditor } from './CodeEditor';
import { TerminalEmulator } from './TerminalEmulator';
import { fileSystemApi } from '../../services/api/fileSystem';
import { useUIStore } from '../../store/uiStore';
import {
    Terminal as TerminalIcon,
    Code,
    X,
    Minimize2,
    Save,
    Play,
    History as DiffIcon,
    RefreshCw
} from 'lucide-react';
import { Button } from '../common/Button';
import { cn } from '../../utils/cn';
import { DiffViewer } from './DiffViewer';

export function IDEContainer() {
    const [files, setFiles] = useState<FileNode[]>([]);
    const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);
    const [terminalVisible, setTerminalVisible] = useState(true);
    const [diffMode, setDiffMode] = useState(false);
    const [editorValue, setEditorValue] = useState('');
    const [originalValue, setOriginalValue] = useState('');
    const [loading, setLoading] = useState(false);
    const { addNotification } = useUIStore();

    // Command execution state to pass to terminal
    const [pendingCommand, setPendingCommand] = useState<string | null>(null);

    useEffect(() => {
        loadFileSystem();
    }, []);

    const loadFileSystem = async () => {
        try {
            setLoading(true);
            const structure = await fileSystemApi.getStructure();
            const rootNode = transformStructure(structure.directories, structure.root_path);
            setFiles(rootNode);
        } catch (error) {
            console.error("Failed to load file system", error);
            addNotification({ title: 'Error', message: 'Failed to load file system', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    // Transform backend directory structure to FileNode[]
    const transformStructure = (dirs: any, rootPath: string): FileNode[] => {
        const nodes: FileNode[] = [];

        // Process directories
        Object.keys(dirs).forEach(dirName => {
            const dirData = dirs[dirName];
            if (dirData.type === 'directory') {
                nodes.push({
                    id: `${rootPath}/${dirName}`,
                    path: dirName, // Relative path from root
                    name: dirName,
                    type: 'directory',
                    children: transformStructure(dirData.subdirs || {}, `${rootPath}/${dirName}`)
                });
            } else {
                nodes.push({
                    id: `${rootPath}/${dirName}`,
                    path: dirName,
                    name: dirName,
                    type: 'file',
                    extension: dirName.split('.').pop()
                });
            }
        });

        // Backend structure flattens files into the directory map with type='file' if they are at that level
        // But the provided backend logic separates files into current dir? 
        // Actually the backend logic was: current[parts[-1]] = {'type': 'file'} 
        // So files are siblings of subdirs in the same dictionary.

        return nodes.sort((a, b) => {
            if (a.type === b.type) return a.name.localeCompare(b.name);
            return a.type === 'directory' ? -1 : 1;
        });
    };

    const handleFileSelect = async (node: FileNode) => {
        if (node.type === 'file') {
            try {
                // The 'id' we constructed is absolute path.
                const fileContent = await fileSystemApi.readFile(node.id);

                setSelectedFile(node);
                setEditorValue(fileContent);
                setOriginalValue(fileContent);
                setDiffMode(false);
            } catch (error) {
                addNotification({ title: 'Error', message: 'Failed to read file', type: 'error' });
            }
        }
    };

    const handleSave = async () => {
        if (!selectedFile) return;
        try {
            await fileSystemApi.writeFile(selectedFile.id, editorValue);
            setOriginalValue(editorValue);
            addNotification({ title: 'Success', message: 'File saved', type: 'success' });
        } catch (error) {
            addNotification({ title: 'Error', message: 'Failed to save file', type: 'error' });
        }
    };

    const handleRun = () => {
        if (!selectedFile) return;
        // Simple heuristic to run files based on extension
        let cmd = '';
        if (selectedFile.name.endsWith('.py')) {
            cmd = `python ${selectedFile.id}`;
        } else if (selectedFile.name.endsWith('.ts') || selectedFile.name.endsWith('.js')) {
            cmd = `npm run start -- ${selectedFile.id}`; // Or node
        } else {
            addNotification({ title: 'Info', message: 'Cannot run this file type directly', type: 'info' });
            return;
        }

        // Pass command to terminal (this needs TerminalEmulator to expose method or use prop)
        // For now, let's use a specialized method if we can, or just notify user.
        addNotification({ title: 'Running', message: `Executing: ${cmd}`, type: 'info' });
        // In a real implementation, we'd pipe this to the terminal component
        setPendingCommand(cmd);
    };

    return (
        <div className="flex h-[calc(100vh-120px)] bg-midnight-950 rounded-3xl border border-white/5 overflow-hidden shadow-2xl relative">
            {/* Sidebar: File Tree */}
            <div className="w-64 border-r border-white/5 bg-midnight-950 flex flex-col">
                <div className="h-12 border-b border-white/5 flex items-center justify-between px-4">
                    <span className="text-xs font-bold text-starlight-300 uppercase tracking-widest">Explorer</span>
                    <button onClick={loadFileSystem} className="text-starlight-400 hover:text-white p-1 rounded">
                        <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                    <FileTree
                        data={files}
                        onSelect={handleFileSelect}
                        selectedId={selectedFile?.id}
                    />
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Editor Header / Tabs */}
                <div className="h-12 border-b border-white/5 bg-midnight-900/50 flex items-center justify-between px-4">
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 px-3 py-1.5 bg-midnight-200/50 rounded-lg border border-white/5">
                            <Code className="w-3.5 h-3.5 text-primary-400" />
                            <span className="text-xs text-white font-medium">{selectedFile?.name || 'No file selected'}</span>
                            {selectedFile && editorValue !== originalValue && (
                                <span className="w-1.5 h-1.5 rounded-full bg-status-warning ml-2" title="Unsaved changes" />
                            )}
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="icon"
                            className={cn("h-8 w-8 rounded-lg", diffMode && "bg-primary-500/20 text-primary-400")}
                            onClick={() => setDiffMode(!diffMode)}
                            title="Toggle Diff View"
                            disabled={!selectedFile}
                        >
                            <DiffIcon className="w-4 h-4" />
                        </Button>
                        <div className="h-4 w-px bg-white/10 mx-1" />
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 rounded-lg"
                            onClick={handleSave}
                            disabled={!selectedFile || editorValue === originalValue}
                        >
                            <Save className={cn("w-4 h-4", editorValue !== originalValue ? "text-primary-400" : "")} />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 rounded-lg text-status-success"
                            onClick={handleRun}
                            disabled={!selectedFile}
                        >
                            <Play className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                {/* Editor Pane */}
                <div className="flex-1 relative min-h-0">
                    {diffMode ? (
                        <DiffViewer
                            oldValue={originalValue}
                            newValue={editorValue}
                            fileName={selectedFile?.name}
                        />
                    ) : (
                        <CodeEditor
                            value={editorValue}
                            language={selectedFile?.extension === 'py' ? 'python' : 'typescript'}
                            onChange={(val) => setEditorValue(val || '')}
                            fileName={selectedFile?.name}
                        />
                    )}
                </div>

                {/* Terminal Pane */}
                {terminalVisible && (
                    <div className="h-48 border-t border-white/5 flex flex-col bg-midnight-950">
                        <div className="h-8 bg-midnight-900 px-4 flex items-center justify-between shrink-0">
                            <div className="flex items-center gap-2">
                                <TerminalIcon className="w-3.5 h-3.5 text-starlight-300" />
                                <span className="text-[10px] text-starlight-300 uppercase tracking-widest font-bold">Neural Terminal</span>
                            </div>
                            <div className="flex items-center gap-1">
                                <button onClick={() => setTerminalVisible(false)} className="p-1 hover:bg-white/5 rounded text-starlight-400">
                                    <Minimize2 className="w-3 h-3" />
                                </button>
                                <button className="p-1 hover:bg-white/5 rounded text-starlight-400">
                                    <X className="w-3 h-3" />
                                </button>
                            </div>
                        </div>
                        <div className="flex-1 min-h-0">
                            <TerminalEmulator initialCommand={pendingCommand} onCommandExecuted={() => setPendingCommand(null)} />
                        </div>
                    </div>
                )}
            </div>

            {/* Toggle Button */}
            {!terminalVisible && (
                <div className="absolute bottom-4 right-4 z-50">
                    <button
                        onClick={() => setTerminalVisible(true)}
                        className="bg-primary-600 hover:bg-primary-500 text-white p-3 rounded-full shadow-lg transition-all"
                    >
                        <TerminalIcon className="w-5 h-5" />
                    </button>
                </div>
            )}
        </div>
    );
}
