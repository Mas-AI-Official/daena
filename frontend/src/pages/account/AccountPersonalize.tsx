/**
 * AccountPersonalize -- AI personality preferences, memory settings, response style.
 * Equivalent to Perplexity's /account/personalize
 */
import { Sparkles, MessageSquare, Brain, BookOpen } from 'lucide-react'

export function AccountPersonalize() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-display font-semibold text-starlight-100">Personalization</h1>
        <p className="text-sm text-starlight-400 mt-1">Customize how Daena responds to you</p>
      </div>

      {/* Response style */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <MessageSquare size={14} /> Response style
        </h3>
        <div className="grid grid-cols-2 gap-3 max-w-lg">
          {['Concise', 'Detailed', 'Technical', 'Creative'].map((style) => (
            <button
              key={style}
              className="px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 text-sm text-starlight-300 hover:border-primary-500/30 hover:text-starlight-100 transition-all cursor-pointer"
            >
              {style}
            </button>
          ))}
        </div>
      </div>

      {/* Knowledge areas */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <BookOpen size={14} /> Your expertise
        </h3>
        <p className="text-xs text-starlight-500">Tell Daena about your background so it can tailor responses</p>
        <textarea
          placeholder="e.g., I'm a software engineer working on AI orchestration platforms. I prefer TypeScript and Python..."
          className="w-full max-w-lg h-24 px-3 py-2 rounded-lg bg-midnight-300/50 border border-white/10 text-sm text-starlight-100 focus:border-primary-500/50 focus:outline-none transition-colors resize-none"
        />
      </div>

      {/* Memory preferences */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Brain size={14} /> Memory
        </h3>
        <div className="space-y-2 max-w-lg">
          <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
            <span className="text-sm text-starlight-300">Remember conversation context</span>
            <input type="checkbox" defaultChecked className="rounded" />
          </label>
          <label className="flex items-center justify-between px-4 py-3 rounded-lg bg-midnight-300/30 border border-white/5 cursor-pointer">
            <span className="text-sm text-starlight-300">Learn from my corrections</span>
            <input type="checkbox" defaultChecked className="rounded" />
          </label>
        </div>
      </div>

      {/* Custom instructions */}
      <div className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
          <Sparkles size={14} /> Custom instructions
        </h3>
        <textarea
          placeholder="Any specific instructions for how Daena should behave..."
          className="w-full max-w-lg h-24 px-3 py-2 rounded-lg bg-midnight-300/50 border border-white/10 text-sm text-starlight-100 focus:border-primary-500/50 focus:outline-none transition-colors resize-none"
        />
      </div>

      <button className="px-6 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors cursor-pointer">
        Save personalization
      </button>
    </div>
  )
}

export default AccountPersonalize
