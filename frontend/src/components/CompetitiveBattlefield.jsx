import React from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { Swords, Users, FileText, Target } from 'lucide-react'

const COMPETITOR_COLORS = {
  'Sarooj': '#f59e0b',
  'Galfar': '#ef4444',
  'Strabag': '#3b82f6',
  'Al Tasnim': '#8b5cf6',
  'L&T': '#06b6d4',
  'Towell': '#10b981',
  'Hassan Allam': '#ec4899',
  'Arab Contractors': '#f97316',
  'Ozkar': '#64748b',
}

function getCompetitorColor(name) {
  const key = Object.keys(COMPETITOR_COLORS).find(k => name?.toLowerCase().includes(k.toLowerCase()))
  return key ? COMPETITOR_COLORS[key] : '#64748b'
}

function getBorderColor(bidderCount) {
  if (bidderCount >= 10) return '#ef4444'
  if (bidderCount >= 5) return '#f59e0b'
  return '#10b981'
}

function CompetitorPill({ name, type }) {
  const color = getCompetitorColor(name)
  if (type === 'BID') {
    return (
      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium mr-1 mb-1"
        style={{ backgroundColor: color, color: '#0F172A' }}>
        {name}
      </span>
    )
  }
  return (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium mr-1 mb-1 border"
      style={{ borderColor: color, color }}>
      {name}
    </span>
  )
}

function MajorProjectCard({ project }) {
  const bidders = project.bidders_count || project.bidders || 0
  const docs = project.doc_purchasers_count || project.doc_purchasers || 0
  const borderColor = getBorderColor(bidders)
  const saroojPresent = project.sarooj_present || project.competitors?.some(c => c.name?.toLowerCase().includes('sarooj'))
  const bgClass = saroojPresent ? 'bg-blue-900/20' : 'bg-[#1E293B]'

  return (
    <div className={`${bgClass} rounded-xl border border-[#334155] p-6 relative overflow-hidden`}
      style={{ borderLeft: `4px solid ${borderColor}` }}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="text-[#e8ecf4] font-bold text-sm">{project.name || project.tender_name}</h3>
          <p className="text-[#8896b0] text-xs mt-1">{project.entity}</p>
        </div>
        {project.category && (
          <span className="text-xs bg-[#334155] text-[#8896b0] px-2 py-0.5 rounded-full">{project.category}</span>
        )}
      </div>

      {project.fee && (
        <p className="text-[#f59e0b] font-mono text-sm mb-3">OMR {project.fee}</p>
      )}

      <div className="flex gap-4 text-xs text-[#8896b0] mb-3">
        <span className="flex items-center gap-1"><FileText size={12} /> {docs} docs</span>
        <span className="flex items-center gap-1"><Users size={12} /> {bidders} bidders</span>
      </div>

      {project.competitors && project.competitors.length > 0 && (
        <div className="flex flex-wrap">
          {project.competitors.map((c, i) => (
            <CompetitorPill key={i} name={c.name || c} type={c.type || c.status || 'DOCS'} />
          ))}
        </div>
      )}
    </div>
  )
}

function HeadToHead({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="mt-8">
      <h3 className="text-[#e8ecf4] font-bold text-lg mb-4 flex items-center gap-2">
        <Target size={18} className="text-[#f59e0b]" /> Head-to-Head
      </h3>
      <div className="space-y-4">
        {data.map((item, idx) => (
          <div key={idx} className="bg-[#1E293B] rounded-xl border border-[#334155] p-4 overflow-x-auto">
            <p className="text-[#e8ecf4] font-medium text-sm mb-3">{item.tender_name || item.project}</p>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#5a6a85]">
                  <th className="text-left py-1">Bidder</th>
                  <th className="text-right py-1">Bid Amount</th>
                  <th className="text-right py-1">vs Sarooj</th>
                </tr>
              </thead>
              <tbody>
                {(item.bids || item.bidders || []).map((bid, i) => {
                  const isSarooj = bid.name?.toLowerCase().includes('sarooj')
                  const diff = bid.difference || bid.diff_pct
                  return (
                    <tr key={i} className={isSarooj ? 'bg-blue-900/30' : ''}>
                      <td className="py-1 text-[#e8ecf4]">
                        <span className="inline-block w-2 h-2 rounded-full mr-2"
                          style={{ backgroundColor: getCompetitorColor(bid.name) }} />
                        {bid.name}
                      </td>
                      <td className="py-1 text-right font-mono text-[#e8ecf4]">
                        {bid.amount ? `OMR ${bid.amount.toLocaleString()}` : '-'}
                      </td>
                      <td className={`py-1 text-right font-mono ${
                        diff > 0 ? 'text-green-400' : diff < 0 ? 'text-red-400' : 'text-[#8896b0]'
                      }`}>
                        {isSarooj ? '—' : diff ? `${diff > 0 ? '+' : ''}${diff}%` : '-'}
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

function LiveCompetition({ data }) {
  if (!data || data.length === 0) return null

  return (
    <div className="mt-8">
      <h3 className="text-[#e8ecf4] font-bold text-lg mb-4 flex items-center gap-2">
        <Swords size={18} className="text-red-400" /> Live Competition
      </h3>
      <div className="grid gap-3">
        {data.map((item, idx) => (
          <div key={idx} className="bg-[#1E293B] rounded-xl border border-[#334155] p-4">
            <p className="text-[#e8ecf4] font-medium text-sm">{item.tender_name || item.name}</p>
            <p className="text-[#8896b0] text-xs mt-1">{item.entity}</p>
            <div className="flex flex-wrap mt-2">
              {(item.competitors || []).map((c, i) => (
                <CompetitorPill key={i} name={c.name || c} type="DOCS" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function CompetitiveBattlefield() {
  const { data, loading, error } = useAPI(() => api.getCompetitiveIntel(), [])

  if (loading) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#1E293B] rounded-xl h-40 border border-[#334155]" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-red-400 text-sm">
          Failed to load competitive data: {error}
        </div>
      </div>
    )
  }

  const majorProjects = data?.major_projects || []
  const headToHead = data?.head_to_head || []
  const liveCompetitive = data?.live_competitive || []

  if (majorProjects.length === 0 && headToHead.length === 0 && liveCompetitive.length === 0) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-center text-[#5a6a85]">
          No competitive battlefield data available
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[#0F172A] p-6">
      <h2 className="text-[#e8ecf4] font-bold text-xl mb-6 flex items-center gap-2">
        <Swords size={22} className="text-[#f59e0b]" /> Competitive Battlefield
      </h2>

      <div className="grid gap-4 md:grid-cols-2">
        {majorProjects.map((project, idx) => (
          <MajorProjectCard key={idx} project={project} />
        ))}
      </div>

      <HeadToHead data={headToHead} />
      <LiveCompetition data={liveCompetitive} />
    </div>
  )
}
