import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { LayoutGrid, Table2, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'

const VALUE_STYLES = {
  critical: { badge: 'bg-red-600 text-white',    row: 'text-red-400' },
  high:     { badge: 'bg-amber-500 text-white',   row: 'text-amber-400' },
  medium:   { badge: 'bg-blue-600 text-white',    row: 'text-blue-400' },
  low:      { badge: 'bg-slate-600 text-white',   row: 'text-slate-400' },
}

function getValueStyle(val) {
  return VALUE_STYLES[val?.toLowerCase()] || VALUE_STYLES.low
}

// ── Card component ────────────────────────────────────────────────────────────
function EntityCard({ entity, onSelect }) {
  const { badge } = getValueStyle(entity.strategic_value)

  return (
    <div
      className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 hover:bg-[#253347] transition-colors cursor-pointer"
      onClick={() => onSelect?.(entity)}
    >
      <div className="flex items-start justify-between mb-3">
        <h4 className="text-sm font-bold text-[#e8ecf4] leading-snug max-w-[70%]">{entity.entity_name}</h4>
        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${badge}`}>
          {entity.strategic_value?.toUpperCase() || 'UNKNOWN'}
        </span>
      </div>

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

      {entity.insight && (
        <p className="text-xs text-[#8896b0] mb-3 leading-relaxed">{entity.insight}</p>
      )}

      {entity.action && (
        <div className="border-l-2 border-green-500 bg-[#0F172A] rounded-r-lg px-3 py-2 mb-3">
          <p className="text-[11px] text-[#8896b0] italic leading-relaxed">
            <span className="text-green-400 font-semibold not-italic mr-1">Action:</span>
            {entity.action}
          </p>
        </div>
      )}

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

// ── Detail overlay (used by table "View" button) ──────────────────────────────
function EntityDetail({ entity, onClose }) {
  if (!entity) return null
  const { badge } = getValueStyle(entity.strategic_value)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-[#111827] border border-[#1e2a42] rounded-xl p-6 max-w-lg w-full shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <h3 className="text-sm font-bold text-[#e8ecf4] leading-snug pr-4">{entity.entity_name}</h3>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${badge}`}>
              {entity.strategic_value?.toUpperCase()}
            </span>
            <button onClick={onClose} className="text-[#5a6a85] hover:text-[#e8ecf4] transition-colors text-lg leading-none">×</button>
          </div>
        </div>

        <div className="flex gap-6 mb-4">
          <div><span className="text-xl font-mono font-bold text-[#e8ecf4]">{entity.total_tenders}</span><p className="text-[9px] text-[#5a6a85] uppercase">Tenders</p></div>
          <div><span className="text-xl font-mono font-bold text-[#e8ecf4]">{entity.scc_relevant_count}</span><p className="text-[9px] text-[#5a6a85] uppercase">SCC Relevant</p></div>
          {entity.avg_fee > 0 && (
            <div><span className="text-xl font-mono font-bold text-[#e8ecf4]">{entity.avg_fee}</span><p className="text-[9px] text-[#5a6a85] uppercase">Avg Fee (OMR)</p></div>
          )}
        </div>

        {entity.insight && <p className="text-xs text-[#8896b0] mb-4 leading-relaxed">{entity.insight}</p>}

        {entity.action && (
          <div className="border-l-2 border-green-500 bg-[#0F172A] rounded-r-lg px-3 py-2 mb-4">
            <p className="text-[11px] text-[#8896b0] italic leading-relaxed">
              <span className="text-green-400 font-semibold not-italic mr-1">Action:</span>
              {entity.action}
            </p>
          </div>
        )}

        <div className="flex flex-wrap gap-1.5">
          {(entity.competitors_present || []).map((comp, i) => (
            <span key={`c${i}`} className="text-[9px] font-semibold px-2 py-0.5 rounded-full border border-red-500/40 text-red-400">{comp}</span>
          ))}
          {(entity.top_categories || []).map((cat, i) => (
            <span key={`k${i}`} className="text-[9px] font-semibold px-2 py-0.5 rounded-full border border-blue-500/40 text-blue-400">{cat}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Sortable column header ─────────────────────────────────────────────────────
function SortHeader({ label, sortKey, col, sortDir, onSort }) {
  const active = sortKey === col
  return (
    <th
      className="px-3 py-2.5 text-left text-[10px] font-semibold text-[#5a6a85] uppercase tracking-wider cursor-pointer select-none hover:text-[#8896b0] transition-colors whitespace-nowrap"
      onClick={() => onSort(col)}
    >
      <span className="flex items-center gap-1">
        {label}
        {active
          ? (sortDir === 'asc' ? <ChevronUp size={11} className="text-blue-400" /> : <ChevronDown size={11} className="text-blue-400" />)
          : <ChevronsUpDown size={11} className="opacity-40" />}
      </span>
    </th>
  )
}

// ── Table view ────────────────────────────────────────────────────────────────
function EntityTable({ entities, onSelect }) {
  const [sortKey, setSortKey] = useState('total_tenders')
  const [sortDir, setSortDir] = useState('desc')

  function handleSort(col) {
    if (sortKey === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(col); setSortDir('desc') }
  }

  const sorted = [...entities].sort((a, b) => {
    const va = a[sortKey] ?? ''
    const vb = b[sortKey] ?? ''
    const cmp = typeof va === 'string' ? va.localeCompare(vb) : (va - vb)
    return sortDir === 'asc' ? cmp : -cmp
  })

  const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }

  // Override sort for strategic_value to use semantic order
  const display = sortKey === 'strategic_value'
    ? [...entities].sort((a, b) => {
        const va = PRIORITY_ORDER[a.strategic_value?.toLowerCase()] ?? 9
        const vb = PRIORITY_ORDER[b.strategic_value?.toLowerCase()] ?? 9
        return sortDir === 'asc' ? va - vb : vb - va
      })
    : sorted

  const cols = [
    { key: 'entity_name',       label: 'Entity' },
    { key: 'strategic_value',   label: 'Priority' },
    { key: 'total_tenders',     label: 'Tenders' },
    { key: 'scc_relevant_count',label: 'SCC Overlap' },
    { key: 'avg_fee',           label: 'Avg Fee (OMR)' },
  ]

  return (
    <div className="overflow-x-auto rounded-xl border border-[#1e2a42]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-[#0a0e1a] z-10">
          <tr>
            {cols.map(c => (
              <SortHeader
                key={c.key}
                label={c.label}
                col={c.key}
                sortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
              />
            ))}
            <th className="px-3 py-2.5 text-[10px] font-semibold text-[#5a6a85] uppercase tracking-wider text-right">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {display.map((entity, i) => {
            const { badge, row: rowColor } = getValueStyle(entity.strategic_value)
            return (
              <tr
                key={entity.id}
                className={`border-t border-[#1e2a42] transition-colors hover:bg-[#111827] ${
                  i % 2 === 0 ? 'bg-[#0d1221]' : 'bg-[#0a0e1a]'
                }`}
              >
                <td className="px-3 py-2.5 font-medium text-[#e8ecf4] max-w-[200px]">
                  <span className="truncate block" title={entity.entity_name}>{entity.entity_name}</span>
                </td>
                <td className="px-3 py-2.5">
                  <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${badge}`}>
                    {entity.strategic_value?.toUpperCase() || '—'}
                  </span>
                </td>
                <td className="px-3 py-2.5 font-mono text-[#e8ecf4]">{entity.total_tenders ?? '—'}</td>
                <td className="px-3 py-2.5 font-mono text-[#e8ecf4]">{entity.scc_relevant_count ?? '—'}</td>
                <td className="px-3 py-2.5 font-mono text-[#8896b0]">{entity.avg_fee > 0 ? entity.avg_fee : '—'}</td>
                <td className="px-3 py-2.5 text-right">
                  <button
                    onClick={() => onSelect(entity)}
                    className="px-2.5 py-1 text-[10px] font-semibold rounded border border-[#1e2a42] text-[#8896b0] hover:text-blue-400 hover:border-blue-500/40 transition-colors"
                  >
                    View
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Main export ────────────────────────────────────────────────────────────────
const LS_KEY = 'entity-intel-view'

export default function EntityIntelligence() {
  const { data, loading, error, refetch } = useAPI(api.getEntityIntel, [])
  const [building, setBuilding] = useState(false)
  const [selectedEntity, setSelectedEntity] = useState(null)

  // Persist view in localStorage; force cards on mobile via CSS (the grid/table choice
  // is stored but the table is hidden on small screens via `hidden sm:block`)
  const [view, setView] = useState(() => {
    try { return localStorage.getItem(LS_KEY) || 'cards' } catch { return 'cards' }
  })

  function switchView(v) {
    setView(v)
    try { localStorage.setItem(LS_KEY, v) } catch {}
  }

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
        <div className="flex items-center gap-3">
          {/* View toggle — hidden on mobile (always shows cards) */}
          {entities.length > 0 && (
            <div className="hidden sm:flex items-center gap-0.5 p-0.5 bg-[#0a0e1a] border border-[#1e2a42] rounded-lg">
              <button
                onClick={() => switchView('cards')}
                title="Card view"
                className={`p-1.5 rounded-md transition-colors ${view === 'cards' ? 'bg-[#162440] text-white' : 'text-[#5a6a85] hover:text-[#8896b0]'}`}
              >
                <LayoutGrid size={13} />
              </button>
              <button
                onClick={() => switchView('table')}
                title="Table view"
                className={`p-1.5 rounded-md transition-colors ${view === 'table' ? 'bg-[#162440] text-white' : 'text-[#5a6a85] hover:text-[#8896b0]'}`}
              >
                <Table2 size={13} />
              </button>
            </div>
          )}
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

      {/* Empty */}
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

      {/* Content — cards always on mobile, toggle on desktop */}
      {!loading && !error && entities.length > 0 && (
        <>
          {/* Cards: shown when view=cards, OR always on mobile (sm:hidden overrides on table mode) */}
          <div className={view === 'table' ? 'sm:hidden' : ''}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {entities.map(entity => (
                <EntityCard key={entity.id} entity={entity} onSelect={setSelectedEntity} />
              ))}
            </div>
          </div>

          {/* Table: only on sm+ when table view is selected */}
          {view === 'table' && (
            <div className="hidden sm:block">
              <EntityTable entities={entities} onSelect={setSelectedEntity} />
            </div>
          )}
        </>
      )}

      {/* Detail overlay */}
      {selectedEntity && (
        <EntityDetail entity={selectedEntity} onClose={() => setSelectedEntity(null)} />
      )}
    </div>
  )
}
