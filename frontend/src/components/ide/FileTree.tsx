import { useState } from 'react';
import {
    File,
    Folder,
    ChevronRight,
    ChevronDown,
    FileCode,
    FileText,
    FileJson,
    FolderPlus,
    FilePlus,
    Search
} from 'lucide-react';
import { cn } from '../../utils/cn';

export interface FileNode {
    id: string;
    path: string; // Relative path
    name: string;
    type: 'file' | 'directory';
    children?: FileNode[];
    extension?: string;
    content?: string;
    size?: number;
    modified?: number;
}

interface FileTreeProps {
    data: FileNode[];
    onSelect: (node: FileNode) => void;
    selectedId?: string;
}

export function FileTree({ data, onSelect, selectedId }: FileTreeProps) {
    const [searchTerm, setSearchTerm] = useState('');

    return (
        <div className="flex flex-col h-full bg-midnight-900 border-r border-white/5 w-64 shrink-0 overflow-hidden">
            <div className="p-4 border-b border-white/5 space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-[10px] text-starlight-300 uppercase tracking-widest font-bold">Workspace</h3>
                    <div className="flex gap-2">
                        <button className="p-1 hover:bg-white/5 rounded text-starlight-400 hover:text-white transition-colors">
                            <FilePlus className="w-3.5 h-3.5" />
                        </button>
                        <button className="p-1 hover:bg-white/5 rounded text-starlight-400 hover:text-white transition-colors">
                            <FolderPlus className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>
                <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-starlight-400" />
                    <input
                        type="text"
                        placeholder="Search files..."
                        className="w-full bg-midnight-200/50 border border-white/5 rounded-lg pl-8 pr-3 py-1.5 text-xs text-starlight-100 focus:outline-none focus:ring-1 focus:ring-primary-500/50"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 scrollbar-hide">
                {data.map((node) => (
                    <TreeNode key={node.id} node={node} onSelect={onSelect} selectedId={selectedId} level={0} />
                ))}
            </div>
        </div>
    );
}

function TreeNode({ node, onSelect, selectedId, level }: { node: FileNode, onSelect: (node: FileNode) => void, selectedId?: string, level: number }) {
    const [isOpen, setIsOpen] = useState(level === 0);
    const isSelected = selectedId === node.id;
    const isDirectory = node.type === 'directory';

    const getIcon = () => {
        if (isDirectory) return isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />;

        const ext = node.name.split('.').pop()?.toLowerCase();
        switch (ext) {
            case 'ts':
            case 'tsx':
            case 'js':
            case 'jsx': return <FileCode className="w-4 h-4 text-primary-400" />;
            case 'json': return <FileJson className="w-4 h-4 text-accent" />;
            case 'md': return <FileText className="w-4 h-4 text-status-info" />;
            default: return <File className="w-4 h-4 text-starlight-400" />;
        }
    };

    const handleClick = () => {
        if (isDirectory) {
            setIsOpen(!isOpen);
        } else {
            onSelect(node);
        }
    };

    return (
        <div className="select-none">
            <div
                className={cn(
                    "flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-all group",
                    isSelected ? "bg-primary-500/10 text-white shadow-glow-sm" : "text-starlight-300 hover:bg-white/5 hover:text-white"
                )}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
                onClick={handleClick}
            >
                {isDirectory && (
                    <span className="shrink-0 opacity-40 group-hover:opacity-100">{isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}</span>
                )}
                {!isDirectory && <span className="w-3.5 h-3.5" />}

                {isDirectory ? <Folder className="w-4 h-4 text-accent/60" /> : getIcon()}
                <span className="text-xs truncate font-medium">{node.name}</span>
            </div>

            {isDirectory && isOpen && node.children && (
                <div className="mt-0.5">
                    {node.children.map((child) => (
                        <TreeNode key={child.id} node={child} onSelect={onSelect} selectedId={selectedId} level={level + 1} />
                    ))}
                </div>
            )}
        </div>
    );
}
