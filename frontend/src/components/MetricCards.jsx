export default function MetricCards({ stats, newsStats, loading }) {
  if (loading || !stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-surface border border-slate-700/50 rounded-xl p-5 animate-pulse">
            <div className="h-10 bg-slate-700 rounded w-16 mb-2" />
            <div className="h-3 bg-slate-700 rounded w-24" />
          </div>
        ))}
      </div>
    )
  }

  const metrics = [
    {
      value: stats.total,
      label: 'Active Pipeline',
      sub: 'Floated + In-Process',
      accent: 'bg-blue-500',
    },
    {
      value: stats.scc_relevant,
      label: 'SCC Addressable',
      sub: `${stats.scc_pct}% of pipeline`,
      accent: 'bg-emerald-500',
    },
    {
      value: stats.retenders,
      label: 'Re-Tenders',
      sub: 'In current dataset',
      accent: 'bg-amber-500',
    },
    {
      value: newsStats?.total || 0,
      label: 'News Signals',
      sub: `${newsStats?.competitor_mentions || 0} competitor mentions`,
      accent: 'bg-violet-500',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((m, i) => (
        <div
          key={i}
          className="bg-surface border border-slate-700/50 rounded-xl p-5 relative overflow-hidden hover:bg-surface-hover transition-colors group"
        >
          <div className={`absolute left-0 top-0 bottom-0 w-1 ${m.accent}`} />
          <div className="text-3xl font-extrabold text-white tabular-nums">{m.value}</div>
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mt-1">
            {m.label}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">{m.sub}</div>
        </div>
      ))}
    </div>
  )
}
