import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const SCORE_COLORS = {
  high: 'bg-green-600',
  good: 'bg-blue-600',
  mid: 'bg-amber-600',
  low: 'bg-slate-600',
}

function getScoreColor(score) {
  if (score >= 80) return SCORE_COLORS.high
  if (score >= 60) return SCORE_COLORS.good
  if (score >= 40) return SCORE_COLORS.mid
  return SCORE_COLORS.low
}

const REC_STYLES = {
  'MUST_BID': 'bg-green-900/50 text-green-400 border-green-700',
  'STRONG_FIT': 'bg-blue-900/50 text-blue-400 border-blue-700',
  'CONSIDER': 'bg-amber-900/50 text-amber-400 border-amber-700',
  'WATCH': 'bg-slate-700/50 text-slate-400 border-slate-600',
  'SKIP': 'bg-slate-700/50 text-slate-400 border-slate-600',
}

const REC_LABELS = {
  'MUST_BID': 'Bid Aggressively',
  'STRONG_FIT': 'Strong Fit',
  'CONSIDER': 'Consider',
  'WATCH': 'Monitor',
  'SKIP': 'Skip',
}

const COMPETITOR_COLORS = {
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

function formatFee(fee) {
  if (!fee) return null
  if (typeof fee === 'string') return fee
  if (fee >= 1000000) return `${(fee / 1000000).toFixed(2)}M OMR`
  if (fee >= 1000) return `${Math.round(fee / 1000)}K OMR`
  return `${fee.toLocaleString()} OMR`
}

function SkeletonCard() {
  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 animate-pulse">
      <div className="flex gap-4">
        <div className="w-14 h-14 rounded-full bg-[#334155]" />
        <div className="flex-1 space-y-3">
          <div className="h-4 bg-[#334155] rounded w-3/4" />
          <div className="h-3 bg-[#334155] rounded w-1/2" />
          <div className="h-3 bg-[#334155] rounded w-full" />
        </div>
      </div>
    </div>
  )
}

function TenderCard({ tender }) {
  const scoreColor = getScoreColor(tender.score)
  const recStyle = REC_STYLES[tender.recommendation] || REC_STYLES['SKIP']
  const feeStr = formatFee(tender.fee)

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 hover:bg-[#253347] transition-colors">
      <div className="flex gap-4">
        {/* Score badge */}
        <div className={`flex-shrink-0 w-14 h-14 rounded-full ${scoreColor} flex items-center justify-center`}>
          <span className="text-white text-lg font-bold">{tender.score}</span>
        </div>

        <div className="flex-1 min-w-0">
          {/* Top row: recommendation + meta */}
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${recStyle}`}>
              {REC_LABELS[tender.recommendation] || tender.recommendation}
            </span>
            {tender.is_retender && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-orange-900/40 text-orange-400 border border-orange-700">
                RE-TENDER
              </span>
            )}
            {tender.grade_en && (
              <span className="text-[10px] text-[#8896b0]">{tender.grade_en}</span>
            )}
          </div>

          {/* Title */}
          <h4 className="text-sm font-semibold text-[#e8ecf4] leading-snug mb-1 line-clamp-2">
            {tender.tender_name_en || tender.tender_number}
          </h4>

          {/* Entity + fee */}
          <div className="flex flex-wrap items-center gap-3 text-xs text-[#8896b0] mb-2">
            {tender.entity_en && <span>{tender.entity_en}</span>}
            {feeStr && <span className="font-mono text-amber-400">{feeStr}</span>}
            {tender.bid_closing_date && (
              <span>Closes {new Date(tender.bid_closing_date).toLocaleDateString()}</span>
            )}
          </div>

          {/* Competitor chips */}
          {tender.tracked_competitors && tender.tracked_competitors.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {tender.tracked_competitors.map((comp, i) => (
                <span
                  key={i}
                  className="text-[9px] font-semibold text-white px-2 py-0.5 rounded-full"
                  style={{ backgroundColor: getCompetitorColor(comp.name) }}
                >
                  {comp.name}{comp.role ? ` (${comp.role})` : ''}
                </span>
              ))}
            </div>
          )}

          {/* AI reasoning */}
          {tender.reasoning && (
            <div className="bg-[#0F172A] rounded-lg px-3 py-2 mt-1">
              <p className="text-[11px] text-[#8896b0] leading-relaxed">
                <span className="text-[#5a6a85] font-semibold mr-1">AI:</span>
                {tender.reasoning}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ScoredTenders() {
  const { data, loading, error, refetch } = useAPI(api.getScoredTenders, [])
  const [showAll, setShowAll] = useState(false)
  const [scoring, setScoring] = useState(false)

  const tenders = data?.tenders || data?.scored_tenders || []
  const sorted = [...tenders].sort((a, b) => (b.score || 0) - (a.score || 0))
  const displayed = showAll ? sorted : sorted.slice(0, 15)
  const total = data?.total || tenders.length

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

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">
            AI Tender Match Scoring
          </h2>
          {total > 0 && (
            <span className="text-[10px] font-semibold bg-blue-600/20 text-blue-400 px-2 py-0.5 rounded-full">
              {total}
            </span>
          )}
        </div>
        {tenders.length > 0 && (
          <button
            onClick={handleTriggerScoring}
            disabled={scoring}
            className="text-[10px] font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
          >
            {scoring ? 'Scoring...' : 'Re-run Scoring'}
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#1E293B] border border-red-900/50 rounded-xl p-6 text-center">
          <p className="text-sm text-red-400 mb-2">Failed to load scored tenders</p>
          <p className="text-xs text-[#5a6a85]">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && tenders.length === 0 && (
        <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-8 text-center">
          <p className="text-sm text-[#8896b0] mb-3">No tenders scored yet</p>
          <button
            onClick={handleTriggerScoring}
            disabled={scoring}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
          >
            {scoring ? 'Running AI Scoring...' : 'Run AI Scoring'}
          </button>
        </div>
      )}

      {/* Tender cards */}
      {!loading && !error && tenders.length > 0 && (
        <div className="space-y-3">
          {displayed.map((tender, i) => (
            <TenderCard key={tender.tender_number || i} tender={tender} />
          ))}

          {sorted.length > 15 && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full text-center text-xs text-blue-400 hover:text-blue-300 py-3 bg-[#1E293B] border border-[#334155] rounded-xl hover:bg-[#253347] transition-colors"
            >
              {showAll ? 'Show top 15 only' : `Show all ${sorted.length} tenders`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
