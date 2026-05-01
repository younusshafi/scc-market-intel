import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const VALUE_STYLES = {
  critical: 'bg-red-600 text-white',
  high: 'bg-amber-600 text-white',
  medium: 'bg-blue-600 text-white',
  low: 'bg-slate-600 text-white',
}

function EntityCard({ entity }) {
  const valueStyle = VALUE_STYLES[entity.strategic_value?.toLowerCase()] || VALUE_STYLES.low

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 hover:bg-[#253347] transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <h4 className="text-sm font-bold text-[#e8ecf4] leading-snug max-w-[70%]">{entity.entity_name}</h4>
        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${valueStyle}`}>
          {entity.strategic_value?.toUpperCase() || 'UNKNOWN'}
        </span>
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-4 mb-3">
        <div className="text-center">
          <span className="text-lg font-mono font-bold text-[#e8ecf4]">{entity.total_tenders}</span>
          <p className="text-[9px] text-[#5a6a85] uppercase">Tenders</p>
        </div>
        <div className="text-center">
          <span className="text-lg font-mono font-bold text-[#e8ecf4]">{entity.scc_relevant_count}</span>
          <p className="text-[9px] text-[#5a6a85] uppercase">SCC Relevant</p>
        </div>
        {entity.avg_fee > 0 && (
          <div className="text-center">
            <span className="text-lg font-mono font-bold text-[#e8ecf4]">{entity.avg_fee}</span>
            <p className="text-[9px] text-[#5a6a85] uppercase">Avg Fee (OMR)</p>
          </div>
        )}
      </div>

      {/* AI Insight */}
      {entity.insight && (
        <p className="text-xs text-[#8896b0] mb-3 leading-relaxed">
          {entity.insight}
        </p>
      )}

      {/* Action */}
      {entity.action && (
        <div className="border-l-2 border-green-500 bg-[#0F172A] rounded-r-lg px-3 py-2 mb-3">
          <p className="text-[11px] text-[#8896b0] italic leading-relaxed">
            <span className="text-green-400 font-semibold not-italic mr-1">Action:</span>
            {entity.action}
          </p>
        </div>
      )}

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {(entity.competitors_present || []).map((comp, i) => (
          <span key={`comp-${i}`} className="text-[9px] font-semibold px-2 py-0.5 rounded-full border border-red-500/40 text-red-400">
            {comp}
          </span>
        ))}
        {(entity.top_categories || []).map((cat, i) => (
          <span key={`cat-${i}`} className="text-[9px] font-semibold px-2 py-0.5 rounded-full border border-blue-500/40 text-blue-400">
            {cat}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function EntityIntelligence() {
  const { data, loading, error, refetch } = useAPI(api.getEntityIntel, [])
  const [building, setBuilding] = useState(false)

  const entities = data?.entities || []

  async function handleBuild() {
    setBuilding(true)
    try {
      await api.buildEntityIntel()
      await refetch()
    } catch (e) {
      console.error('Entity intel build failed:', e)
    } finally {
      setBuilding(false)
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">
            Entity Intelligence
          </h2>
          {entities.length > 0 && (
            <span className="text-[10px] font-semibold bg-blue-600/20 text-blue-400 px-2 py-0.5 rounded-full">
              {entities.length}
            </span>
          )}
        </div>
        {entities.length > 0 && (
          <button
            onClick={handleBuild}
            disabled={building}
            className="text-[10px] font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
          >
            {building ? 'Building...' : 'Rebuild Intel'}
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 animate-pulse">
              <div className="flex justify-between mb-3">
                <div className="h-4 w-40 bg-[#334155] rounded" />
                <div className="h-4 w-14 bg-[#334155] rounded-full" />
              </div>
              <div className="flex gap-4 mb-3">
                <div className="h-8 w-12 bg-[#334155] rounded" />
                <div className="h-8 w-12 bg-[#334155] rounded" />
              </div>
              <div className="h-3 bg-[#334155] rounded w-full mb-2" />
              <div className="h-3 bg-[#334155] rounded w-2/3" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#1E293B] border border-red-900/50 rounded-xl p-6 text-center">
          <p className="text-sm text-red-400 mb-2">Failed to load entity intelligence</p>
          <p className="text-xs text-[#5a6a85]">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && entities.length === 0 && (
        <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-8 text-center">
          <p className="text-sm text-[#8896b0] mb-3">No entity intelligence built yet</p>
          <button
            onClick={handleBuild}
            disabled={building}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
          >
            {building ? 'Building Intel...' : 'Build Intel'}
          </button>
        </div>
      )}

      {/* Entity cards */}
      {!loading && !error && entities.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {entities.map((entity) => (
            <EntityCard key={entity.id} entity={entity} />
          ))}
        </div>
      )}
    </div>
  )
}
