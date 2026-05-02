import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const SCC_CATEGORIES = ['Construction', 'Ports', 'Roads', 'Bridges', 'Pipeline', 'Electromechanical', 'Dams', 'Marine']

const GOVERNORATE_POSITIONS = {
  'Muscat': { x: 75, y: 45 },
  'Dhofar': { x: 30, y: 85 },
  'Musandam': { x: 85, y: 5 },
  'Al Buraimi': { x: 60, y: 20 },
  'Ad Dakhiliyah': { x: 55, y: 45 },
  'Al Batinah North': { x: 70, y: 25 },
  'Al Batinah South': { x: 65, y: 35 },
  'Ash Sharqiyah North': { x: 80, y: 55 },
  'Ash Sharqiyah South': { x: 85, y: 65 },
  'Ad Dhahirah': { x: 45, y: 35 },
  'Al Wusta': { x: 50, y: 65 },
}

function findPosition(governorate) {
  for (const [key, pos] of Object.entries(GOVERNORATE_POSITIONS)) {
    if (governorate.toLowerCase().includes(key.toLowerCase()) || key.toLowerCase().includes(governorate.toLowerCase())) {
      return pos
    }
  }
  return null
}

function PTLCPanel() {
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
  const maxCount = Math.max(...GOVERNORATES.map(g => g.count))

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        {STATS.map((stat, idx) => (
          <div key={idx} className="bg-[#0F172A] rounded-lg p-4 text-center">
            <p className="font-mono text-lg font-bold text-[#e8ecf4]">{stat.value}</p>
            <p className="text-xs text-[#5a6a85] mt-1">{stat.label}</p>
          </div>
        ))}
      </div>
      <div className="space-y-3">
        {GOVERNORATES.map((gov, idx) => (
          <div key={idx}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-[#e8ecf4]">{gov.name}</span>
              <span className="font-mono text-[#8896b0]">{gov.count}</span>
            </div>
            <div className="h-2 bg-[#0F172A] rounded-full overflow-hidden">
              <div className="h-full rounded-full bg-blue-500" style={{ width: `${(gov.count / maxCount) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function GeoPanel() {
  const { data, loading } = useAPI(api.getGeoDistribution, [])

  if (loading || !data || data.total_tenders === 0) {
    return <p className="text-sm text-[#5a6a85] italic">Loading geographic data...</p>
  }

  const regions = data.regions || []
  const activeRegions = regions.filter(r => r.count > 0)
  const maxCount = Math.max(...activeRegions.map(r => r.count), 1)

  const dots = activeRegions.map(r => {
    const pos = findPosition(r.governorate)
    if (!pos) return null
    const size = Math.max(8, Math.min(32, (r.count / maxCount) * 32))
    return { ...r, ...pos, size }
  }).filter(Boolean)

  return (
    <div>
      <div className="flex gap-4 text-xs text-[#5a6a85] mb-3">
        <span>{data.total_located || 0} located</span>
        <span>{data.national || 0} national</span>
      </div>
      <div className="relative w-full" style={{ paddingBottom: '60%' }}>
        <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full" style={{ overflow: 'visible' }}>
          <path d="M 40,10 L 90,5 L 92,15 L 85,25 L 80,35 L 85,50 L 90,65 L 85,75 L 70,80 L 50,85 L 30,90 L 20,80 L 25,65 L 35,50 L 40,35 L 45,20 Z"
            fill="#0F172A" stroke="#334155" strokeWidth="0.5" />
          {dots.map((dot) => (
            <g key={dot.governorate}>
              <circle cx={dot.x} cy={dot.y} r={dot.size / 4} fill="#3b82f6" opacity={0.6} />
              <circle cx={dot.x} cy={dot.y} r={dot.size / 8} fill="#3b82f6" opacity={0.9} />
              <text x={dot.x + dot.size / 3.5} y={dot.y + 1} fontSize="3.5" fill="#8896b0" dominantBaseline="middle">
                {dot.governorate} ({dot.count})
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="grid grid-cols-2 gap-2 mt-4">
        {activeRegions.map((r) => (
          <div key={r.governorate} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full bg-blue-500 opacity-70 flex-shrink-0" />
            <span className="text-[#8896b0] truncate">{r.governorate}</span>
            <span className="text-[#e8ecf4] font-mono ml-auto">{r.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function CompositionPanel({ stats }) {
  if (!stats) return <p className="text-sm text-[#5a6a85] italic">No data available.</p>

  return (
    <div className="space-y-3">
      {(stats.categories || []).map((cat) => {
        const pct = stats.total ? Math.round((cat.count / stats.total) * 100) : 0
        const isScc = SCC_CATEGORIES.some(s => cat.name?.toLowerCase().includes(s.toLowerCase()))
        return (
          <div key={cat.name}>
            <div className="flex justify-between items-center mb-1">
              <span className="text-sm text-[#e8ecf4]">{cat.name}</span>
              <span className="text-xs font-mono text-[#8896b0]">{cat.count} ({pct}%)</span>
            </div>
            <div className="h-2 bg-[#0F172A] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${isScc ? 'bg-blue-500' : 'bg-slate-600'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function MarketContext({ stats }) {
  const [subTab, setSubTab] = useState('pipeline')

  const tabs = [
    { id: 'pipeline', label: 'PTLC Pipeline' },
    { id: 'geographic', label: 'Geographic' },
    { id: 'composition', label: 'Composition' },
  ]

  return (
    <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-6">
      <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
        Market Context
      </h3>

      {/* Sub-tabs */}
      <div className="flex gap-1 mb-5 bg-[#0F172A] rounded-lg p-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setSubTab(tab.id)}
            className={`flex-1 text-xs font-semibold py-2 px-3 rounded-md transition-colors ${
              subTab === tab.id
                ? 'bg-[#1e2a42] text-[#e8ecf4]'
                : 'text-[#5a6a85] hover:text-[#8896b0]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {subTab === 'pipeline' && <PTLCPanel />}
      {subTab === 'geographic' && <GeoPanel />}
      {subTab === 'composition' && <CompositionPanel stats={stats} />}
    </div>
  )
}
