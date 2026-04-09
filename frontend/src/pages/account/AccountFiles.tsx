/**
 * AccountFiles -- Personal file management preferences.
 * Links to the main /files page for full management.
 */
import { useNavigate } from 'react-router-dom'
import { FileText, ExternalLink, HardDrive } from 'lucide-react'

export function AccountFiles() {
  const navigate = useNavigate()

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Files</h1>
        <p className="text-sm text-starlight-400 mt-1">Your personal file storage and preferences</p>
      </div>

      {/* Link to full files page */}
      <button
        onClick={() => navigate('/files')}
        className="flex items-center gap-3 p-4 rounded-xl bg-midnight-300/30 border border-white/5 hover:border-primary-500/20 transition-all cursor-pointer max-w-lg w-full text-left"
      >
        <FileText size={20} className="text-accent-cyan" />
        <div className="flex-1">
          <p className="text-sm font-medium text-starlight-100">Manage files</p>
          <p className="text-xs text-starlight-500">Upload, browse, and manage your workspace files</p>
        </div>
        <ExternalLink size={14} className="text-starlight-400" />
      </button>

      {/* Storage info */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <HardDrive size={14} /> Storage
        </h3>
        <div className="max-w-lg p-4 rounded-lg bg-midnight-300/30 border border-white/5">
          <div className="flex justify-between text-xs mb-2">
            <span className="text-starlight-400">Used</span>
            <span className="text-starlight-300">0 MB / 1 GB</span>
          </div>
          <div className="h-1.5 rounded-full bg-midnight-400 overflow-hidden">
            <div className="h-full rounded-full bg-primary-500/60" style={{ width: '0%' }} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default AccountFiles
