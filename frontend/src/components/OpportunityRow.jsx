import { useState } from 'react'
import { getCompetitorColor } from '../utils/colors'

function getScoreBarColor(score) {
  if (score >= 85) return 'from-green-500 to-emerald-400'
  if (score >= 70) return 'from-blue-500 to-blue-400'
  return 'from-amber-500 to-amber-400'
}

function getRecLabel(rec) {
  const map = {
    'MUST_BID':    { label: 'BID NOW',  cls: 'bg-green-500/20 text-green-400 border-green-500/40' },
    'STRONG_FIT':  { label: 'EVALUATE', cls: 'bg-blue-500/20 text-blue-400 border-blue-500/40' },
    'CONSIDER':    { label: 'EVALUATE', cls: 'bg-blue-500/20 text-blue-400 border-blue-500/40' },
    'WATCH':       { label: 'MONITOR',  cls: 'bg-amber-500/20 text-amber-400 border-amber-500/40' },
    'SKIP':        { label: 'MONITOR',  cls: 'bg-slate-500/20 text-slate-400 border-slate-500/40' },
  }
  return map[rec] || map['WATCH']
}

function CompetitorPills({ competitors }) {
  if (!competitors || competitors.length === 0) return null
  const visible = competitors.slice(0, 4)
  const extra = competitors.length - 4

  return (
    <div className="flex items-center gap-1 mt-2 flex-wrap">
      {visible.map((comp, i) => {
        const name = comp.name || comp
        const c = getCompetitorColor(name)
        return (
          <span
            key={i}
            title={name}
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${c.bg} ${c.text} border ${c.border}`}
          >
            {c.abbr}
          </span>
        )
      })}
      {extra > 0 && (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-500/20 text-slate-400 border border-slate-500/30">
          +{extra}
        </span>
      )}
    </div>
  )
}

export default function OpportunityRow({ tender }) {
  const [expanded, setExpanded] = useState(false)

  const score = tender.score || 0
  const recConfig = getRecLabel(tender.recommendation)
  const barColor = getScoreBarColor(score)

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
            <h4 className="text-sm font-semibold text-[#e8ecf4] leading-snug mb-1">
              {tender.tender_name_en || tender.tender_number}
            </h4>
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

            {/* Competitor pills */}
            {tender.tracked_competitors && tender.tracked_competitors.length > 0 && (
              <>
                <CompetitorPills competitors={tender.tracked_competitors} />
                <span className="text-[11px] text-[#5a6a85] mt-1 block">
                  {tender.num_bidders || 0} bidders · {tender.num_purchasers || 0} purchasers
                </span>
              </>
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
          {tender.reasoning && (
            <div className="mb-3">
              <p className="text-xs text-[#5a6a85] font-semibold mb-1">AI Analysis</p>
              <p className="text-sm text-[#8896b0] italic leading-relaxed">{tender.reasoning}</p>
            </div>
          )}

          {tender.tracked_competitors && tender.tracked_competitors.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-[#5a6a85] font-semibold mb-2">Competitors</p>
              <div className="flex flex-wrap gap-2">
                {tender.tracked_competitors.map((comp, i) => {
                  const name = comp.name || comp
                  const role = comp.role || 'DOCS'
                  const c = getCompetitorColor(name)
                  return (
                    <span
                      key={i}
                      className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${c.bg} ${c.text} ${c.border}`}
                    >
                      {name} · {role}
                    </span>
                  )
                })}
              </div>
            </div>
          )}

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
