import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const COMPETITOR_COLORS = {
  'Sarooj': '#2563EB',
  'Galfar': '#DC2626',
  'Strabag': '#EA580C',
  'Al Tasnim': '#16A34A',
  'L&T': '#7C3AED',
  'Towell': '#0891B2',
  'Hassan Allam': '#CA8A04',
  'Arab Contractors': '#BE185D',
  'Ozkar': '#6B7280',
}

function formatValue(val) {
  if (!val || val === 0) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
  if (val >= 1000) return `${Math.round(val / 1000)}K`
  return val.toLocaleString()
}

export default function AwardedIntelligence() {
  const { data, loading, error } = useAPI(api.getAwardedStats, [])

  if (loading) {
    return (
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-6 animate-pulse">
        <div className="h-5 w-40 bg-[#1e2a42] rounded mb-4" />
        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3].map(i => <div key={i} className="h-16 bg-[#0F172A] rounded-lg" />)}
        </div>
      </div>
    )
  }

  if (error || !data) return null

  const hasWinnerData = data.with_bid_details > 0
  const topWinners = data.top_winners || []

  return (
    <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-6 mt-6">
      <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
        Award History
      </h3>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-[#0F172A] rounded-lg p-4 text-center">
          <p className="font-mono text-2xl font-bold text-[#e8ecf4]">
            {data.construction_awarded?.toLocaleString() || '0'}
          </p>
          <p className="text-xs text-[#5a6a85] mt-1">Construction Awards</p>
        </div>
        <div className="bg-[#0F172A] rounded-lg p-4 text-center">
          <p className="font-mono text-2xl font-bold text-[#e8ecf4]">
            {data.total_contract_value ? `${formatValue(data.total_contract_value)} OMR` : 'Processing'}
          </p>
          <p className="text-xs text-[#5a6a85] mt-1">Total Contract Value</p>
        </div>
        <div className="bg-[#0F172A] rounded-lg p-4 text-center">
          <p className="font-mono text-2xl font-bold text-[#e8ecf4]">
            {data.total_awarded?.toLocaleString() || '0'}
          </p>
          <p className="text-xs text-[#5a6a85] mt-1">Total Awards (All)</p>
        </div>
      </div>

      {/* Top winners table */}
      {hasWinnerData && topWinners.length > 0 ? (
        <div>
          <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-3">
            Top Winners (Construction)
          </h4>
          <div className="bg-[#0F172A] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#5a6a85] border-b border-[#1e2a42]">
                  <th className="text-left py-2.5 px-4 font-medium">Competitor</th>
                  <th className="text-right py-2.5 px-4 font-medium">Wins</th>
                  <th className="text-right py-2.5 px-4 font-medium">Total Value</th>
                </tr>
              </thead>
              <tbody>
                {topWinners.map((w, i) => (
                  <tr key={i} className="border-b border-[#1e2a42] last:border-0">
                    <td className="py-2.5 px-4 text-[#e8ecf4]">
                      <span className="inline-block w-2.5 h-2.5 rounded-full mr-2"
                        style={{ backgroundColor: COMPETITOR_COLORS[w.company] || '#6B7280' }} />
                      {w.company}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">{w.wins}</td>
                    <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">
                      {w.total_value ? `${formatValue(w.total_value)} OMR` : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-[#0F172A] rounded-lg p-4 text-center">
          <p className="text-sm text-[#5a6a85]">
            Award details loading — historical bid data being processed
          </p>
          <div className="mt-2 flex justify-center">
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" style={{ animationDelay: '0.2s' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" style={{ animationDelay: '0.4s' }} />
            </div>
          </div>
        </div>
      )}

      {/* Top entities */}
      {data.top_entities && data.top_entities.length > 0 && (
        <div className="mt-5">
          <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-3">
            Top Awarding Entities
          </h4>
          <div className="space-y-2">
            {data.top_entities.slice(0, 5).map((e, i) => {
              const maxCount = data.top_entities[0]?.count || 1
              const pct = (e.count / maxCount) * 100
              return (
                <div key={i}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-[#e8ecf4] truncate mr-2">{e.entity}</span>
                    <span className="font-mono text-[#8896b0] flex-shrink-0">
                      {e.count} <span className="text-[#5a6a85]">({e.construction} const.)</span>
                    </span>
                  </div>
                  <div className="h-1.5 bg-[#1e2a42] rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-blue-500/60" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
