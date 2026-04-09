/**
 * OrgComputer -- EXE mode organization-level policies.
 * Equivalent to Perplexity's /account/org/computer
 */
import { Monitor, Shield, Zap } from 'lucide-react'

export function OrgComputer() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Computer</h1>
        <p className="text-sm text-starlight-400 mt-1">Organization-level EXE mode policies and DaenaBot configuration</p>
      </div>

      {/* EXE mode settings */}
      <div className="space-y-4 max-w-lg">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Zap size={14} /> EXE Mode defaults
        </h3>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Allow EXE mode for all members</p>
            <p className="text-[10px] text-starlight-500">Members can use file, terminal, and browser agents</p>
          </div>
          <input type="checkbox" defaultChecked className="rounded" />
        </label>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Require governance approval for EXE actions</p>
            <p className="text-[10px] text-starlight-500">All DaenaBot tool calls go through approval queue</p>
          </div>
          <input type="checkbox" className="rounded" />
        </label>

        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200 pt-4">
          <Shield size={14} /> Security
        </h3>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Sandbox terminal commands</p>
            <p className="text-[10px] text-starlight-500">Restrict file system access to project directories only</p>
          </div>
          <input type="checkbox" defaultChecked className="rounded" />
        </label>

        <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
          <div>
            <p className="text-sm text-starlight-300">Block outbound network in EXE mode</p>
            <p className="text-[10px] text-starlight-500">Prevent agents from making external HTTP calls</p>
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

export default OrgComputer
