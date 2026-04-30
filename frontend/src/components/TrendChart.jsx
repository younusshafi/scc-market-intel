export default function TrendChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
        <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
          Tender Volume Trend
        </h3>
        <p className="text-sm text-[#5a6a85] italic">No trend data available yet.</p>
      </div>
    )
  }

  const maxVal = Math.max(...data.map(d => Math.max(d.total || 0, d.scc || 0)), 1)
  const chartHeight = 180
  const barWidth = Math.min(30, Math.floor(600 / data.length / 2.5))
  const gap = Math.min(20, Math.floor(600 / data.length / 4))
  const groupWidth = barWidth * 2 + gap
  const chartWidth = data.length * (groupWidth + gap * 2)

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
      <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
        Tender Volume Trend
      </h3>

      <div className="overflow-x-auto">
        <svg width={chartWidth + 40} height={chartHeight + 40} className="mx-auto">
          {/* Y-axis gridlines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct) => (
            <line
              key={pct}
              x1={30}
              y1={10 + chartHeight * (1 - pct)}
              x2={chartWidth + 30}
              y2={10 + chartHeight * (1 - pct)}
              stroke="#334155"
              strokeWidth="0.5"
              strokeDasharray={pct === 0 ? '' : '2,2'}
            />
          ))}

          {/* Bars */}
          {data.map((d, i) => {
            const x = 35 + i * (groupWidth + gap * 2)
            const totalH = (d.total / maxVal) * chartHeight
            const sccH = (d.scc / maxVal) * chartHeight

            return (
              <g key={d.month}>
                {/* All bar */}
                <rect
                  x={x}
                  y={10 + chartHeight - totalH}
                  width={barWidth}
                  height={totalH}
                  fill="#334155"
                  rx={3}
                />
                {/* SCC bar */}
                <rect
                  x={x + barWidth + 2}
                  y={10 + chartHeight - sccH}
                  width={barWidth}
                  height={sccH}
                  fill="#3b82f6"
                  rx={3}
                />
                {/* Month label */}
                <text
                  x={x + barWidth}
                  y={chartHeight + 28}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#94A3B8"
                >
                  {d.month}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-4">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-[#334155]" />
          <span className="text-xs text-[#94A3B8]">All Tenders</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-[#3b82f6]" />
          <span className="text-xs text-[#94A3B8]">SCC-Relevant</span>
        </div>
      </div>
    </div>
  )
}
