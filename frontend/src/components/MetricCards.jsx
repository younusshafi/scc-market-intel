import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

function Tooltip({ text }) {
  return (
    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1.5 bg-[#0F172A] border border-[#334155] rounded text-[10px] text-[#8896b0] whitespace-nowrap z-20 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
      {text}
    </div>
  )
}

function MetricCard({ value, label, accent, tooltip, sub }) {
  return (
    <div className={`relative group bg-[#111827] border border-[#1e2a42] border-l-4 ${accent} rounded-lg p-4 hover:border-[#2a3a5c] transition-colors cursor-default`}>
      {tooltip && <Tooltip text={tooltip} />}
      <div className="text-2xl font-mono font-bold text-[#e8ecf4] leading-none truncate">
        {value ?? '—'}
      </div>
      <div className="text-[10px] font-semibold text-[#5a6a85] uppercase tracking-wide mt-1.5 leading-tight">
        {label}
      </div>
      {sub && (
        <div className="text-[10px] text-[#5a6a85] mt-0.5 truncate">{sub}</div>
      )}
    </div>
  )
}

export default function MetricCards() {
  const { data, loading } = useAPI(api.getDashboardMetrics, [])

  if (loading || !data) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg p-4 animate-pulse">
              <div className="h-7 bg-[#1e2a42] rounded w-12 mb-2" />
              <div className="h-3 bg-[#1e2a42] rounded w-20" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg p-4 animate-pulse">
              <div className="h-7 bg-[#1e2a42] rounded w-12 mb-2" />
              <div className="h-3 bg-[#1e2a42] rounded w-20" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  const ht = data.highest_value_open_tender

  const row1 = [
    {
      value: data.tracked_projects,
      label: 'Tracked Projects',
      accent: 'border-l-blue-500',
      tooltip: 'SCC-relevant tenders with fee ≥ 200 OMR in core categories',
    },
    {
      value: data.competitive_tenders,
      label: 'Competitive Tenders',
      accent: 'border-l-red-500',
      tooltip: 'Open tenders where ≥1 tracked competitor purchased docs or bid',
    },
    {
      value: data.scc_active,
      label: 'SCC Active',
      accent: 'border-l-green-500',
      tooltip: 'Tenders where SCC has purchased docs or submitted a bid',
    },
    {
      value: data.closing_this_month,
      label: 'Closing This Month',
      accent: 'border-l-amber-500',
      tooltip: 'SCC-relevant tenders with bid closing date in next 30 days',
    },
    {
      value: data.news_signals,
      label: 'News Signals',
      accent: 'border-l-purple-500',
      tooltip: 'High-priority AI-classified news articles with SCC implications',
    },
  ]

  const row2 = [
    {
      value: data.scc_win_rate_ytd != null
        ? `${data.scc_win_rate_ytd}%`
        : '—',
      label: 'SCC Win Rate (YTD)',
      accent: 'border-l-emerald-500',
      tooltip: `${data.scc_wins_ytd ?? 0} wins from ${data.total_awarded_ytd ?? 0} construction awards this calendar year`,
      sub: data.total_awarded_ytd > 0 ? `${data.scc_wins_ytd}/${data.total_awarded_ytd} awards` : null,
    },
    {
      value: data.avg_competitors_per_tender != null
        ? data.avg_competitors_per_tender
        : '—',
      label: 'Avg Competitors/Tender',
      accent: 'border-l-orange-500',
      tooltip: 'Average number of tracked competitors bidding on same tenders as SCC (from probe data)',
    },
    {
      value: ht ? `${(ht.fee >= 1000 ? (ht.fee / 1000).toFixed(0) + 'K' : ht.fee)} OMR` : '—',
      label: 'Highest Open Tender',
      accent: 'border-l-cyan-500',
      tooltip: 'Highest doc-fee SCC-relevant open tender (fee = document purchase cost, not project value)',
      sub: ht ? ht.title?.substring(0, 40) + (ht.title?.length > 40 ? '…' : '') : null,
    },
    {
      value: data.most_active_competitor_30d ?? '—',
      label: 'Most Active (30 days)',
      accent: 'border-l-rose-500',
      tooltip: 'Tracked competitor with most doc purchases on SCC-relevant tenders in last 30 days',
      sub: data.most_active_competitor_30d_count > 0
        ? `${data.most_active_competitor_30d_count} purchases`
        : null,
    },
  ]

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {row1.map((m, i) => <MetricCard key={i} {...m} />)}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {row2.map((m, i) => <MetricCard key={i} {...m} />)}
      </div>
    </div>
  )
}
