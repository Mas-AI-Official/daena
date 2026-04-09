/**
 * OrgFiles -- Organization file policies and storage settings.
 * Equivalent to Perplexity's /account/org/files
 */
import { FolderOpen, Shield, HardDrive } from 'lucide-react'

export function OrgFiles() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Organization files</h1>
        <p className="text-sm text-starlight-400 mt-1">File storage policies and limits for your organization</p>
      </div>

      <div className="space-y-4 max-w-lg">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <HardDrive size={14} /> Storage limits
        </h3>

        <div className="p-4 rounded-lg bg-midnight-300/30 border border-white/5 space-y-3">
          <div className="flex justify-between text-xs">
            <span className="text-starlight-400">Organization storage</span>
            <span className="text-starlight-300">0 MB / 10 GB</span>
          </div>
          <div className="h-1.5 rounded-full bg-midnight-400 overflow-hidden">
            <div className="h-full rounded-full bg-primary-500/60" style={{ width: '0%' }} />
          </div>
          <div className="flex justify-between text-[10px] text-starlight-500">
            <span>Per-member limit: 1 GB</span>
            <span>Total members: 1</span>
          </div>
        </div>

        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200 pt-4">
          <Shield size={14} /> File policies
        </h3>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Allow file uploads in chat</p>
            <p className="text-[10px] text-starlight-500">Members can attach files to chat messages</p>
          </div>
          <input type="checkbox" defaultChecked className="rounded" />
        </label>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Auto-delete after 90 days</p>
            <p className="text-[10px] text-starlight-500">Files older than 90 days are automatically removed</p>
          </div>
          <input type="checkbox" className="rounded" />
        </label>
      </div>

      <button className="px-6 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors cursor-pointer">
        Save policies
      </button>
    </div>
  )
}

export default OrgFiles
