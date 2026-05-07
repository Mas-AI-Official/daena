/**
 * SecurityScans -- the Scans tab.
 *
 * Recent-scan list with click-to-expand JSON detail panels. Both the
 * expanded-id and the cached detail payload are owned by the parent
 * page so the detail survives a tab swap; this component is purely
 * presentational.
 */
import { motion, AnimatePresence } from 'framer-motion'
import { Crosshair } from 'lucide-react'
import { Card, EmptyState } from '@/components/common'
import { type ScanSummary, ScanRow } from './types'

interface Props {
  scans: ScanSummary[]
  expandedScan: string | null
  scanDetail: Record<string, unknown> | null
  onExpandScan: (id: string) => void
}

export default function SecurityScans({
  scans, expandedScan, scanDetail, onExpandScan,
}: Props) {
  if (scans.length === 0) {
    return (
      <EmptyState
        icon={<Crosshair className="text-starlight-500" size={40} />}
        title="No scans yet"
        description="No scans recorded yet"
      />
    )
  }

  return (
    <div className="space-y-2">
      {scans.map(scan => (
        <div key={scan.scan_id}>
          <button
            onClick={() => onExpandScan(scan.scan_id)}
            className="w-full text-left"
          >
            <ScanRow scan={scan} expanded={expandedScan === scan.scan_id} />
          </button>

          <AnimatePresence>
            {expandedScan === scan.scan_id && scanDetail && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <Card className="p-4 ml-4 mt-1 mb-2 border-starlight-700">
                  <pre className="text-xs text-starlight-400 overflow-x-auto max-h-96 overflow-y-auto">
                    {JSON.stringify(scanDetail, null, 2)}
                  </pre>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  )
}

