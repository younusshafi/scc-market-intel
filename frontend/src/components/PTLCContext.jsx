// TODO: Wire to live API data when available
import React from 'react'
import { Globe, BarChart3, Info } from 'lucide-react'

const STATS = [
  { label: 'Total Pipeline', value: 'OMR 1.5B' },
  { label: 'Roads/Bridges/Dams', value: '58%' },
  { label: 'Planned Tenders', value: '10,000' },
]

const GOVERNORATES = [
  { name: 'Muscat', count: 413 },
  { name: 'S. Al Batinah', count: 129 },
  { name: 'N. Al Batinah', count: 101 },
  { name: 'Dhofar', count: 69 },
]

function HorizontalBar({ value, max }) {
  const pct = (value / max) * 100
  return (
    <div className="flex items-center gap-3 mb-2">
      <div className="w-full bg-[#0F172A] rounded-full h-2.5">
        <div className="h-2.5 rounded-full bg-[#3b82f6] transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function PTLCContext() {
  const maxCount = Math.max(...GOVERNORATES.map(g => g.count))

  return (
    <div className="bg-[#0F172A] p-6">
      <h2 className="text-[#e8ecf4] font-bold text-xl mb-6 flex items-center gap-2">
        <Globe size={22} className="text-[#3b82f6]" /> PTLC Market Context
      </h2>

      <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          {STATS.map((stat, idx) => (
            <div key={idx} className="bg-[#0F172A] rounded-lg p-4 text-center">
              <p className="font-mono text-lg font-bold text-[#e8ecf4]">{stat.value}</p>
              <p className="text-[#5a6a85] text-xs mt-1">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Governorate Breakdown */}
        <h3 className="text-[#8896b0] text-xs uppercase tracking-wide mb-4">Governorate Distribution</h3>
        <div className="space-y-3">
          {GOVERNORATES.map((gov, idx) => (
            <div key={idx}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-[#e8ecf4]">{gov.name}</span>
                <span className="font-mono text-[#8896b0]">{gov.count}</span>
              </div>
              <HorizontalBar value={gov.count} max={maxCount} />
            </div>
          ))}
        </div>

        {/* Positioning Note */}
        <div className="mt-6 border-l-4 border-[#3b82f6] bg-blue-900/10 rounded-r-lg p-4">
          <div className="flex items-start gap-2">
            <Info size={16} className="text-[#3b82f6] mt-0.5 flex-shrink-0" />
            <p className="text-[#e8ecf4] text-sm">
              SCC is positioned in the top 3 construction categories with Excellent/First grade eligibility
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
