/**
 * About settings — version info, patents, links.
 */
import { useState, useEffect } from 'react'
import { Card } from '@/components/common'
import { Info, ExternalLink, FileText, Shield } from 'lucide-react'
import api from '@/lib/api'

export function SettingsAbout() {
  const [version, setVersion] = useState('v3.6.0')

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const res = await api.get('/health')
        if (res.data?.version) {
          setVersion(res.data.version)
        }
      } catch {
        // Keep default version
      }
    }
    fetchVersion()
  }, [])

  return (
    <div className="space-y-6">
      <Card variant="glass" padding="lg">
        <div className="text-center mb-6">
          <img
            src="/daena-gold.png"
            alt="Daena"
            className="w-16 h-16 mx-auto mb-3 rounded-2xl object-contain select-none"
            style={{ filter: 'drop-shadow(0 0 8px rgba(212,168,67,0.4))' }}
          />
          <h2 className="text-xl font-display font-bold text-starlight-100">Daena</h2>
          <p className="text-sm text-starlight-400">Governed Multi-Agent AI Orchestration</p>
          <p className="text-xs text-starlight-500 mt-1">{version}</p>
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Info size={14} /> About
        </h3>
        <div className="space-y-2 text-xs text-starlight-400">
          <p>
            Daena is an AI operating system where 10 department-agents collaborate
            like a company, governed by tiered policies, expert councils, and human
            audit/approval.
          </p>
          <p>
            Built by MAS-AI Technologies Inc., Ontario, Canada.
          </p>
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <Shield size={14} /> Intellectual Property
        </h3>
        <div className="space-y-2">
          {[
            { name: 'PhiLattice Architecture (sunflower-honeycomb)', status: 'USPTO Provisional Filed' },
            { name: 'NBMF (Neural-Backed Memory Fabric)', status: 'USPTO Provisional Filed' },
          ].map((p) => (
            <div key={p.name} className="flex items-center justify-between px-3 py-2 rounded-lg bg-midnight-800/40 border border-white/5">
              <div>
                <p className="text-xs text-starlight-200 font-semibold">{p.name}</p>
                <p className="text-[10px] text-starlight-500">{p.status}</p>
              </div>
              <FileText size={12} className="text-starlight-500" />
            </div>
          ))}
        </div>
      </Card>

      <Card variant="glass" padding="lg">
        <h3 className="text-sm font-display font-semibold text-starlight-100 mb-4 flex items-center gap-2">
          <ExternalLink size={14} /> Links
        </h3>
        <div className="space-y-2">
          {[
            { label: 'Documentation', href: 'https://daena.mas-ai.co' },
            { label: 'API Reference', href: `${window.location.origin}/docs` },
            { label: 'GitHub', href: 'https://github.com/Mas-AI-Official' },
            { label: 'MAS-AI Technologies', href: 'https://mas-ai.co' },
          ].map((l) => (
            <a
              key={l.label}
              href={l.href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-primary-400 hover:text-primary-300 transition-colors"
            >
              <ExternalLink size={10} />
              {l.label}
            </a>
          ))}
        </div>
      </Card>
    </div>
  )
}
