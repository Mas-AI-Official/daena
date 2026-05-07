/**
 * SecurityMissions -- the Missions tab.
 *
 * Self-contained mission console: launches new red-team missions
 * against /missions/start, lists active missions, expands a chosen
 * mission's status + attack-paths detail, and triggers
 * /missions/{id}/execute to advance a mission step-by-step.
 *
 * Owns its own data fetch (independent from the parent page's
 * /security/* fetches) so the missions surface stays interactive
 * without coupling to the dashboard refresh button.
 */
import { useCallback, useEffect, useState } from 'react'
import { Crosshair } from 'lucide-react'
import { Card, Badge, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { alertDialog } from '@/stores/confirmStore'

interface MissionInfo {
  mission_id: string
  goal: string
  target: string
  status: string
  engagement_level: string
  paths_total?: number
  nodes_discovered?: number
}

const LEVEL_COLORS: Record<string, string> = {
  audit: 'text-accent-cyan',
  pentest: 'text-status-warning',
  red_team: 'text-status-error',
  adversary: 'text-accent-purple',
}

export default function SecurityMissions() {
  const [missions, setMissions] = useState<MissionInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [goal, setGoal] = useState('')
  const [target, setTarget] = useState('')
  const [level, setLevel] = useState('pentest')
  const [selectedMission, setSelectedMission] = useState<string | null>(null)
  const [missionDetail, setMissionDetail] = useState<Record<string, unknown> | null>(null)

  const loadMissions = useCallback(async () => {
    try {
      const res = await api.get('/missions/active')
      setMissions(res.data)
    } catch {
      // No active missions
    }
  }, [])

  useEffect(() => { loadMissions() }, [loadMissions])

  const loadMissionDetail = async (mid: string) => {
    try {
      const [statusRes, pathsRes] = await Promise.all([
        api.get(`/missions/${mid}/status`),
        api.get(`/missions/${mid}/paths`),
      ])
      setMissionDetail({
        status: statusRes.data,
        paths: pathsRes.data,
      })
    } catch {
      // Error loading detail
    }
  }

  const startMission = async () => {
    if (!goal || !target) return
    setLoading(true)
    try {
      const res = await api.post('/missions/start', {
        goal, target, engagement_level: level,
      })
      setGoal('')
      setTarget('')
      loadMissions()
      setSelectedMission(res.data.mission_id)
      loadMissionDetail(res.data.mission_id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start mission'
      await alertDialog({
        title: 'Mission failed to start',
        message: msg,
        confirmLabel: 'Dismiss',
        variant: 'danger',
      })
    } finally {
      setLoading(false)
    }
  }

  const executeStep = async (mid: string) => {
    try {
      await api.post(`/missions/${mid}/execute`)
      loadMissionDetail(mid)
    } catch {
      // Error executing
    }
  }

  return (
    <div className="space-y-6">
      {/* Start new mission */}
      <Card className="p-4">
        <h3 className="text-sm font-medium text-starlight-300 mb-3 flex items-center gap-2">
          <Crosshair size={16} className="text-accent-amber" />
          Start Mission
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            type="text"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            placeholder="Goal (e.g., Prove database access)"
            className="px-3 py-2 bg-starlight-900 border border-starlight-700 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-600 focus:border-accent-amber/50 focus:outline-none"
          />
          <input
            type="text"
            value={target}
            onChange={e => setTarget(e.target.value)}
            placeholder="Target (e.g., target.com)"
            className="px-3 py-2 bg-starlight-900 border border-starlight-700 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-600 focus:border-accent-amber/50 focus:outline-none"
          />
          <select
            value={level}
            onChange={e => setLevel(e.target.value)}
            className="px-3 py-2 bg-starlight-900 border border-starlight-700 rounded-lg text-sm text-starlight-200 focus:border-accent-amber/50 focus:outline-none"
          >
            <option value="audit">Audit</option>
            <option value="pentest">Pentest</option>
            <option value="red_team">Red Team</option>
            <option value="adversary">Adversary</option>
          </select>
          <button
            onClick={startMission}
            disabled={loading || !goal || !target}
            className="px-4 py-2 bg-accent-amber/20 text-accent-amber border border-accent-amber/30 rounded-lg text-sm font-medium hover:bg-accent-amber/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Planning...' : 'Launch Mission'}
          </button>
        </div>
      </Card>

      {/* Active missions */}
      {missions.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-starlight-400">Active Missions</h3>
          {missions.map(m => (
            <Card
              key={m.mission_id}
              className={`p-4 cursor-pointer transition-colors ${
                selectedMission === m.mission_id ? 'border-accent-amber/50' : 'hover:border-starlight-600'
              }`}
              onClick={() => { setSelectedMission(m.mission_id); loadMissionDetail(m.mission_id) }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-starlight-200 font-medium">{m.goal}</div>
                  <div className="text-xs text-starlight-500 mt-1">
                    Target: {m.target}
                    <span className={`ml-3 ${LEVEL_COLORS[m.engagement_level] || ''}`}>
                      {m.engagement_level?.toUpperCase()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={m.status === 'planned' ? 'warning' : m.status === 'executing' ? 'error' : 'success'}>
                    {m.status}
                  </Badge>
                  <button
                    onClick={e => { e.stopPropagation(); executeStep(m.mission_id) }}
                    className="px-3 py-1 bg-status-error/20 text-status-error border border-status-error/30 rounded text-xs hover:bg-status-error/30 transition-colors"
                  >
                    Execute Next
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Mission detail */}
      {selectedMission && missionDetail ? (
        <Card className="p-4">
          <h3 className="text-sm font-medium text-starlight-300 mb-3">
            Mission Detail: {selectedMission}
          </h3>
          {Boolean(missionDetail.status) && typeof missionDetail.status === 'object' && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              {['paths_total', 'paths_completed', 'paths_failed', 'nodes_discovered'].map(key => {
                // Narrow to number so React accepts the child. Unknown
                // values fall back to 0 so the tile still renders rather
                // than producing a TS2322 at build time.
                const raw = (missionDetail.status as Record<string, unknown>)[key]
                const value = typeof raw === 'number' ? raw : 0
                return (
                  <div key={key} className="bg-starlight-900 rounded-lg p-3">
                    <div className="text-xs text-starlight-500 capitalize">{key.replace(/_/g, ' ')}</div>
                    <div className="text-lg font-semibold text-starlight-200 mt-1">{value}</div>
                  </div>
                )
              })}
            </div>
          )}
          {/* Attack paths */}
          {Array.isArray(missionDetail.paths) && (missionDetail.paths as Array<Record<string, unknown>>).map((path, i) => (
            <div key={i} className="mb-3 bg-starlight-900 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-starlight-300 font-medium capitalize">
                  {(path.type as string) ?? 'unknown'} Path
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-starlight-500">
                    Feasibility: {((path.feasibility as number) * 100).toFixed(0)}%
                  </span>
                  <Badge variant={(path.status as string) === 'planned' ? 'warning' : 'success'}>
                    {path.status as string}
                  </Badge>
                </div>
              </div>
              {Array.isArray(path.step_details) && (path.step_details as Array<Record<string, string>>).map((step, j) => (
                <div key={j} className="flex items-center gap-2 py-1 text-xs">
                  <span className={
                    step.status === 'succeeded' ? 'text-status-success' :
                    step.status === 'failed' ? 'text-status-error' :
                    'text-starlight-500'
                  }>
                    {step.status === 'succeeded' ? '✓' : step.status === 'failed' ? '✗' : '○'}
                  </span>
                  <span className="text-starlight-400">{step.description}</span>
                  <span className="text-starlight-600 ml-auto">{step.module}</span>
                </div>
              ))}
            </div>
          ))}
        </Card>
      ) : null}

      {/* Empty state */}
      {missions.length === 0 && !loading && (
        <EmptyState
          icon={<Crosshair size={40} />}
          title="No Active Missions"
          description="Start a mission to begin autonomous red team operations. Daena will plan attack paths, map the target's proximity rings, and execute step by step."
        />
      )}
    </div>
  )
}

