import { useState } from 'react'

const COMPETITOR_COLORS = {
  'Galfar': '#DC2626',
  'Strabag': '#EA580C',
  'Al Tasnim': '#16A34A',
  'L&T': '#7C3AED',
  'Towell': '#0891B2',
  'Hassan Allam': '#CA8A04',
  'Arab Contractors': '#BE185D',
  'Ozkar': '#6B7280',
  'Sarooj': '#2563EB',
}

function getCompetitorColor(name) {
  if (!name) return '#6B7280'
  const key = Object.keys(COMPETITOR_COLORS).find(k => name.toLowerCase().includes(k.toLowerCase()))
  return key ? COMPETITOR_COLORS[key] : '#6B7280'
}

function getScoreBarColor(score) {
  if (score >= 85) return 'from-green-500 to-emerald-400'
  if (score >= 70) return 'from-blue-500 to-blue-400'
  return 'from-amber-500 to-amber-400'
}

function getRecLabel(rec) {
  const map = {
    'MUST_BID': { label: 'BID NOW', cls: 'bg-green-500/20 text-green-400 border-green-500/40' },
    'STRONG_FIT': { label: 'EVALUATE', cls: 'bg-blue-500/20 text-blue-400 border-blue-500/40' },
    'CONSIDER': { label: 'EVALUATE', cls: 'bg-blue-500/20 text-blue-400 border-blue-500/40' },
    'WATCH': { label: 'MONITOR', cls: 'bg-amber-500/20 text-amber-400 border-amber-500/40' },
    'SKIP': { label: 'MONITOR', cls: 'bg-slate-500/20 text-slate-400 border-slate-500/40' },
  }
  return map[rec] || map['WATCH']
}

export default function OpportunityRow({ tender }) {
  const [expanded, setExpanded] = useState(false)

  const score = tender.score || 0
  const recConfig = getRecLabel(tender.recommendation)
  const barColor = getScoreBarColor(score)

  // Closing urgency
  const today = new Date()
  const closingDate = tender.bid_closing_date ? new Date(tender.bid_closing_date) : null
  const daysUntilClose = closingDate ? Math.ceil((closingDate - today) / (1000 * 60 * 60 * 24)) : null
  const closingUrgent = daysUntilClose !== null && daysUntilClose <= 14
  const closingCritical = daysUntilClose !== null && daysUntilClose <= 7

  return (
    <div
      className="bg-[#111827] border border-[#1e2a42] rounded-lg hover:border-[#2a3a5c] transition-all cursor-pointer"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="px-5 py-4">
        <div className="flex items-center gap-4">
          {/* Main content */}
          <div className="flex-1 min-w-0">
            {/* Title */}
            <h4 className="text-sm font-semibold text-[#e8ecf4] leading-snug mb-1">
              {tender.tender_name_en || tender.tender_number}
            </h4>
            {/* Meta */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[#5a6a85]">
              {tender.entity_en && <span>{tender.entity_en}</span>}
              {tender.entity_en && tender.category_en && <span>·</span>}
              {tender.category_en && <span>{tender.category_en}</span>}
              {tender.fee && (
                <>
                  <span>·</span>
                  <span className="font-mono text-[#8896b0]">Fee: {tender.fee} OMR</span>
                </>
              )}
            </div>
            {/* Competitor chips */}
            {tender.tracked_competitors && tender.tracked_competitors.length > 0 && (
              <div className="flex items-center gap-1.5 mt-2">
                {tender.tracked_competitors.slice(0, 4).map((comp, i) => (
                  <span
                    key={i}
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: getCompetitorColor(comp.name || comp) }}
                    title={comp.name || comp}
                  />
                ))}
                {tender.tracked_competitors.length > 4 && (
                  <span className="text-[11px] text-[#5a6a85]">+{tender.tracked_competitors.length - 4}</span>
                )}
                <span className="text-[11px] text-[#5a6a85] ml-1">
                  {tender.num_bidders || 0} bidders · {tender.num_purchasers || 0} purchasers
                </span>
              </div>
            )}
          </div>

          {/* Right side: score + recommendation + closing */}
          <div className="flex items-center gap-4 flex-shrink-0">
            {/* Closing date */}
            {closingDate && (
              <span className={`text-xs font-mono ${
                closingCritical ? 'text-red-400' : closingUrgent ? 'text-amber-400' : 'text-[#5a6a85]'
              }`}>
                {closingCritical && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse mr-1" />
                )}
                {closingDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
              </span>
            )}

            {/* Recommendation pill */}
            <span className={`text-[10px] font-bold px-2.5 py-1 rounded border ${recConfig.cls}`}>
              {recConfig.label}
            </span>

            {/* Score bar + number */}
            <div className="flex items-center gap-2 w-28">
              <div className="flex-1 h-[6px] bg-[#1e2a42] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full bg-gradient-to-r ${barColor}`}
                  style={{ width: `${score}%` }}
                />
              </div>
              <span className="text-sm font-mono font-bold text-[#e8ecf4] w-7 text-right">{score}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-[#1e2a42] px-5 py-4 bg-[#0a0e17]">
          {/* AI reasoning */}
          {tender.reasoning && (
            <div className="mb-3">
              <p className="text-xs text-[#5a6a85] font-semibold mb-1">AI Analysis</p>
              <p className="text-sm text-[#8896b0] italic leading-relaxed">{tender.reasoning}</p>
            </div>
          )}

          {/* Competitor details */}
          {tender.tracked_competitors && tender.tracked_competitors.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-[#5a6a85] font-semibold mb-2">Competitors</p>
              <div className="flex flex-wrap gap-2">
                {tender.tracked_competitors.map((comp, i) => {
                  const name = comp.name || comp
                  const role = comp.role || 'DOCS'
                  const color = getCompetitorColor(name)
                  return (
                    <span
                      key={i}
                      className="text-xs font-semibold px-2.5 py-1 rounded-full border"
                      style={{ borderColor: color, color }}
                    >
                      {name} · {role}
                    </span>
                  )
                })}
              </div>
            </div>
          )}

          {/* Meta row */}
          <div className="flex flex-wrap gap-4 text-xs text-[#5a6a85]">
            <span>Tender: {tender.tender_number}</span>
            {tender.grade_en && <span>Grade: {tender.grade_en}</span>}
            {tender.is_retender && <span className="text-orange-400 font-semibold">RE-TENDER</span>}
          </div>
        </div>
      )}
    </div>
  )
}
