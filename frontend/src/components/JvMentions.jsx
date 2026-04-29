import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

export default function JvMentions() {
  const { data: stats, loading: statsLoading } = useAPI(api.getJvStats, [])
  const { data: mentions, loading: mentionsLoading } = useAPI(() => api.getJvMentions({ page_size: 20 }), [])

  const loading = statsLoading || mentionsLoading

  if (loading) {
    return (
      <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">JV & Consortium Mentions</h3>
        <p className="text-slate-500 text-sm">Loading...</p>
      </div>
    )
  }

  const totalJv = stats?.total_jv_mentions || 0
  const topPartners = stats?.top_partners || []
  const articles = mentions?.articles || []

  if (totalJv === 0 && articles.length === 0) {
    return (
      <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">JV & Consortium Mentions</h3>
        <p className="text-slate-500 text-sm">No joint venture or consortium mentions detected in news articles yet. JV detection runs on each news scrape.</p>
      </div>
    )
  }

  return (
    <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">JV & Consortium Mentions</h3>
        <span className="text-xs font-bold bg-purple-500 text-white px-3 py-0.5 rounded-full">{totalJv}</span>
      </div>

      {/* Partner frequency */}
      {topPartners.length > 0 && (
        <div className="mb-5">
          <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Companies mentioned in JV context</p>
          <div className="flex flex-wrap gap-2">
            {topPartners.map((p) => (
              <span key={p.name} className="px-3 py-1 bg-purple-500/10 border border-purple-500/30 rounded-full text-xs text-purple-300">
                {p.name} <span className="text-purple-500">({p.count})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Article list */}
      {articles.length > 0 && (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {articles.map((a) => (
            <div key={a.id} className="bg-slate-900 rounded-lg p-3 border-l-2 border-purple-500/50">
              <div className="flex justify-between items-start gap-3">
                <div className="flex-1 min-w-0">
                  <a
                    href={a.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-slate-200 hover:text-purple-300 transition-colors line-clamp-1"
                  >
                    {a.title}
                  </a>
                  {a.jv_details?.[0]?.context && (
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                      ...{a.jv_details[0].context}...
                    </p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[10px] text-slate-500">{a.source?.split(' — ')[0]}</div>
                  <div className="text-[10px] text-slate-600">{a.published?.split('T')[0] || ''}</div>
                </div>
              </div>
              {a.jv_details?.[0]?.partners?.length > 0 && (
                <div className="flex gap-1 mt-2">
                  {a.jv_details[0].partners.map((p) => (
                    <span key={p} className="px-2 py-0.5 bg-slate-800 rounded text-[10px] text-slate-400">{p}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
