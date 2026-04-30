import React from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { Activity } from 'lucide-react'

const COMPETITOR_COLORS = {
  'Sarooj': '#2563EB',
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

function formatValue(val) {
  if (!val || val === 0) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(2)}M OMR`
  if (val >= 1000) return `${Math.round(val / 1000)}K OMR`
  return `${val.toLocaleString()} OMR`
}

function formatFee(fee) {
  if (!fee) return null
  if (typeof fee === 'string') return fee
  if (fee >= 1000000) return `${(fee / 1000000).toFixed(2)}M OMR`
  if (fee >= 1000) return `${Math.round(fee / 1000)}K OMR`
  return `${fee.toLocaleString()} OMR`
}

function LivePulse() {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500" />
      </span>
      <span className="text-red-400 text-xs font-semibold uppercase tracking-wide">LIVE</span>
    </span>
  )
}

function CompetitorPill({ name, role }) {
  const color = getCompetitorColor(name)
  if (role === 'BID') {
    return (
      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium mr-1.5 mb-1"
        style={{ backgroundColor: color, color: '#fff' }}>
        {name} &middot; BID
      </span>
    )
  }
  return (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium mr-1.5 mb-1 border"
      style={{ borderColor: color, color }}>
      {name} &middot; DOCS
    </span>
  )
}

function MajorProjectCard({ project }) {
  const borderColor = project.border_colour || '#334155'
  const bgClass = project.sarooj_present ? 'bg-blue-900/10' : 'bg-[#1E293B]'

  return (
    <div className={`${bgClass} rounded-lg border border-[#334155] p-3 overflow-hidden`}
      style={{ borderLeft: `4px solid ${borderColor}` }}>
      {/* Row 1: Name + Fee */}
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-[#e8ecf4] font-bold text-sm truncate flex-1">{project.name}</h4>
        {project.fee != null && (
          <span className="text-amber-400 font-mono text-xs whitespace-nowrap">{formatFee(project.fee)}</span>
        )}
      </div>
      {/* Row 2: Entity */}
      <p className="text-[#5a6a85] text-xs mt-0.5">{project.entity}</p>
      {/* Row 3: Category */}
      {project.category && (
        <span className="inline-block mt-1 text-[10px] bg-[#334155] text-[#8896b0] px-2 py-0.5 rounded-full">
          {project.category}
        </span>
      )}
      {/* Row 4: Purchasers + Bidders */}
      <p className="text-[#8896b0] text-xs mt-2">
        <span className="text-[#e8ecf4] font-bold">{project.num_purchasers || 0}</span> doc purchasers &middot;{' '}
        <span className="text-[#e8ecf4] font-bold">{project.num_bidders || 0}</span> bidders
      </p>
      {/* Row 5: Competitor pills */}
      <div className="mt-2 flex flex-wrap">
        {project.competitors && project.competitors.length > 0 ? (
          project.competitors.map((c, i) => (
            <CompetitorPill key={i} name={c.name} role={c.role || 'DOCS'} />
          ))
        ) : (
          <p className="text-[#5a6a85] text-xs italic">No tracked competitors</p>
        )}
      </div>
    </div>
  )
}

function HeadToHeadSection({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="mt-8">
      <h3 className="text-[#5a6a85] text-xs font-semibold uppercase tracking-wider mb-4">
        Head-to-Head: SCC vs Competitors
      </h3>
      <div className="space-y-4">
        {data.map((item, idx) => (
          <div key={idx} className="bg-[#0F172A] rounded-lg border border-[#334155] p-4 overflow-x-auto">
            <h4 className="text-[#e8ecf4] font-semibold text-sm mb-1">{item.project}</h4>
            <p className="text-[#5a6a85] text-xs font-mono mb-3">{item.tender_number}</p>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#5a6a85] border-b border-[#334155]">
                  <th className="text-left py-1.5 font-medium">Company</th>
                  <th className="text-right py-1.5 font-medium">Bid Value (OMR)</th>
                  <th className="text-right py-1.5 font-medium">Difference from SCC</th>
                </tr>
              </thead>
              <tbody>
                {(item.rows || []).map((row, i) => {
                  const isSCC = row.is_scc
                  const rowBg = isSCC ? 'bg-blue-900/30' : ''
                  return (
                    <tr key={i} className={rowBg}>
                      <td className="py-1.5 text-[#e8ecf4]">
                        <span className="inline-block w-2 h-2 rounded-full mr-2"
                          style={{ backgroundColor: getCompetitorColor(row.name) }} />
                        {row.name}
                      </td>
                      <td className="py-1.5 text-right font-mono text-[#e8ecf4]">
                        {formatValue(row.value)}
                      </td>
                      <td className={`py-1.5 text-right font-mono ${
                        isSCC ? 'text-[#8896b0]' :
                        row.diff_pct > 0 ? 'text-red-400' : 'text-amber-400'
                      }`}>
                        {isSCC ? 'Baseline' : (
                          row.diff != null ? `+${formatValue(Math.abs(row.diff)).replace(' OMR', '')} (+${row.diff_pct?.toFixed(1)}%)` : '--'
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  )
}

function LiveCompetitiveTenders({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="mt-8">
      <h3 className="text-[#5a6a85] text-xs font-semibold uppercase tracking-wider mb-4">
        Live Competitive Tenders
      </h3>
      <div className="space-y-3">
        {data.map((item, idx) => (
          <div key={idx} className="bg-[#0F172A] rounded-lg border border-[#334155] p-4">
            {/* Title row */}
            <div className="flex items-center justify-between mb-1">
              <h4 className="text-[#e8ecf4] font-semibold text-sm">{item.project}</h4>
              <LivePulse />
            </div>
            {/* Meta line */}
            <p className="text-[#8896b0] text-xs mb-2">
              <span className="text-[#e8ecf4] font-bold">{item.tracked_count || 0} of {item.total_purchasers || 0}</span>{' '}
              tracked competitors active &middot; {item.total_purchasers || 0} total purchasers
              {item.has_bids && <span className="text-amber-400 ml-2">&middot; Bids received</span>}
            </p>
            {/* Competitor pills */}
            {item.tracked && item.tracked.length > 0 && (
              <div className="flex flex-wrap mb-2">
                {item.tracked.map((c, i) => (
                  <span key={i} className="inline-block px-2 py-0.5 rounded-full text-xs font-medium mr-1.5 mb-1"
                    style={{ backgroundColor: getCompetitorColor(c.name), color: '#fff' }}>
                    {c.name}
                  </span>
                ))}
              </div>
            )}
            {/* Purchase timestamps */}
            {item.tracked && item.tracked.length > 0 && (
              <div className="space-y-0.5 mt-2">
                {item.tracked.map((c, i) => (
                  <p key={i} className="text-[#8896b0] text-xs flex items-center gap-1.5">
                    <span className="inline-block w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: getCompetitorColor(c.name) }} />
                    <span className="text-[#e8ecf4]">{c.name}:</span>
                    <span className="font-mono">{c.date || '--'}</span>
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ActivitySummaryTable({ data }) {
  if (!data || data.length === 0) return null

  const sorted = [...data].sort((a, b) => ((b.docs || 0) + (b.bids || 0)) - ((a.docs || 0) + (a.bids || 0)))

  return (
    <div className="mt-8">
      <h3 className="text-[#5a6a85] text-xs font-semibold uppercase tracking-wider mb-4">
        Competitor Activity Summary
      </h3>
      <div className="bg-[#0F172A] rounded-lg border border-[#334155] overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[#5a6a85] border-b border-[#334155]">
              <th className="text-left py-2 px-3 font-medium">Competitor</th>
              <th className="text-right py-2 px-3 font-medium">Docs Purchased</th>
              <th className="text-right py-2 px-3 font-medium">Tenders Bid</th>
              <th className="text-right py-2 px-3 font-medium">Conversion</th>
              <th className="text-right py-2 px-3 font-medium">Largest Bid</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => {
              const isSarooj = row.name?.toLowerCase().includes('sarooj') || row.name?.toLowerCase().includes('scc')
              const conv = row.conv || 0
              const convColor = conv >= 50 ? 'text-green-400' : conv >= 40 ? 'text-amber-400' : conv === 0 ? 'text-[#5a6a85]' : 'text-[#e8ecf4]'
              return (
                <tr key={i} className={isSarooj ? 'bg-blue-900/30' : ''}>
                  <td className="py-2 px-3 text-[#e8ecf4]">
                    <span className="inline-block w-2 h-2 rounded-full mr-2"
                      style={{ backgroundColor: getCompetitorColor(row.name) }} />
                    {row.name}
                  </td>
                  <td className="py-2 px-3 text-right font-mono text-[#e8ecf4]">{row.docs || 0}</td>
                  <td className="py-2 px-3 text-right font-mono text-[#e8ecf4]">{row.bids || 0}</td>
                  <td className={`py-2 px-3 text-right font-mono ${convColor}`}>{conv}%</td>
                  <td className="py-2 px-3 text-right font-mono text-[#e8ecf4]">
                    {row.max_bid ? formatValue(row.max_bid) : '--'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function CompetitiveBattlefield() {
  const { data, loading, error } = useAPI(() => api.getCompetitiveIntel(), [])

  if (loading) {
    return (
      <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6"
        style={{ borderTop: '3px solid', borderImage: 'linear-gradient(90deg, #ef4444, #f59e0b, #10b981) 1' }}>
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#0F172A] rounded-lg h-32 border border-[#334155]" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6"
        style={{ borderTop: '3px solid', borderImage: 'linear-gradient(90deg, #ef4444, #f59e0b, #10b981) 1' }}>
        <p className="text-red-400 text-sm">Failed to load competitive intelligence data.</p>
      </div>
    )
  }

  const majorProjects = data?.major_projects || []
  const headToHead = data?.head_to_head || []
  const liveCompetitive = data?.live_competitive || []
  const activitySummary = data?.activity_summary || []

  if (majorProjects.length === 0 && headToHead.length === 0 && liveCompetitive.length === 0 && activitySummary.length === 0) {
    return (
      <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6"
        style={{ borderTop: '3px solid', borderImage: 'linear-gradient(90deg, #ef4444, #f59e0b, #10b981) 1' }}>
        <p className="text-[#5a6a85] text-sm text-center">No competitive intelligence data available.</p>
      </div>
    )
  }

  return (
    <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6"
      style={{ borderTop: '3px solid', borderImage: 'linear-gradient(90deg, #ef4444, #f59e0b, #10b981) 1' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-[#e8ecf4] font-bold text-lg flex items-center gap-2">
          <Activity size={18} className="text-[#f59e0b]" />
          Competitive Intelligence
        </h2>
        <LivePulse />
      </div>

      {/* Major Project Tracker */}
      {majorProjects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {majorProjects.map((project, idx) => (
            <MajorProjectCard key={idx} project={project} />
          ))}
        </div>
      )}

      {/* Head-to-Head */}
      <HeadToHeadSection data={headToHead} />

      {/* Live Competitive Tenders */}
      <LiveCompetitiveTenders data={liveCompetitive} />

      {/* Competitor Activity Summary */}
      <ActivitySummaryTable data={activitySummary} />
    </div>
  )
}
