import React from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { Activity } from 'lucide-react'

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

function getColor(name) {
  const key = Object.keys(COMPETITOR_COLORS).find(k => name?.toLowerCase().includes(k.toLowerCase()))
  return key ? COMPETITOR_COLORS[key] : '#64748b'
}

function HorizontalBar({ value, max, color }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="w-full bg-[#0F172A] rounded-full h-2">
      <div className="h-2 rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  )
}

export default function CompetitorTimeline() {
  const { data, loading, error } = useAPI(() => api.getCompetitiveIntel(), [])

  if (loading) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="animate-pulse">
          <div className="bg-[#1E293B] rounded-xl h-64 border border-[#334155]" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-red-400 text-sm">
          Failed to load competitor data: {error}
        </div>
      </div>
    )
  }

  const activity = data?.activity_summary || []

  if (activity.length === 0) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-center text-[#5a6a85]">
          No competitor activity data available
        </div>
      </div>
    )
  }

  // Sort by total activity
  const sorted = [...activity].sort((a, b) => {
    const totalA = (a.docs || 0) + (a.bids || 0)
    const totalB = (b.docs || 0) + (b.bids || 0)
    return totalB - totalA
  })

  const maxActivity = Math.max(...sorted.map(c => (c.docs || 0) + (c.bids || 0)), 1)

  return (
    <div className="bg-[#0F172A] p-6">
      <h2 className="text-[#e8ecf4] font-bold text-xl mb-6 flex items-center gap-2">
        <Activity size={22} className="text-[#3b82f6]" /> Competitor Activity
      </h2>

      <div className="bg-[#1E293B] rounded-xl border border-[#334155] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#334155] text-[#5a6a85] text-xs">
              <th className="text-left p-4">Competitor</th>
              <th className="text-right p-4">Docs</th>
              <th className="text-right p-4">Bids</th>
              <th className="text-right p-4">Conv. %</th>
              <th className="text-right p-4">Max Bid</th>
              <th className="text-right p-4">W/D</th>
              <th className="p-4 w-32">Activity</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((comp, idx) => {
              const docs = comp.docs || 0
              const bids = comp.bids || 0
              const color = getColor(comp.name)
              const total = docs + bids

              return (
                <tr key={idx} className="border-b border-[#334155]/50 hover:bg-[#0F172A]/30">
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                      <span className="text-[#e8ecf4]">{comp.name}</span>
                    </div>
                  </td>
                  <td className="p-4 text-right font-mono text-[#e8ecf4]">{docs}</td>
                  <td className="p-4 text-right font-mono text-[#e8ecf4]">{bids}</td>
                  <td className="p-4 text-right font-mono text-[#e8ecf4]">{comp.conv || 0}%</td>
                  <td className="p-4 text-right font-mono text-[#e8ecf4]">
                    {comp.max_bid ? `OMR ${comp.max_bid.toLocaleString()}` : '-'}
                  </td>
                  <td className="p-4 text-right font-mono text-[#e8ecf4]">{comp.withdrawals || 0}</td>
                  <td className="p-4">
                    <HorizontalBar value={total} max={maxActivity} color={color} />
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
