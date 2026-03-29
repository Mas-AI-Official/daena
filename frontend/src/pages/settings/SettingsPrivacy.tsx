/**
 * SettingsPrivacy -- Privacy & Data settings tab.
 * Export data, delete data, memory preferences, consent toggles.
 */
import { useState, useEffect } from 'react'
import { Download, Trash2, Database, Shield, AlertTriangle } from 'lucide-react'
import { toast } from '@/stores/toastStore'
import { Card, Switch } from '@/components/common'
import { api } from '@/lib/api'
import { persistUiPref } from '@/stores/uiStore'

export function SettingsPrivacy() {
  const [memoryGen, setMemoryGen] = useState(true)
  const [searchPast, setSearchPast] = useState(true)
  const [storageLocal, setStorageLocal] = useState(true)
  const [improveUsage, setImproveUsage] = useState(false)
  const [locationMeta, setLocationMeta] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const handleExport = async () => {
    try {
      const res = await api.get('/settings/user/export')
      const payload = res.data?.data ?? res.data
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `daena-export-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      toast.success('Data export downloaded')
    } catch {
      toast.error('Failed to export data')
    }
  }
  const handleDeleteRequest = async () => {
    try {
      await api.post('/settings/user/delete-request')
      toast.success('Delete request submitted')
      setDeleteConfirm(false)
    } catch {
      toast.error('Failed to submit delete request')
    }
  }

  // Hydrate from backend on mount
  useEffect(() => {
    api.get('/settings/user').then(res => {
      const d = res.data?.data
      if (!d) return
      if (d.memory_generation != null) setMemoryGen(d.memory_generation)
      if (d.search_past_conversations != null) setSearchPast(d.search_past_conversations)
      if (d.storage_local != null) setStorageLocal(d.storage_local)
      if (d.improve_from_usage != null) setImproveUsage(d.improve_from_usage)
      if (d.location_metadata != null) setLocationMeta(d.location_metadata)
    }).catch(() => {})
  }, [])

  return (
    <div className="space-y-8">
      {/* Your Data */}
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">Your Data</h3>
          <p className="text-xs text-starlight-400 mt-0.5">Control what Daena stores and how to export or delete it.</p>
        </div>
        <Card variant="glass" padding="md" className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-starlight-200">Export all data</p>
              <p className="text-[10px] text-starlight-500">Download everything: chats, memories, projects, settings. JSON archive.</p>
            </div>
            <button
              onClick={() => { void handleExport() }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-colors cursor-pointer"
            >
              <Download size={12} /> Export
            </button>
          </div>
          <div className="border-t border-white/5 pt-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-accent-red">Delete all data</p>
              <p className="text-[10px] text-starlight-500">Permanently remove all your data from Daena. Cannot be undone.</p>
            </div>
            {!deleteConfirm ? (
              <button
                onClick={() => setDeleteConfirm(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-red/10 text-accent-red hover:bg-accent-red/20 transition-colors cursor-pointer"
              >
                <Trash2 size={12} /> Delete
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button onClick={() => setDeleteConfirm(false)} className="px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-400 cursor-pointer">Cancel</button>
                <button
                  onClick={() => { void handleDeleteRequest() }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-accent-red/20 text-accent-red border border-accent-red/30 cursor-pointer"
                >
                  <AlertTriangle size={12} /> Confirm Delete
                </button>
              </div>
            )}
          </div>
        </Card>
      </section>

      {/* Memory Preferences */}
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">Memory Preferences</h3>
          <p className="text-xs text-starlight-400 mt-0.5">Control how Daena remembers and uses context.</p>
        </div>
        <Card variant="glass" padding="md" className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Generate memories from conversations</p>
              <p className="text-[10px] text-starlight-500">Daena extracts and stores relevant facts from your chats.</p>
            </div>
            <Switch checked={memoryGen} onChange={() => { setMemoryGen(!memoryGen); persistUiPref('memory_generation', !memoryGen) }} label="" size="sm" />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Search past conversations for context</p>
              <p className="text-[10px] text-starlight-500">Daena references previous chats for better answers.</p>
            </div>
            <Switch checked={searchPast} onChange={() => { setSearchPast(!searchPast); persistUiPref('search_past_conversations', !searchPast) }} label="" size="sm" />
          </div>

          <div className="border-t border-white/5 pt-3">
            <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold mb-2">Memory storage</p>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-xs text-starlight-300 cursor-pointer">
                <input type="radio" checked={storageLocal} onChange={() => { setStorageLocal(true); persistUiPref('storage_local', true) }} className="accent-primary-500" />
                <Database size={12} className="text-starlight-400" />
                Local only (Daena-Mind vault on your machine)
              </label>
              <label className="flex items-center gap-2 text-xs text-starlight-400 cursor-pointer">
                <input type="radio" checked={!storageLocal} onChange={() => { setStorageLocal(false); persistUiPref('storage_local', false) }} className="accent-primary-500" />
                <Shield size={12} className="text-starlight-500" />
                Cloud (encrypted, synced across devices) -- coming soon
              </label>
            </div>
          </div>
        </Card>
      </section>

      {/* Data Processing */}
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-display font-semibold text-starlight-100">Data Processing</h3>
          <p className="text-xs text-starlight-400 mt-0.5">Control how your data is used beyond your conversations.</p>
        </div>
        <Card variant="glass" padding="md" className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Allow Daena to improve from your usage</p>
              <p className="text-[10px] text-starlight-500">Conversations may improve Daena's capabilities. Never shared externally.</p>
            </div>
            <Switch checked={improveUsage} onChange={() => { setImproveUsage(!improveUsage); persistUiPref('improve_from_usage', !improveUsage) }} label="" size="sm" />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-starlight-200">Location metadata</p>
              <p className="text-[10px] text-starlight-500">Allow coarse location for local recommendations.</p>
            </div>
            <Switch checked={locationMeta} onChange={() => { setLocationMeta(!locationMeta); persistUiPref('location_metadata', !locationMeta) }} label="" size="sm" />
          </div>
        </Card>
      </section>
    </div>
  )
}

export default SettingsPrivacy
