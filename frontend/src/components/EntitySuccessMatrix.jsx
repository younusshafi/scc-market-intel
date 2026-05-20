import { useState } from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, CartesianGrid,
} from 'recharts'

// Entity data sourced from backend/data/competitive_intelligence.json (scc_entity_performance)
// win_rate is decimal (0.0–1.0), bids is SCC bid count at that entity
const ENTITY_DATA = [
  { name: 'Muscat Municipality', bids: 5, wins: 2, win_rate: 40 },
  { name: 'Ministry of Agricultural, Fisheries & Water', bids: 10, wins: 0, win_rate: 0 },
  { name: 'Ministry of Transport Comms & IT', bids: 16, wins: 2, win_rate: 12.5 },
  { name: 'Al Dhahira Governor Office', bids: 4, wins: 0, win_rate: 0 },
  { name: 'Buraimi Governor Office', bids: 2, wins: 1, win_rate: 50 },
  { name: 'South Al Batinah Governor Office', bids: 4, wins: 0, win_rate: 0 },
  { name: 'Al Dakhiliyah Governor Office', bids: 6, wins: 0, win_rate: 0 },
  { name: 'North Al Sharqiyah Governor Office', bids: 4, wins: 0, win_rate: 0 },
  { name: 'North Al Batinah Governor Office', bids: 2, wins: 0, win_rate: 0 },
  { name: 'Al Wusta Governor Office', bids: 1, wins: 0, win_rate: 0 },
  { name: 'Ministry of Housing & Urban Planning', bids: 3, wins: 0, win_rate: 0 },
  { name: 'SEZAD (Duqm)', bids: 5, wins: 0, win_rate: 0 },
  { name: 'South Sharqiyah Governor Office', bids: 4, wins: 0, win_rate: 0 },
  { name: 'Ministry of Agriculture & Fisheries', bids: 3, wins: 1, win_rate: 33.3 },
  { name: 'Office of Minister of State', bids: 4, wins: 0, win_rate: 0 },
  { name: 'OPAZ (Special Economic Zone)', bids: 4, wins: 0, win_rate: 0 },
  { name: 'Ministry of Health', bids: 1, wins: 0, win_rate: 0 },
  { name: 'Ministry of Transport & Communications', bids: 2, wins: 0, win_rate: 0 },
  { name: 'Public Establishment Industrial Estates', bids: 1, wins: 0, win_rate: 0 },
  { name: 'Ministry of Regional Municipalities', bids: 2, wins: 0, win_rate: 0 },
  { name: 'General Secretariat Cabinet', bids: 1, wins: 0, win_rate: 0 },
  { name: 'Ministry of Housing', bids: 5, wins: 1, win_rate: 20 },
  { name: 'Civil Service Pension Fund', bids: 1, wins: 0, win_rate: 0 },
]

// Quadrant thresholds
const WIN_RATE_THRESHOLD = 15  // x-axis divider (%)
const VOLUME_THRESHOLD = 4     // y-axis divider (SCC bid count)

function getQuadrant(win_rate, bids) {
  const highWin = win_rate >= WIN_RATE_THRESHOLD
  const highVol = bids >= VOLUME_THRESHOLD
  if (highWin && highVol) return { label: 'Priority Targets', color: '#10B981' }
  if (!highWin && highVol) return { label: 'High Opportunity', color: '#F59E0B' }
  if (highWin && !highVol) return { label: 'Strong but Niche', color: '#3B82F6' }
  return { label: 'Low Priority', color: '#475569' }
}

function MatrixTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  const q = getQuadrant(d.win_rate, d.bids)
  return (
    <div className="bg-[#1e2a42] border border-[#334155] rounded-lg px-3 py-2.5 text-xs shadow-xl max-w-[220px]">
      <p className="text-[#e8ecf4] font-semibold mb-1 leading-tight">{d.name}</p>
      <div className="space-y-0.5 text-[#8896b0]">
        <p>SCC Bids: <span className="text-[#e8ecf4] font-mono">{d.bids}</span></p>
        <p>SCC Wins: <span className="text-[#e8ecf4] font-mono">{d.wins}</span></p>
        <p>Win Rate: <span className="text-[#e8ecf4] font-mono">{d.win_rate}%</span></p>
      </div>
      <div className="mt-2 pt-1.5 border-t border-[#334155]">
        <span className="text-[10px] font-semibold" style={{ color: q.color }}>{q.label}</span>
      </div>
    </div>
  )
}

export default function EntitySuccessMatrix() {
  const [hoveredName, setHoveredName] = useState(null)

  // Map data to scatter points — add slight jitter for overlapping zeros
  const points = ENTITY_DATA.map((e, i) => ({
    ...e,
    x: e.win_rate + (Math.sin(i * 7.3) * 0.8),  // tiny jitter on zero clusters
    y: e.bids,
    z: Math.max(e.bids * 12, 60),  // dot size proportional to bid count
    quadrant: getQuadrant(e.win_rate, e.bids),
  }))

  return (
    <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
          Entity Success Matrix
        </h4>
        <span className="text-[10px] text-[#5a6a85]">{ENTITY_DATA.length} entities · {ENTITY_DATA.reduce((s, e) => s + e.bids, 0)} SCC bids</span>
      </div>
      <p className="text-[10px] text-[#475569] mb-4">
        X: SCC win rate · Y: SCC engagement volume · Dot size: bid count
      </p>

      <div className="relative">
        {/* Quadrant labels — positioned in corners */}
        <div className="absolute inset-0 pointer-events-none z-10" style={{ left: 60, right: 10, top: 5, bottom: 40 }}>
          <div className="relative w-full h-full">
            {/* Top-left: High Opportunity */}
            <span className="absolute top-1 left-1 text-[9px] font-semibold text-amber-500/50 uppercase tracking-wider">High Opportunity</span>
            {/* Top-right: Priority Targets */}
            <span className="absolute top-1 right-1 text-[9px] font-semibold text-emerald-500/50 uppercase tracking-wider">Priority Targets</span>
            {/* Bottom-left: Low Priority */}
            <span className="absolute bottom-1 left-1 text-[9px] font-semibold text-slate-500/50 uppercase tracking-wider">Low Priority</span>
            {/* Bottom-right: Strong but Niche */}
            <span className="absolute bottom-1 right-1 text-[9px] font-semibold text-blue-500/50 uppercase tracking-wider">Strong but Niche</span>
          </div>
        </div>

        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2a42" />
            <XAxis
              type="number"
              dataKey="x"
              name="Win Rate"
              domain={[-2, 58]}
              tick={{ fill: '#5a6a85', fontSize: 10 }}
              axisLine={{ stroke: '#1e2a42' }}
              tickLine={false}
              label={{ value: 'SCC Win Rate (%)', position: 'insideBottomRight', offset: -5, fill: '#475569', fontSize: 10 }}
              tickCount={7}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="SCC Bids"
              domain={[0, 20]}
              tick={{ fill: '#5a6a85', fontSize: 10 }}
              axisLine={{ stroke: '#1e2a42' }}
              tickLine={false}
              label={{ value: 'SCC Bids', angle: -90, position: 'insideLeft', offset: 10, fill: '#475569', fontSize: 10 }}
            />
            <ZAxis type="number" dataKey="z" range={[40, 300]} />
            <Tooltip content={<MatrixTooltip />} cursor={{ strokeDasharray: '3 3', stroke: '#334155' }} />

            {/* Quadrant divider lines */}
            <ReferenceLine
              x={WIN_RATE_THRESHOLD}
              stroke="#334155"
              strokeDasharray="4 4"
              strokeWidth={1}
            />
            <ReferenceLine
              y={VOLUME_THRESHOLD}
              stroke="#334155"
              strokeDasharray="4 4"
              strokeWidth={1}
            />

            <Scatter
              data={points}
              shape={(props) => {
                const { cx, cy, payload } = props
                const q = payload.quadrant
                const r = Math.sqrt(payload.z / Math.PI)
                const isHovered = hoveredName === payload.name
                return (
                  <g
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredName(payload.name)}
                    onMouseLeave={() => setHoveredName(null)}
                  >
                    <circle
                      cx={cx}
                      cy={cy}
                      r={Math.max(r, 5)}
                      fill={q.color}
                      fillOpacity={isHovered ? 0.9 : 0.5}
                      stroke={q.color}
                      strokeWidth={isHovered ? 2 : 1}
                      strokeOpacity={0.8}
                    />
                    {payload.bids >= 5 && (
                      <text
                        x={cx}
                        y={cy - Math.max(r, 5) - 4}
                        textAnchor="middle"
                        fill="#8896b0"
                        fontSize={9}
                        style={{ pointerEvents: 'none' }}
                      >
                        {payload.name.split(' ')[0]}
                      </text>
                    )}
                  </g>
                )
              }}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-3 justify-center">
        {[
          { label: 'Priority Targets', color: '#10B981' },
          { label: 'High Opportunity', color: '#F59E0B' },
          { label: 'Strong but Niche', color: '#3B82F6' },
          { label: 'Low Priority', color: '#475569' },
        ].map(q => (
          <span key={q.label} className="flex items-center gap-1.5 text-[10px] text-[#5a6a85]">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: q.color, opacity: 0.7 }} />
            {q.label}
          </span>
        ))}
      </div>
    </div>
  )
}
