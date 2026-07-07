import { lazy } from 'react'
import { Activity, FolderKanban, Kanban, ListTodo } from 'lucide-react'
import { TabbedSurface, type SurfaceTab } from '@/components/layout/TabbedSurface'

// Work surface (FM-3, 2026-07-02): Tasks / Workstreams / Projects / Pipeline
// were four separate Execution nav entries + routes. They are all "units of
// work" lenses on the same operation, so they fold into ONE tabbed Work
// surface. Each tab keeps its real route (/tasks, /workstreams, /projects,
// /pipeline) so every deep-link + query param (?status, ?focus) still lands on
// the right tab with the child page's own state intact -- no redirect drops
// them (Rule 17). The existing tested pages render UNCHANGED inside the tab
// region (reuse, not rewrite). /projects/:projectId stays a separate route
// (the detail view), so it is not a tab here.
const TasksPage = lazy(() => import('@/pages/TasksPage'))
const WorkstreamsPage = lazy(() => import('@/pages/WorkstreamsPage'))
const ProjectsPage = lazy(() => import('@/pages/ProjectsPage'))
const PipelinePage = lazy(() => import('@/pages/PipelinePage'))

const WORK_TABS: SurfaceTab[] = [
  { label: 'Tasks', path: '/tasks', icon: <ListTodo size={15} />, Component: TasksPage },
  { label: 'Workstreams', path: '/workstreams', icon: <Activity size={15} />, Component: WorkstreamsPage },
  { label: 'Projects', path: '/projects', icon: <FolderKanban size={15} />, Component: ProjectsPage },
  { label: 'Pipeline', path: '/pipeline', icon: <Kanban size={15} />, Component: PipelinePage },
]

/** Lazy-loaded, so this must default-export. */
export default function WorkPage() {
  return <TabbedSurface tabs={WORK_TABS} ariaLabel="Work views" />
}
