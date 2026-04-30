export default function MetricCards({ stats, newsStats, loading }) {
  if (loading || !stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-[#1E293B] border border-[#334155] rounded-xl p-6 animate-pulse">
            <div className="h-10 bg-[#334155] rounded w-16 mb-2" />
            <div className="h-3 bg-[#334155] rounded w-24" />
          </div>
        ))}
      </div>
    )
  }

  const sccPct = stats.total ? Math.round((stats.scc_relevant / stats.total) * 100) : 0

  const metrics = [
    {
      value: stats.total,
      label: 'Active Pipeline',
      sub: 'Floated + In-Process',
      accent: 'border-blue-500',
    },
    {
      value: stats.scc_relevant,
      label: 'SCC Addressable',
      sub: `${stats.scc_pct || sccPct}% of pipeline`,
      accent: 'border-green-500',
      trend: stats.scc_pct > 20 ? 'up' : null,
    },
    {
      value: newsStats?.competitor_mentions || 0,
      label: 'Competitor Alerts',
      sub: 'Mentions this period',
      accent: 'border-amber-500',
    },
    {
      value: stats.retenders,
      label: 'Re-Tenders',
      sub: 'In current dataset',
      accent: 'border-purple-500',
    },
    {
      value: newsStats?.total || 0,
      label: 'News Signals',
      sub: 'Articles tracked',
      accent: 'border-cyan-500',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      {metrics.map((m, i) => (
        <div
          key={i}
          className={`bg-[#1E293B] border border-[#334155] rounded-xl p-6 border-l-4 ${m.accent} hover:bg-[#253347] transition-colors`}
        >
          <div className="text-[2.5rem] font-mono font-bold text-white leading-none">{m.value}</div>
          <div className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mt-2">
            {m.label}
          </div>
          <div className="text-xs text-[#8896b0] mt-0.5 flex items-center gap-1">
            {m.sub}
            {m.trend === 'up' && <span className="text-green-500">&#8593;</span>}
            {m.trend === 'down' && <span className="text-red-500">&#8595;</span>}
          </div>
        </div>
      ))}
    </div>
  )
}
