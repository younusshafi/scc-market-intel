import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

export default function GeoDistribution() {
  const { data, loading } = useAPI(api.getGeoDistribution, [])

  if (loading) {
    return (
      <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Geographic Distribution</h3>
        <p className="text-slate-500 text-sm">Loading...</p>
      </div>
    )
  }

  if (!data || data.total_tenders === 0) {
    return (
      <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Geographic Distribution</h3>
        <p className="text-slate-500 text-sm">No tender data available.</p>
      </div>
    )
  }

  const activeRegions = data.regions.filter(r => r.count > 0)
  const maxCount = Math.max(...activeRegions.map(r => r.count), 1)

  return (
    <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Geographic Distribution</h3>
        <div className="flex gap-3 text-[10px] text-slate-500">
          <span>{data.total_located} located</span>
          <span>{data.national} national</span>
          <span>{data.unlocated} unlocated</span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mb-4 text-[10px] text-slate-500">
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-blue-500 rounded" /> SCC-relevant</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-slate-600 rounded" /> Other</span>
      </div>

      {/* Bar chart */}
      <div className="space-y-2">
        {activeRegions.map((r) => (
          <div key={r.governorate} className="flex items-center gap-3">
            <span className="text-xs text-slate-400 w-36 truncate text-right" title={r.governorate}>
              {r.governorate}
            </span>
            <div className="flex-1 bg-slate-800 rounded-full h-4 overflow-hidden flex">
              {r.scc_relevant > 0 && (
                <div
                  className="h-full bg-blue-500"
                  style={{ width: `${(r.scc_relevant / maxCount) * 100}%` }}
                  title={`${r.scc_relevant} SCC-relevant`}
                />
              )}
              {(r.count - r.scc_relevant) > 0 && (
                <div
                  className="h-full bg-slate-600"
                  style={{ width: `${((r.count - r.scc_relevant) / maxCount) * 100}%` }}
                  title={`${r.count - r.scc_relevant} other`}
                />
              )}
            </div>
            <span className="text-xs text-slate-300 w-10 text-right">{r.count}</span>
            <span className="text-[10px] text-slate-500 w-12 text-right">{r.pct}%</span>
          </div>
        ))}

        {activeRegions.length === 0 && (
          <p className="text-sm text-slate-500 py-4">No tenders could be mapped to specific governorates. Most are issued by national-level entities.</p>
        )}
      </div>

      {/* National summary */}
      {data.national > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-700/50 flex items-center gap-3">
          <span className="text-xs text-slate-400 w-36 text-right">National / Multi-region</span>
          <div className="flex-1 bg-slate-800 rounded-full h-4 overflow-hidden">
            <div
              className="h-full bg-emerald-600/60"
              style={{ width: `${(data.national / Math.max(maxCount, data.national)) * 100}%` }}
            />
          </div>
          <span className="text-xs text-slate-300 w-10 text-right">{data.national}</span>
          <span className="text-[10px] text-slate-500 w-12 text-right">
            {data.total_tenders ? Math.round(data.national / data.total_tenders * 100) : 0}%
          </span>
        </div>
      )}
    </div>
  )
}
