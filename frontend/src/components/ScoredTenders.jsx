import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import OpportunityRow from './OpportunityRow'
import TenderTable from './TenderTable'

export default function ScoredTenders() {
  const { data, loading, error, refetch } = useAPI(api.getScoredTenders, [])
  const { data: allTenders } = useAPI(() => api.getTenders({ scc_only: true, page_size: 200 }), [])
  const [subTab, setSubTab] = useState('recommended')
  const [showAll, setShowAll] = useState(false)
  const [scoring, setScoring] = useState(false)
  const [showRawTable, setShowRawTable] = useState(false)

  const tenders = data?.tenders || []
  const retenders = (allTenders?.tenders || []).filter(t => t.is_retender)

  // Closing soon = within 7 days
  const today = new Date()
  const closingSoonCount = tenders.filter(t => {
    if (!t.bid_closing_date) return false
    const days = (new Date(t.bid_closing_date) - today) / (1000 * 60 * 60 * 24)
    return days >= 0 && days <= 7
  }).length

  // Filter by sub-tab
  let displayed = []
  if (subTab === 'recommended') {
    displayed = tenders.filter(t => t.score >= 70).sort((a, b) => b.score - a.score)
  } else if (subTab === 'all') {
    displayed = [...tenders].sort((a, b) => b.score - a.score)
  } else if (subTab === 'closing') {
    const todayStr = today.toISOString().split('T')[0]
    displayed = tenders
      .filter(t => t.bid_closing_date && t.bid_closing_date >= todayStr)
      .sort((a, b) => (a.bid_closing_date || '').localeCompare(b.bid_closing_date || ''))
  } else if (subTab === 'retenders') {
    displayed = retenders
  }

  const limit = showAll ? displayed.length : 10
  const shown = displayed.slice(0, limit)

  async function handleTriggerScoring() {
    setScoring(true)
    try {
      await api.triggerScoring()
      await refetch()
    } catch (e) {
      console.error('Scoring failed:', e)
    } finally {
      setScoring(false)
    }
  }

  const tabs = [
    { id: 'recommended', label: 'Recommended', count: tenders.filter(t => t.score >= 70).length },
    { id: 'all', label: 'All Scored', count: tenders.length },
    {
      id: 'closing',
      label: 'Closing Soon',
      count: closingSoonCount,
      countStyle: closingSoonCount > 0
        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
        : 'bg-[#334155] text-[#5a6a85]',
    },
    { id: 'retenders', label: 'Re-Tenders', count: retenders.length },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
          Opportunities
        </h2>
        <button
          onClick={handleTriggerScoring}
          disabled={scoring}
          className="text-xs font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
        >
          {scoring ? 'Scoring...' : 'Re-run Scoring'}
        </button>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 mb-4 bg-[#0a0e17] rounded-lg p-1 border border-[#1e2a42]">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => { setSubTab(tab.id); setShowAll(false) }}
            className={`text-xs font-semibold py-2 px-4 rounded-md transition-colors flex items-center gap-1.5 ${
              subTab === tab.id
                ? 'bg-[#1e2a42] text-[#e8ecf4]'
                : 'text-[#5a6a85] hover:text-[#8896b0]'
            }`}
          >
            {tab.label}
            {tab.count !== null && tab.count > 0 && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${tab.countStyle || 'bg-[#334155] text-[#8896b0]'}`}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg h-20 animate-pulse" />
          ))}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#111827] border border-red-900/50 rounded-lg p-6 text-center">
          <p className="text-sm text-red-400">Failed to load scored tenders</p>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && displayed.length === 0 && (
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-8 text-center">
          <p className="text-sm text-[#5a6a85]">
            {subTab === 'retenders' ? 'No re-tenders detected' : 'No tenders in this view'}
          </p>
          {tenders.length === 0 && (
            <button
              onClick={handleTriggerScoring}
              disabled={scoring}
              className="mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
            >
              {scoring ? 'Running...' : 'Run AI Scoring'}
            </button>
          )}
        </div>
      )}

      {/* Rows */}
      {!loading && !error && shown.length > 0 && (
        <div className="space-y-2">
          {shown.map((tender, i) => (
            subTab === 'retenders' ? (
              <RetenderRow key={tender.tender_number || i} tender={tender} />
            ) : (
              <OpportunityRow key={tender.tender_number || i} tender={tender} />
            )
          ))}

          {displayed.length > 10 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full text-center text-xs text-blue-400 hover:text-blue-300 py-3 bg-[#111827] border border-[#1e2a42] rounded-lg hover:border-[#2a3a5c] transition-colors"
            >
              {showAll ? 'Show top 10' : `Show all ${displayed.length}`}
            </button>
          )}
        </div>
      )}

      {/* Raw tender table — collapsed by default */}
      <div className="mt-8">
        <button
          onClick={() => setShowRawTable(v => !v)}
          className="flex items-center gap-2 text-sm text-[#5a6a85] hover:text-[#8896b0] transition-colors"
        >
          <span
            className="text-[10px] transition-transform duration-200"
            style={{ display: 'inline-block', transform: showRawTable ? 'rotate(90deg)' : 'rotate(0deg)' }}
          >
            ▶
          </span>
          {showRawTable ? 'Hide' : 'View'} all SCC-relevant tenders (unscored)
        </button>
        {showRawTable && (
          <div className="mt-4">
            <TenderTable sccOnly={true} />
          </div>
        )}
      </div>
    </div>
  )
}

function RetenderRow({ tender }) {
  return (
    <div className="bg-[#111827] border border-[#1e2a42] border-l-4 border-l-orange-500 rounded-lg px-5 py-4">
      <h4 className="text-sm font-semibold text-[#e8ecf4] leading-snug mb-1">
        {tender.tender_name_en || tender.tender_number}
      </h4>
      <div className="flex flex-wrap items-center gap-x-2 text-xs text-[#5a6a85]">
        {tender.entity_en && <span>{tender.entity_en}</span>}
        {tender.category_en && <><span>·</span><span>{tender.category_en}</span></>}
        {tender.bid_closing_date && (
          <><span>·</span><span>Closes {new Date(tender.bid_closing_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span></>
        )}
        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-orange-900/40 text-orange-400 border border-orange-700 ml-1">
          RE-TENDER
        </span>
      </div>
    </div>
  )
}
