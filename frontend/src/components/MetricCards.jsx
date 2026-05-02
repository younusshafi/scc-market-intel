import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

export default function MetricCards() {
  const { data, loading } = useAPI(api.getDashboardMetrics, [])

  if (loading || !data) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5 animate-pulse">
            <div className="h-9 bg-[#1e2a42] rounded w-14 mb-2" />
            <div className="h-4 bg-[#1e2a42] rounded w-24" />
          </div>
        ))}
      </div>
    )
  }

  const metrics = [
    {
      value: data.tracked_projects,
      label: 'Tracked Projects',
      accent: 'border-l-blue-500',
    },
    {
      value: data.competitive_tenders,
      label: 'Competitive Tenders',
      accent: 'border-l-red-500',
    },
    {
      value: data.scc_active,
      label: 'SCC Active',
      accent: 'border-l-green-500',
    },
    {
      value: data.closing_this_month,
      label: 'Closing This Month',
      accent: 'border-l-amber-500',
    },
    {
      value: data.news_signals,
      label: 'News Signals',
      accent: 'border-l-purple-500',
    },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      {metrics.map((m, i) => (
        <div
          key={i}
          className={`bg-[#111827] border border-[#1e2a42] border-l-4 ${m.accent} rounded-lg p-5 hover:border-[#2a3a5c] transition-colors`}
        >
          <div className="text-3xl font-mono font-bold text-[#e8ecf4] leading-none">
            {m.value ?? 0}
          </div>
          <div className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wide mt-2">
            {m.label}
          </div>
        </div>
      ))}
    </div>
  )
}
