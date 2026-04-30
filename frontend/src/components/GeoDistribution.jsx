import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

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

export default function GeoDistribution() {
  const { data, loading } = useAPI(api.getGeoDistribution, [])

  if (loading) {
    return (
      <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
        <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">Geographic Distribution</h3>
        <p className="text-[#5a6a85] text-sm">Loading...</p>
      </div>
    )
  }

  if (!data || data.total_tenders === 0) {
    return (
      <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
        <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">Geographic Distribution</h3>
        <p className="text-[#5a6a85] text-sm italic">No tender data available.</p>
      </div>
    )
  }

  const regions = data.regions || []
  const activeRegions = regions.filter(r => r.count > 0)
  const maxCount = Math.max(...activeRegions.map(r => r.count), 1)

  // Map dots with positions
  const dots = activeRegions.map(r => {
    const pos = findPosition(r.governorate)
    if (!pos) return null
    const size = Math.max(8, Math.min(32, (r.count / maxCount) * 32))
    return { ...r, ...pos, size }
  }).filter(Boolean)

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">Geographic Distribution</h3>
        <div className="flex gap-3 text-[10px] text-[#5a6a85]">
          <span>{data.total_located || 0} located</span>
          <span>{data.national || 0} national</span>
          <span>{data.unlocated || 0} unlocated</span>
        </div>
      </div>

      {/* SVG Map */}
      <div className="relative w-full" style={{ paddingBottom: '70%' }}>
        <svg
          viewBox="0 0 100 100"
          className="absolute inset-0 w-full h-full"
          style={{ overflow: 'visible' }}
        >
          {/* Background outline shape (simplified Oman silhouette) */}
          <path
            d="M 40,10 L 90,5 L 92,15 L 85,25 L 80,35 L 85,50 L 90,65 L 85,75 L 70,80 L 50,85 L 30,90 L 20,80 L 25,65 L 35,50 L 40,35 L 45,20 Z"
            fill="#0F172A"
            stroke="#334155"
            strokeWidth="0.5"
          />

          {/* Dots for each governorate */}
          {dots.map((dot) => (
            <g key={dot.governorate}>
              <circle
                cx={dot.x}
                cy={dot.y}
                r={dot.size / 4}
                fill="#3b82f6"
                opacity={0.6}
              />
              <circle
                cx={dot.x}
                cy={dot.y}
                r={dot.size / 8}
                fill="#3b82f6"
                opacity={0.9}
              />
              <text
                x={dot.x + dot.size / 3.5}
                y={dot.y + 1}
                fontSize="3"
                fill="#8896b0"
                dominantBaseline="middle"
              >
                {dot.governorate} ({dot.count})
              </text>
            </g>
          ))}
        </svg>
      </div>

      {/* Legend / Summary */}
      <div className="mt-4 pt-3 border-t border-[#334155]">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {activeRegions.map((r) => (
            <div key={r.governorate} className="flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full bg-blue-500 opacity-70 flex-shrink-0" />
              <span className="text-[#8896b0] truncate">{r.governorate}</span>
              <span className="text-[#e8ecf4] font-mono ml-auto">{r.count}</span>
            </div>
          ))}
        </div>
        {data.national > 0 && (
          <div className="flex items-center gap-2 text-xs mt-2 pt-2 border-t border-[#334155]/50">
            <span className="w-2 h-2 rounded-full bg-green-500 opacity-70 flex-shrink-0" />
            <span className="text-[#8896b0]">National / Multi-region</span>
            <span className="text-[#e8ecf4] font-mono ml-auto">{data.national}</span>
          </div>
        )}
      </div>
    </div>
  )
}
