/**
 * ProjectsPage -- Persistent project workspaces. Lists all projects,
 * allows CRUD, and each project scopes tasks/files/chat/departments.
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus,
  FolderOpen,
  Clock,
  FileText,
  ListTodo,
  Settings,
  Trash2,
  Pencil,
  Loader2,
  ChevronRight,
  FolderKanban,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, EmptyState, Shimmer, Input } from '@/components/common'
import { api } from '@/lib/api'
import type { ProjectResponse } from '@/types/api'

// ── Helpers ──

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

// ── Create/Edit Dialog ──

interface ProjectDialogProps {
  open: boolean
  onClose: () => void
  onSave: (name: string, description: string) => void
  initialName?: string
  initialDescription?: string
  title: string
  saving?: boolean
}

function ProjectDialog({
  open,
  onClose,
  onSave,
  initialName = '',
  initialDescription = '',
  title,
  saving,
}: ProjectDialogProps) {
  const [name, setName] = useState(initialName)
  const [description, setDescription] = useState(initialDescription)

  useEffect(() => {
    setName(initialName)
    setDescription(initialDescription)
  }, [initialName, initialDescription, open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="w-full max-w-md"
      >
        <Card variant="elevated" padding="lg" className="space-y-4">
          <h2 className="text-lg font-display font-bold text-starlight-100">{title}</h2>

          <div className="space-y-3">
            <div>
              <label className="text-xs text-starlight-400 mb-1 block">Project Name</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Daena V2 Sprint"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs text-starlight-400 mb-1 block">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What is this project about?"
                rows={3}
                className="w-full glass-input text-sm text-starlight-200 placeholder:text-starlight-400/50 resize-none"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button
              onClick={() => onSave(name.trim(), description.trim())}
              disabled={!name.trim() || saving}
            >
              {saving ? <Loader2 size={14} className="animate-spin mr-1.5" /> : null}
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </Card>
      </motion.div>
    </div>
  )
}

// ── ProjectCard ──

interface ProjectCardProps {
  project: ProjectResponse
  onEdit: () => void
  onDelete: () => void
  onClick: () => void
}

function ProjectCard({ project, onEdit, onDelete, onClick }: ProjectCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      layout
    >
      <Card
        variant="glass"
        padding="md"
        className="group cursor-pointer hover:border-white/10 transition-all"
        onClick={onClick}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <FolderOpen size={16} className="text-primary-400 shrink-0" />
              <h3 className="text-sm font-medium text-starlight-100 truncate">
                {project.name}
              </h3>
            </div>
            {project.description && (
              <p className="text-xs text-starlight-400 line-clamp-2 ml-6">
                {project.description}
              </p>
            )}
          </div>

          {/* Actions (show on hover) */}
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={(e) => { e.stopPropagation(); onEdit() }}
              className="p-1.5 rounded-md hover:bg-white/5 text-starlight-400 hover:text-starlight-200 transition-colors"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              className="p-1.5 rounded-md hover:bg-status-error/10 text-starlight-400 hover:text-status-error transition-colors"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="flex items-center gap-4 mt-3 ml-6">
          <span className="flex items-center gap-1 text-[10px] text-starlight-400">
            <ListTodo size={10} />
            {project.task_count} task{project.task_count !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-starlight-400">
            <FileText size={10} />
            {project.file_count} file{project.file_count !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1 text-[10px] text-starlight-400">
            <Clock size={10} />
            {timeAgo(project.updated_at)}
          </span>
        </div>
      </Card>
    </motion.div>
  )
}

// ── Main page ──

export function ProjectsPage() {
  usePageTitle('Projects')
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<ProjectResponse | null>(null)
  const [saving, setSaving] = useState(false)

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/projects')
      setProjects(data.projects ?? [])
    } catch {
      setProjects([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchProjects() }, [fetchProjects])

  const handleCreate = async (name: string, description: string) => {
    setSaving(true)
    try {
      await api.post('/projects', { name, description })
      setCreateOpen(false)
      fetchProjects()
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async (name: string, description: string) => {
    if (!editTarget) return
    setSaving(true)
    try {
      await api.put(`/projects/${editTarget.id}`, { name, description })
      setEditTarget(null)
      fetchProjects()
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (projectId: string) => {
    try {
      await api.delete(`/projects/${projectId}`)
      fetchProjects()
    } catch {
      // toast error handled by interceptor
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-3">
              <FolderKanban size={24} className="text-primary-400" />
              Projects
            </h1>
            <p className="text-sm text-starlight-400 mt-1">
              Persistent workspaces for organizing tasks, files, and chat context
            </p>
          </div>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} className="mr-1.5" />
            New Project
          </Button>
        </motion.div>

        {/* Project grid */}
        {loading ? (
          <Shimmer count={4} layout="list" />
        ) : projects.length === 0 ? (
          <EmptyState
            icon={<FolderOpen size={40} className="text-starlight-400" />}
            title="No projects yet"
            description="Create your first project to organize work into focused workspaces"
            action={
              <Button onClick={() => setCreateOpen(true)}>
                <Plus size={16} className="mr-1.5" />
                Create Project
              </Button>
            }
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <AnimatePresence mode="popLayout">
              {projects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onEdit={() => setEditTarget(project)}
                  onDelete={() => handleDelete(project.id)}
                  onClick={() => navigate(`/projects/${project.id}`)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}

        {/* Create dialog */}
        <AnimatePresence>
          {createOpen && (
            <ProjectDialog
              open={createOpen}
              onClose={() => setCreateOpen(false)}
              onSave={handleCreate}
              title="New Project"
              saving={saving}
            />
          )}
        </AnimatePresence>

        {/* Edit dialog */}
        <AnimatePresence>
          {editTarget && (
            <ProjectDialog
              open={!!editTarget}
              onClose={() => setEditTarget(null)}
              onSave={handleUpdate}
              title="Edit Project"
              initialName={editTarget.name}
              initialDescription={editTarget.description}
              saving={saving}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

export default ProjectsPage
