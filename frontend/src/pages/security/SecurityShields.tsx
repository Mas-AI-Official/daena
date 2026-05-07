/**
 * SecurityShields -- the Shields tab.
 *
 * Per-department SHIELD activation panel. Pure presentational: the
 * shields payload comes from the parent's /security/shields fetch.
 * Active = department's SHIELD sub-capability is in elevated
 * authorized defensive review mode.
 */
import { Shield, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Card, EmptyState } from '@/components/common'
import { type ShieldDetails } from './types'

interface Props {
  shields: ShieldDetails | null
}

export default function SecurityShields({ shields }: Props) {
  if (!shields) {
    return (
      <EmptyState
        icon={<Shield className="text-starlight-500" size={40} />}
        title="SHIELD data unavailable"
        description="SHIELD data not available"
      />
    )
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-1">
          <Shield className="text-accent-amber" size={18} />
          <span className="text-sm font-medium text-starlight-200">
            Department SHIELD Status
          </span>
        </div>
        <p className="text-xs text-starlight-500 mb-4">
          When elevated security mode activates, every department's SHIELD
          sub-capability receives authorized defensive review context. This
          keeps security analysis scoped to approved targets and evidence.
        </p>

        <div className="space-y-2">
          {Object.entries(shields.departments).map(([dept, info]) => (
            <div
              key={dept}
              className={`
                p-3 rounded-lg border flex items-start gap-3
                ${info.active
                  ? 'bg-accent-amber/5 border-accent-amber/20'
                  : 'bg-starlight-800/30 border-starlight-700'}
              `}
            >
              <div className={`p-1.5 rounded ${info.active ? 'bg-accent-amber/10' : 'bg-starlight-800'}`}>
                {info.active ? (
                  <ShieldAlert size={16} className="text-accent-amber" />
                ) : (
                  <ShieldCheck size={16} className="text-starlight-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-starlight-200">{dept}</span>
                  <span className={`
                    px-1.5 py-0.5 text-[10px] rounded font-medium
                    ${info.active
                      ? 'bg-accent-amber/15 text-accent-amber'
                      : 'bg-starlight-800 text-starlight-500'}
                  `}>
                    {info.active ? 'ELEVATED' : info.mode.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-starlight-500 mt-1 line-clamp-2">
                  {info.role_summary}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Summary bar */}
      <div className="flex items-center gap-4 text-sm text-starlight-400">
        <div className="flex items-center gap-1.5">
          <ShieldAlert size={14} className="text-accent-amber" />
          <span>{shields.total_offensive} elevated</span>
        </div>
        <div className="flex items-center gap-1.5">
          <ShieldCheck size={14} className="text-starlight-500" />
          <span>{shields.total_departments - shields.total_offensive} defensive</span>
        </div>
      </div>
    </div>
  )
}
