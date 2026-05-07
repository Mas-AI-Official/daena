/**
 * ProjectDetailPage: tabbed detail view for a single project.
 * Tabs: Overview | Tasks | Files | Settings
 * Overview shows project info, stats, and quick actions.
 * Tasks shows task IDs associated with the project.
 * Files shows tracked file paths.
 * Settings shows project-specific configuration.
 */
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  FolderOpen,
  ListTodo,
  FileText,
  Settings,
  MessageSquare,
  Pencil,
  Trash2,
  Plus,
  Loader2,
  Clock,
  LayoutGrid,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { deleteWithToast } from '@/lib/mutations'
import { toast } from '@/stores/toastStore'
import type { ProjectResponse } from '@/types/api'

// Tab definitions
const TABS = [
  { key: 'overview', label: 'Overview', icon: LayoutGrid },
  { key: 'tasks', label: 'Tasks', icon: ListTodo },
  { key: 'files', label: 'Files', icon: FileText },
  { key: 'settings', label: 'Settings', icon: Settings },
] as const

type TabKey = (typeof TABS)[number]['key']

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

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [taskIds, setTaskIds] = useState<string[]>([])
  const [filePaths, setFilePaths] = useState<string[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)
  const [filesLoading, setFilesLoading] = useState(false)

  usePageTitle(project?.name ? `${project.name} | Projects` : 'Project')

  const fetchProject = useCallback(async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const { data } = await api.get(`/projects/${projectId}`)
      setProject(data)
    } catch {
      toast.error('Failed to load project')
      navigate('/projects')
    } finally {
      setLoading(false)
    }
  }, [projectId, navigate])

  useEffect(() => {
    fetchProject()
  }, [fetchProject])

  // Fetch tasks when tab is active
  useEffect(() => {
    if (activeTab !== 'tasks' || !projectId) return
    setTasksLoading(true)
    api.get(`/projects/${projectId}/tasks`)
      .then(({ data }) => setTaskIds(data.task_ids ?? []))
      .catch(() => setTaskIds([]))
      .finally(() => setTasksLoading(false))
  }, [activeTab, projectId])

  // Fetch files when tab is active
  useEffect(() => {
    if (activeTab !== 'files' || !projectId) return
    setFilesLoading(true)
    api.get(`/projects/${projectId}/files`)
      .then(({ data }) => setFilePaths(data.file_paths ?? []))
      .catch(() => setFilePaths([]))
      .finally(() => setFilesLoading(false))
  }, [activeTab, projectId])

  const handleDelete = async () => {
    if (!projectId) return
    const ok = await deleteWithToast(`/projects/${projectId}`, { entity: 'Project' })
    if (ok) navigate('/projects')
  }

  if (loading) {
    return (
      <div className="h-full overflow-y-auto">
        <div className="max-w-5xl mx-auto p-6">
          <Shimmer count={4} layout="list" />
        </div>
      </div>
    )
  }

  if (!project) return null

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Breadcrumb + header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-3"
        >
          <Link
            to="/projects"
            className="inline-flex items-center gap-1.5 text-xs text-starlight-400 hover:text-starlight-200 transition-colors"
          >
            <ArrowLeft size={12} />
            Back to Projects
          </Link>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-primary-500/15">
                <FolderOpen size={22} className="text-primary-400" />
              </div>
              <div>
                <h1 className="text-2xl font-display font-bold text-starlight-100">
                  {project.name}
                </h1>
                {project.description && (
                  <p className="text-sm text-starlight-400 mt-0.5">{project.description}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate(`/chat?project=${projectId}`)}
              >
                <MessageSquare size={14} />
                Open Chat
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDelete}
                className="!text-status-error hover:!bg-status-error/10"
              >
                <Trash2 size={14} />
              </Button>
            </div>
          </div>
        </motion.div>

        {/* Stat bar */}
        <div className="flex items-center gap-6 text-xs text-starlight-400">
          <span className="flex items-center gap-1.5">
            <ListTodo size={12} />
            {project.task_count} task{project.task_count !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1.5">
            <FileText size={12} />
            {project.file_count} file{project.file_count !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock size={12} />
            Updated {timeAgo(project.updated_at)}
          </span>
        </div>

        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-white/5 pb-px">
          {TABS.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.key
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-all cursor-pointer ${
                  isActive
                    ? 'bg-primary-500/10 text-primary-400 border-b-2 border-primary-500'
                    : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/[0.03] border-b-2 border-transparent'
                }`}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Tab content */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15 }}
        >
          {activeTab === 'overview' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card variant="glass" padding="md">
                <h3 className="text-xs font-semibold text-starlight-400 uppercase tracking-wider mb-3">
                  Quick Actions
                </h3>
                <div className="space-y-2">
                  <button
                    onClick={() => navigate(`/chat?project=${projectId}`)}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-starlight-300 hover:text-starlight-100 hover:bg-white/5 transition-all cursor-pointer"
                  >
                    <MessageSquare size={14} className="text-primary-400" />
                    Start Chat in Project
                  </button>
                  <button
                    onClick={() => setActiveTab('tasks')}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-starlight-300 hover:text-starlight-100 hover:bg-white/5 transition-all cursor-pointer"
                  >
                    <ListTodo size={14} className="text-accent-cyan" />
                    View Tasks
                  </button>
                  <button
                    onClick={() => setActiveTab('files')}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-starlight-300 hover:text-starlight-100 hover:bg-white/5 transition-all cursor-pointer"
                  >
                    <FileText size={14} className="text-accent-purple" />
                    View Files
                  </button>
                </div>
              </Card>
              <Card variant="glass" padding="md">
                <h3 className="text-xs font-semibold text-starlight-400 uppercase tracking-wider mb-3">
                  Project Info
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-starlight-400">Created</span>
                    <span className="text-starlight-200">
                      {new Date(project.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-starlight-400">Last Updated</span>
                    <span className="text-starlight-200">{timeAgo(project.updated_at)}</span>
                  </div>
                  {project.working_directory && (
                    <div className="flex justify-between">
                      <span className="text-starlight-400">Directory</span>
                      <code className="text-xs text-accent-cyan font-mono truncate max-w-[200px]">
                        {project.working_directory}
                      </code>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          )}

          {activeTab === 'tasks' && (
            <div>
              {tasksLoading ? (
                <Shimmer count={3} layout="list" />
              ) : taskIds.length === 0 ? (
                <EmptyState
                  icon={ListTodo}
                  title="No tasks yet"
                  description="Tasks created in this project's chat sessions will appear here"
                />
              ) : (
                <div className="space-y-2">
                  {taskIds.map((taskId) => (
                    <Card key={taskId} variant="glass" padding="sm" className="flex items-center gap-3">
                      <ListTodo size={14} className="text-starlight-400" />
                      <code className="text-xs font-mono text-starlight-300 flex-1">{taskId}</code>
                      <Link
                        to={`/tasks#task-${taskId}`}
                        className="text-xs text-primary-400 hover:underline"
                      >
                        View
                      </Link>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'files' && (
            <div>
              {filesLoading ? (
                <Shimmer count={3} layout="list" />
              ) : filePaths.length === 0 ? (
                <EmptyState
                  icon={FileText}
                  title={project.working_directory ? 'No files tracked yet' : 'No working directory set'}
                  description={
                    project.working_directory
                      ? 'Files referenced in project tasks will be tracked here'
                      : 'Set a working directory in project settings to browse files'
                  }
                />
              ) : (
                <div className="space-y-2">
                  {filePaths.map((fp) => (
                    <Card key={fp} variant="glass" padding="sm" className="flex items-center gap-3">
                      <FileText size={14} className="text-starlight-400" />
                      <code className="text-xs font-mono text-starlight-300 flex-1 truncate">{fp}</code>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'settings' && (
            <Card variant="glass" padding="md" className="space-y-4">
              <h3 className="text-xs font-semibold text-starlight-400 uppercase tracking-wider">
                Project Settings
              </h3>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-starlight-400 mb-1 block">Working Directory</label>
                  <input
                    type="text"
                    defaultValue={project.working_directory ?? ''}
                    placeholder="/path/to/project"
                    className="w-full glass-input px-3 py-2 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:ring-1 focus:ring-primary-500/40 font-mono"
                    onBlur={(e) => {
                      const val = e.target.value.trim()
                      if (val !== (project.working_directory ?? '')) {
                        api.put(`/projects/${projectId}`, { working_directory: val || null })
                          .then(() => {
                            toast.success('Working directory updated')
                            fetchProject()
                          })
                          .catch(() => toast.error('Failed to update'))
                      }
                    }}
                  />
                </div>
                <p className="text-[10px] text-starlight-500">
                  Project-specific model preferences and governance overrides will be available in a future update.
                </p>
              </div>
            </Card>
          )}
        </motion.div>
      </div>
    </div>
  )
}

export default ProjectDetailPage
