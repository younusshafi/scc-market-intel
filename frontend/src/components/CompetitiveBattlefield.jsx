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

function getCompetitorColor(name) {
  if (!name) return '#6B7280'
  const key = Object.keys(COMPETITOR_COLORS).find(k => name.toLowerCase().includes(k.toLowerCase()))
  return key ? COMPETITOR_COLORS[key] : '#6B7280'
}

function formatValue(val) {
  if (!val || val === 0) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(2)}M`
  if (val >= 1000) return `${Math.round(val / 1000)}K`
  return val.toLocaleString()
}

function LivePulse() {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
      </span>
      <span className="text-red-400 text-[10px] font-bold uppercase tracking-wider">LIVE</span>
    </span>
  )
}

function LiveCompetitiveTenders({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
          Live Competitive Tenders
        </h3>
        <LivePulse />
      </div>
      <div className="space-y-3">
        {data.map((item, idx) => {
          const tracked = [...(item.tracked || [])].sort((a, b) =>
            (a.date || '').localeCompare(b.date || '')
          )

          return (
            <div key={idx} className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5 hover:border-[#2a3a5c] transition-colors">
              <div className="flex items-start justify-between gap-4">
                {/* Left: project info */}
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-semibold text-[#e8ecf4] leading-snug mb-1">{item.project}</h4>
                  <p className="text-xs text-[#5a6a85] mb-2">
                    {item.total_purchasers} doc purchasers
                    {item.has_bids && <span className="text-amber-400 ml-2">· Bids received</span>}
                  </p>
                </div>
                {/* Right: competitor avatars + count */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <div className="flex -space-x-1">
                    {tracked.slice(0, 5).map((c, i) => (
                      <span
                        key={i}
                        className="w-6 h-6 rounded-full border-2 border-[#111827] flex items-center justify-center text-[8px] font-bold text-white"
                        style={{ backgroundColor: getCompetitorColor(c.name) }}
                        title={c.name}
                      >
                        {(c.name || '')[0]}
                      </span>
                    ))}
                  </div>
                  <span className="text-sm font-bold text-[#e8ecf4]">{item.tracked_count} active</span>
                </div>
              </div>

              {/* Timeline bar */}
              {tracked.length > 0 && (
                <div className="mt-4 relative">
                  <div className="h-0.5 bg-[#1e2a42] rounded-full absolute top-3 left-0 right-0" />
                  <div className="flex justify-between relative">
                    {tracked.map((c, i) => (
                      <div key={i} className="flex flex-col items-center" style={{ flex: 1 }}>
                        <span
                          className="w-3.5 h-3.5 rounded-full border-2 border-[#111827] z-10"
                          style={{ backgroundColor: getCompetitorColor(c.name) }}
                        />
                        <span className="text-[10px] font-semibold text-[#8896b0] mt-1.5 text-center">
                          {c.name}
                        </span>
                        <span className="text-[10px] font-mono text-[#5a6a85]">
                          {c.date ? c.date.slice(5) : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function HeadToHeadSection({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="mt-8">
      <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
        Head-to-Head: SCC vs Competitors
      </h3>
      <div className="space-y-3">
        {data.map((item, idx) => {
          const maxVal = Math.max(...(item.rows || []).map(r => r.value || 0), 1)
          const sccRow = (item.rows || []).find(r => r.is_scc)
          const isLowest = sccRow && (item.rows || []).every(r => r.is_scc || r.value >= sccRow.value)

          return (
            <div key={idx} className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-semibold text-[#e8ecf4]">{item.project}</h4>
                {isLowest && (
                  <span className="text-[10px] font-bold px-2.5 py-1 rounded bg-green-500/20 text-green-400 border border-green-500/40">
                    LOWEST BIDDER
                  </span>
                )}
              </div>
              <div className="space-y-3">
                {(item.rows || []).map((row, i) => {
                  const pct = maxVal ? (row.value / maxVal) * 100 : 0
                  const isSCC = row.is_scc
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-xs text-[#8896b0] w-24 truncate flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{ backgroundColor: getCompetitorColor(row.name) }} />
                        {row.name}
                      </span>
                      <div className="flex-1 h-2.5 bg-[#0F172A] rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${isSCC ? 'bg-amber-400' : 'bg-slate-500'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-mono text-[#e8ecf4] w-20 text-right">
                        {formatValue(row.value)} OMR
                      </span>
                      {!isSCC && row.diff_pct != null && (
                        <span className={`text-xs font-mono w-16 text-right ${row.diff_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {row.diff_pct > 0 ? '+' : ''}{row.diff_pct.toFixed(1)}%
                        </span>
                      )}
                      {isSCC && <span className="text-xs text-[#5a6a85] w-16 text-right">SCC</span>}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ActivitySummaryTable({ data }) {
  if (!data || data.length === 0) return null
  const sorted = [...data].sort((a, b) => ((b.docs || 0) + (b.bids || 0)) - ((a.docs || 0) + (a.bids || 0)))

  return (
    <div className="mt-8">
      <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
        Competitor Activity Summary
      </h3>
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-[#5a6a85] border-b border-[#1e2a42]">
              <th className="text-left py-3 px-4 font-medium">Competitor</th>
              <th className="text-right py-3 px-4 font-medium">Docs</th>
              <th className="text-right py-3 px-4 font-medium">Bids</th>
              <th className="text-right py-3 px-4 font-medium">Conv %</th>
              <th className="text-right py-3 px-4 font-medium">Largest Bid</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => {
              const isSarooj = row.name?.toLowerCase().includes('sarooj')
              const conv = row.conv || 0
              const convColor = conv >= 50 ? 'text-green-400' : conv >= 40 ? 'text-amber-400' : 'text-[#8896b0]'
              return (
                <tr key={i} className={isSarooj ? 'bg-blue-900/20' : ''}>
                  <td className="py-2.5 px-4 text-[#e8ecf4]">
                    <span className="inline-block w-2.5 h-2.5 rounded-full mr-2"
                      style={{ backgroundColor: getCompetitorColor(row.name) }} />
                    {row.name}
                  </td>
                  <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">{row.docs || 0}</td>
                  <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">{row.bids || 0}</td>
                  <td className={`py-2.5 px-4 text-right font-mono ${convColor}`}>{conv}%</td>
                  <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">
                    {row.max_bid ? `${formatValue(row.max_bid)} OMR` : '--'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function HistoricalWinRates({ winners }) {
  if (!winners || !winners.competitors || winners.competitors.length === 0) return null

  const sorted = [...winners.competitors]
    .filter(c => c.total_bids > 0)
    .sort((a, b) => b.win_rate - a.win_rate)

  const maxRate = Math.max(...sorted.map(c => c.win_rate), 1)

  return (
    <div className="mt-6">
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
        <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
          Historical Win Rates (Construction Awards)
        </h3>
        <div className="space-y-2.5">
          {sorted.map((c, i) => {
            const pct = (c.win_rate / maxRate) * 100
            return (
              <div key={i} className="flex items-center gap-3">
                <div className="w-24 flex-shrink-0">
                  <span className="text-xs text-[#e8ecf4] font-medium">{c.company}</span>
                </div>
                <div className="flex-1 h-5 bg-[#0F172A] rounded-full overflow-hidden relative">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: COMPETITOR_COLORS[c.company] || '#6B7280',
                      opacity: 0.7,
                    }}
                  />
                </div>
                <div className="w-40 flex-shrink-0 text-right">
                  <span className="text-xs font-mono text-[#8896b0]">
                    {c.total_wins} wins / {c.total_bids} bids
                  </span>
                  <span className="text-xs font-mono text-[#e8ecf4] ml-2 font-semibold">
                    ({c.win_rate}%)
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function CompetitiveBattlefield() {
  const { data, loading, error } = useAPI(() => api.getCompetitiveIntel(), [])
  const { data: winners } = useAPI(() => api.getAwardedWinners(), [])

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg h-28 animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-[#111827] border border-red-900/50 rounded-lg p-6 text-center">
        <p className="text-sm text-red-400">Failed to load competitive intelligence</p>
      </div>
    )
  }

  const headToHead = data?.head_to_head || []
  const liveCompetitive = data?.live_competitive || []
  const activitySummary = data?.activity_summary || []

  return (
    <div>
      <LiveCompetitiveTenders data={liveCompetitive} />
      <HeadToHeadSection data={headToHead} />
      <ActivitySummaryTable data={activitySummary} />
      <HistoricalWinRates winners={winners} />
    </div>
  )
}
