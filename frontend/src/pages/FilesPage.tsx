/**
 * FilesPage -- Full file management with drag-drop upload, sortable table,
 * search, and file type icons.
 */
import { useEffect, useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText,
  Upload,
  Search,
  FolderOpen,
  Trash2,
  Download,
  MoreVertical,
  Image,
  FileCode,
  FileSpreadsheet,
  File,
  FileArchive,
  Music,
  Video,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Loader2,
  CheckCircle2,
  X,
  XCircle,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { api } from '@/lib/api'
import { deleteWithToast, batchDeleteWithToast } from '@/lib/mutations'
import { toast } from '@/stores/toastStore'

// ── Types ──

interface FileRecord {
  id: string
  filename: string
  original_filename: string
  content_type: string | null
  size_bytes: number
  sha256: string
  purpose: string
  created_at: string
}

type SortKey = 'created_at' | 'original_filename' | 'size_bytes'
type SortDir = 'asc' | 'desc'

// ── Helpers ──

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(i > 0 ? 1 : 0)} ${sizes[i]}`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  if (diff < 604800_000) return `${Math.floor(diff / 86400_000)}d ago`
  return d.toLocaleDateString()
}

function fileIcon(contentType: string | null) {
  if (!contentType) return <File size={18} className="text-starlight-400" />
  if (contentType.startsWith('image/')) return <Image size={18} className="text-accent-purple" />
  if (contentType.startsWith('video/')) return <Video size={18} className="text-accent-cyan" />
  if (contentType.startsWith('audio/')) return <Music size={18} className="text-accent-amber" />
  if (contentType === 'application/pdf') return <FileText size={18} className="text-accent-red" />
  if (contentType.includes('zip') || contentType.includes('tar') || contentType.includes('gzip')) return <FileArchive size={18} className="text-starlight-400" />
  if (contentType.includes('spreadsheet') || contentType.includes('csv') || contentType.includes('excel')) return <FileSpreadsheet size={18} className="text-accent-green" />
  if (contentType.includes('json') || contentType.includes('javascript') || contentType.includes('typescript') || contentType.includes('python') || contentType.includes('xml') || contentType.includes('yaml') || contentType.includes('html') || contentType.includes('css')) return <FileCode size={18} className="text-primary-400" />
  if (contentType.startsWith('text/')) return <FileText size={18} className="text-starlight-300" />
  return <File size={18} className="text-starlight-400" />
}

function fileExtension(filename: string): string {
  const dot = filename.lastIndexOf('.')
  return dot >= 0 ? filename.slice(dot + 1).toUpperCase() : ''
}

// ── File Row ──

function FileRow({ file, selected, onSelect, onDelete }: {
  file: FileRecord
  selected: boolean
  onSelect: (id: string, checked: boolean) => void
  onDelete: (id: string) => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.02] transition-colors group">
      <input
        type="checkbox"
        checked={selected}
        onChange={(e) => onSelect(file.id, e.target.checked)}
        className="w-3.5 h-3.5 rounded border-white/20 bg-transparent accent-primary-500 cursor-pointer shrink-0"
      />
      <div className="w-9 h-9 rounded-lg bg-midnight-400/60 flex items-center justify-center shrink-0">
        {fileIcon(file.content_type)}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-starlight-100 truncate">{file.original_filename}</p>
        <p className="text-[10px] text-starlight-500">
          {fileExtension(file.original_filename)} {file.content_type ? `-- ${file.content_type.split('/').pop()}` : ''}
        </p>
      </div>
      <span className="text-xs text-starlight-400 w-16 text-right shrink-0">{formatBytes(file.size_bytes)}</span>
      <span className="text-xs text-starlight-500 w-20 text-right shrink-0">{formatDate(file.created_at)}</span>
      <span className="text-[10px] text-starlight-500 w-16 text-right shrink-0 capitalize">{file.purpose}</span>
      <div className="relative shrink-0">
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="File actions menu"
          title="File actions"
          className="p-1 rounded hover:bg-white/5 text-starlight-500 opacity-60 group-hover:opacity-100 transition-opacity cursor-pointer"
        >
          <MoreVertical size={14} />
        </button>
        <AnimatePresence>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="absolute right-0 top-full mt-1 w-40 rounded-lg bg-midnight-200 border border-white/10 shadow-xl z-50 py-1"
              >
                <button
                  onClick={async () => {
                    setMenuOpen(false)
                    try {
                      const res = await api.get(`/files/${file.id}/download`, { responseType: 'blob' })
                      const url = URL.createObjectURL(res.data)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = file.original_filename
                      a.click()
                      URL.revokeObjectURL(url)
                    } catch {
                      toast.error('Failed to download file')
                    }
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-starlight-300 hover:bg-white/5 cursor-pointer"
                >
                  <Download size={12} /> Download
                </button>
                <button
                  onClick={() => { setMenuOpen(false); onDelete(file.id) }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs text-accent-red hover:bg-accent-red/10 cursor-pointer"
                >
                  <Trash2 size={12} /> Delete
                </button>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ── Main Page ──

export function FilesPage() {
  usePageTitle('Files')

  const [files, setFiles] = useState<FileRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set())
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchFiles = useCallback(async () => {
    try {
      const res = await api.get('/files', { params: { search: search || undefined, sort: sortKey, order: sortDir }, timeout: 5000 })
      const raw = res.data?.data || []
      // Map backend response (file_id, filename) to frontend shape (id, original_filename)
      setFiles(raw.map((f: Record<string, unknown>) => ({
        id: String(f.file_id ?? f.id ?? ''),
        filename: String(f.filename ?? ''),
        original_filename: String(f.filename ?? f.original_filename ?? ''),
        content_type: f.content_type as string | null,
        size_bytes: Number(f.size_bytes ?? 0),
        sha256: String(f.sha256 ?? ''),
        purpose: String(f.purpose ?? 'general'),
        created_at: String(f.created_at ?? new Date().toISOString()),
      })))
    } catch {
      // Graceful -- backend might not have list endpoint yet
      setFiles([])
    } finally {
      setLoading(false)
    }
  }, [search, sortKey, sortDir])

  useEffect(() => {
    void fetchFiles()
  }, [fetchFiles])

  const handleUpload = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return
    setUploading(true)
    let successCount = 0
    for (const file of Array.from(fileList)) {
      try {
        const formData = new FormData()
        formData.append('file', file)
        await api.post('/files/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        successCount++
      } catch {
        toast.error(`Failed to upload ${file.name}`)
      }
    }
    if (successCount > 0) {
      toast.success(`${successCount} file${successCount > 1 ? 's' : ''} uploaded`)
      void fetchFiles()
    }
    setUploading(false)
  }

  const handleDelete = async (fileId: string) => {
    // Explicit copy: we DO delete from both disk and DB. Operator
    // previously assumed the file would silently come back ("like spam").
    const ok = await deleteWithToast(`/files/${fileId}`, {
      entity: 'File',
      confirmMessage: 'This permanently removes the file from both your storage and the database. The file will NOT be recoverable from the trash or by re-uploading the listing entry. Are you sure?',
    })
    if (ok) {
      setFiles((prev) => prev.filter((f) => f.id !== fileId))
      setSelectedFiles((prev) => { const n = new Set(prev); n.delete(fileId); return n })
    }
  }

  const handleBatchDelete = async () => {
    if (selectedFiles.size === 0) return
    // Snapshot IDs before the batch; the source-of-truth for "which
    // survived" is the set of IDs that actually succeeded, returned
    // in the result. We refetch afterwards for a consistent view.
    const targetIds = new Set(selectedFiles)
    const result = await batchDeleteWithToast(
      targetIds,
      (id) => `/files/${id}`,
      { entity: 'file' },
    )
    if (result.succeeded > 0) {
      setFiles((prev) => prev.filter((f) => !targetIds.has(f.id)))
      setSelectedFiles(new Set())
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    void handleUpload(e.dataTransfer.files)
  }

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return <ArrowUpDown size={10} className="text-starlight-600" />
    return sortDir === 'asc' ? <ArrowUp size={10} className="text-primary-400" /> : <ArrowDown size={10} className="text-primary-400" />
  }

  const filteredFiles = search
    ? files.filter((f) => f.original_filename.toLowerCase().includes(search.toLowerCase()))
    : files

  const totalSize = files.reduce((acc, f) => acc + f.size_bytes, 0)

  return (
    <div
      className="h-full flex flex-col overflow-hidden"
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/5 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-display font-semibold text-starlight-100">Files</h1>
            <p className="text-sm text-starlight-400 mt-0.5">
              {files.length > 0
                ? `${files.length} file${files.length !== 1 ? 's' : ''} -- ${formatBytes(totalSize)} total`
                : 'Upload and manage your workspace files'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-midnight-300/50 border border-white/10">
              <Search size={14} className="text-starlight-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search files..."
                className="bg-transparent text-sm text-starlight-100 focus:outline-none w-48"
              />
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => void handleUpload(e.target.files)}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-500 text-white text-xs font-medium hover:bg-primary-600 transition-colors cursor-pointer disabled:opacity-50"
            >
              {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
              Upload
            </button>
          </div>
        </div>
      </div>

      {/* Batch actions bar */}
      <AnimatePresence>
        {selectedFiles.size > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-b border-white/5"
          >
            <div className="flex items-center gap-3 px-6 py-2.5 bg-primary-500/5">
              <span className="text-xs text-primary-400 font-medium">{selectedFiles.size} selected</span>
              <div className="flex-1" />
              <button
                onClick={() => void handleBatchDelete()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-red/10 text-accent-red hover:bg-accent-red/20 cursor-pointer"
              >
                <Trash2 size={12} /> Delete selected
              </button>
              <button
                onClick={() => setSelectedFiles(new Set())}
                className="p-1 rounded hover:bg-white/5 text-starlight-500 cursor-pointer"
              >
                <X size={14} />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Drag overlay */}
        <AnimatePresence>
          {dragOver && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 z-30 bg-primary-500/10 border-2 border-dashed border-primary-500/40 rounded-xl flex items-center justify-center"
            >
              <div className="text-center">
                <Upload size={40} className="mx-auto text-primary-400 mb-2" />
                <p className="text-sm font-medium text-primary-400">Drop files to upload</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={24} className="animate-spin text-starlight-400" />
          </div>
        ) : files.length === 0 ? (
          /* Empty state with upload zone */
          <div className="p-6 max-w-2xl mx-auto">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-white/10 rounded-xl p-12 text-center hover:border-primary-500/30 transition-colors cursor-pointer"
            >
              <Upload size={32} className="mx-auto text-starlight-500 mb-3" />
              <p className="text-sm text-starlight-300">Drag and drop files here</p>
              <p className="text-xs text-starlight-500 mt-1">or click to browse</p>
              <p className="text-[10px] text-starlight-600 mt-3">PDF, images, code, documents, archives -- up to 20 MB</p>
            </div>
            <div className="text-center py-8">
              <FolderOpen size={40} className="mx-auto text-starlight-600 mb-3" />
              <p className="text-sm text-starlight-400">No files yet</p>
              <p className="text-xs text-starlight-500 mt-1">Upload files to use them in chat and with your agents</p>
            </div>
          </div>
        ) : (
          /* File table */
          <div className="px-6 py-4">
            {/* Upload zone (compact when files exist) */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-white/10 rounded-xl p-6 text-center hover:border-primary-500/30 transition-colors cursor-pointer mb-4"
            >
              <Upload size={20} className="mx-auto text-starlight-500 mb-1" />
              <p className="text-xs text-starlight-400">Drop files here or click to upload</p>
            </div>

            {/* Table header */}
            <div className="flex items-center gap-3 px-4 py-2 text-[10px] text-starlight-500 uppercase tracking-wider font-semibold border-b border-white/5">
              <input
                type="checkbox"
                checked={selectedFiles.size === filteredFiles.length && filteredFiles.length > 0}
                onChange={() => {
                  if (selectedFiles.size === filteredFiles.length) setSelectedFiles(new Set())
                  else setSelectedFiles(new Set(filteredFiles.map((f) => f.id)))
                }}
                className="w-3.5 h-3.5 rounded border-white/20 bg-transparent accent-primary-500 cursor-pointer shrink-0"
              />
              <div className="w-9 shrink-0" /> {/* icon spacer */}
              <button onClick={() => toggleSort('original_filename')} className="flex-1 flex items-center gap-1 cursor-pointer hover:text-starlight-300">
                Name <SortIcon k="original_filename" />
              </button>
              <button onClick={() => toggleSort('size_bytes')} className="w-16 text-right flex items-center justify-end gap-1 cursor-pointer hover:text-starlight-300">
                Size <SortIcon k="size_bytes" />
              </button>
              <button onClick={() => toggleSort('created_at')} className="w-20 text-right flex items-center justify-end gap-1 cursor-pointer hover:text-starlight-300">
                Date <SortIcon k="created_at" />
              </button>
              <span className="w-16 text-right shrink-0">Type</span>
              <span className="w-6 shrink-0" /> {/* menu spacer */}
            </div>

            {/* File rows */}
            <div className="divide-y divide-white/5">
              {filteredFiles.length === 0 ? (
                <div className="px-4 py-8 text-center text-xs text-starlight-500">No files match your search</div>
              ) : (
                filteredFiles.map((file) => (
                  <FileRow
                    key={file.id}
                    file={file}
                    selected={selectedFiles.has(file.id)}
                    onSelect={(id, checked) => {
                      setSelectedFiles((prev) => {
                        const next = new Set(prev)
                        if (checked) next.add(id)
                        else next.delete(id)
                        return next
                      })
                    }}
                    onDelete={handleDelete}
                  />
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default FilesPage
