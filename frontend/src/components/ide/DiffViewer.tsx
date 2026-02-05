import { useRef, useEffect } from 'react';
import { html } from 'diff2html';
import type { Diff2HtmlConfig } from 'diff2html';
import 'diff2html/bundles/css/diff2html.min.css';
import { createPatch } from 'diff';
import { cn } from '../../utils/cn';

interface DiffViewerProps {
    oldValue: string;
    newValue: string;
    fileName?: string;
    className?: string;
}

export function DiffViewer({ oldValue, newValue, fileName = 'file.txt', className }: DiffViewerProps) {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        try {
            const patch = createPatch(fileName, oldValue, newValue);

            const diffHtml = html(patch, {
                drawFileList: false,
                matching: 'lines',
                outputFormat: 'side-by-side',
                renderNothingWhenEmpty: false,
            } as Diff2HtmlConfig);

            containerRef.current.innerHTML = diffHtml;
        } catch (error) {
            console.error('Failed to render diff:', error);
            containerRef.current.innerHTML = '<div class="p-4 text-status-error">Error rendering diff</div>';
        }
    }, [oldValue, newValue, fileName]);

    return (
        <div
            ref={containerRef}
            className={cn(
                "diff-viewer-container h-full overflow-auto bg-midnight-950",
                className
            )}
        />
    );
}
