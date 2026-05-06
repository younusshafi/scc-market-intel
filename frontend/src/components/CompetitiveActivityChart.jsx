import { useState, useMemo } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Cell,
} from 'recharts'

const COMPETITOR_COLORS = {
  'Sarooj':          '#2563EB',
  'Galfar':          '#DC2626',
  'Strabag':         '#EA580C',
  'Al Tasnim':       '#16A34A',
  'L&T':             '#7C3AED',
  'Towell':          '#0891B2',
  'Hassan Allam':    '#CA8A04',
  'Arab Contractors':'#BE185D',
  'Ozkar':           '#6B7280',
}

const TRACKED = [
  'Galfar', 'Strabag', 'Al Tasnim', 'L&T',
  'Towell', 'Hassan Allam', 'Arab Contractors', 'Ozkar', 'Sarooj',
]

function fmtOMR(v) {
  if (!v || v === 0) return '—'
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B OMR`
  if (v >= 1_000_000)     return `${(v / 1_000_000).toFixed(1)}M OMR`
  if (v >= 1_000)         return `${Math.round(v / 1_000)}K OMR`
  return `${v.toLocaleString()} OMR`
}

function fmtNum(v) {
  if (v === null || v === undefined) return '—'
  return v.toLocaleString()
}

// Custom tooltip: shows all companies' values for that year, highlights hovered company
function ActivityTooltip({ active, payload, label, metric }) {
  if (!active || !payload || !payload.length) return null

  // Sort by value desc to build rank
  const sorted = [...payload].sort((a, b) => (b.value || 0) - (a.value || 0))
  const isOMR = metric === 'total_value_won' || metric === 'avg_bid_value'

  return (
    <div className="bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-2.5 text-xs shadow-xl max-w-[220px]">
      <p className="text-[#e8ecf4] font-semibold mb-2">{label}</p>
      {sorted.map((p, i) => (
        p.value > 0 && (
          <div key={p.dataKey} className="flex items-center justify-between gap-3 py-0.5">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: p.fill }} />
              <span style={{ color: p.fill }} className="font-medium">{p.dataKey}</span>
              <span className="text-[#5a6a85] text-[10px]">#{i + 1}</span>
            </span>
            <span className="text-[#e8ecf4] font-mono text-[10px]">
              {isOMR ? fmtOMR(p.value) : fmtNum(p.value)}
            </span>
          </div>
        )
      ))}
    </div>
  )
}

function SummaryCard({ label, value, sub, accent = 'border-l-blue-500' }) {
  return (
    <div className={`bg-[#0F172A] border border-[#1e2a42] border-l-4 ${accent} rounded-lg px-4 py-3`}>
      <p className="text-[10px] font-semibold text-[#5a6a85] uppercase tracking-wide">{label}</p>
      <p className="font-mono text-base font-bold text-[#e8ecf4] mt-1 truncate">{value}</p>
      {sub && <p className="text-[10px] text-[#5a6a85] mt-0.5">{sub}</p>}
    </div>
  )
}

const METRICS = [
  { key: 'contracts_won',  label: 'Contracts Won',  stacked: true  },
  { key: 'bids_submitted', label: 'Bids Submitted',  stacked: true  },
  { key: 'docs_purchased', label: 'Docs Purchased',  stacked: true  },
  { key: 'total_value_won',label: 'Value Won',       stacked: true  },
  { key: 'avg_bid_value',  label: 'Avg Bid',         stacked: false },
]

export default function CompetitiveActivityChart({ sccLostTo }) {
  const { data: raw, loading } = useAPI(api.getYearlyActivity, [])
  const [metric, setMetric] = useState('contracts_won')
  const [summaryYear, setSummaryYear] = useState('all')

  const { chartData, allYears, summary } = useMemo(() => {
    if (!raw?.data) return { chartData: [], allYears: [], summary: {} }

    const flatData = raw.data
    const allYears = (raw.years || []).filter(y => y >= 2019)

    // Pivot: year -> company -> row
    const yearMap = {}
    for (const row of flatData) {
      if (!yearMap[row.year]) yearMap[row.year] = {}
      yearMap[row.year][row.company] = row
    }

    // Chart data: one entry per year, company keys hold metric value
    const chartData = allYears.map(year => {
      const entry = { year: String(year) }
      TRACKED.forEach(company => {
        entry[company] = yearMap[year]?.[company]?.[metric] ?? 0
      })
      return entry
    })

    // Summary stats — filtered to selected year
    const rows = summaryYear === 'all'
      ? flatData
      : flatData.filter(r => r.year === parseInt(summaryYear))

    const totalValue   = rows.reduce((s, r) => s + (r.total_value_won || 0), 0)
    const sccRows      = rows.filter(r => r.company === 'Sarooj')
    const sccValue     = sccRows.reduce((s, r) => s + (r.total_value_won || 0), 0)
    const sccWins      = sccRows.reduce((s, r) => s + (r.contracts_won || 0), 0)
    const totalWins    = rows.reduce((s, r) => s + (r.contracts_won || 0), 0)
    const sccWinRate   = totalWins > 0 ? ((sccWins / totalWins) * 100).toFixed(1) : null

    // Toughest rival: use sccLostTo prop if available, else highest wins excl. SCC
    let toughestRival = sccLostTo?.[0]?.company ?? null
    if (!toughestRival) {
      const rivalTotals = {}
      rows.filter(r => r.company !== 'Sarooj').forEach(r => {
        rivalTotals[r.company] = (rivalTotals[r.company] || 0) + (r.contracts_won || 0)
      })
      toughestRival = Object.entries(rivalTotals).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null
    }

    return {
      chartData,
      allYears,
      summary: { totalValue, sccValue, sccWinRate, sccWins, totalWins, toughestRival },
    }
  }, [raw, metric, summaryYear, sccLostTo])

  const availableMetrics = raw?.has_docs_data
    ? METRICS
    : METRICS.filter(m => m.key !== 'docs_purchased')

  const currentMetric = availableMetrics.find(m => m.key === metric) ?? availableMetrics[0]
  const isOMR = metric === 'total_value_won' || metric === 'avg_bid_value'
  const isStacked = currentMetric?.stacked ?? true

  if (loading) {
    return (
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5 animate-pulse">
        <div className="h-4 w-64 bg-[#1e2a42] rounded mb-4" />
        <div className="grid grid-cols-4 gap-3 mb-5">
          {[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-[#0F172A] rounded-lg" />)}
        </div>
        <div className="h-[380px] bg-[#0F172A] rounded-lg" />
      </div>
    )
  }

  if (!raw) return null

  return (
    <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">

      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
          Competitive Activity — All Companies (2019–Present)
        </h4>
        <div className="flex items-center gap-1 bg-[#0F172A] rounded-lg p-0.5">
          {availableMetrics.map(m => (
            <button
              key={m.key}
              onClick={() => setMetric(m.key)}
              className={`px-2.5 py-1 text-[10px] font-semibold rounded transition-colors ${
                metric === m.key
                  ? 'bg-blue-600 text-white'
                  : 'text-[#5a6a85] hover:text-[#e8ecf4]'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary stat bar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 flex-1">
          <SummaryCard
            label="Total Market Value Awarded"
            value={fmtOMR(summary.totalValue)}
            accent="border-l-slate-500"
          />
          <SummaryCard
            label="SCC Total Won"
            value={fmtOMR(summary.sccValue)}
            accent="border-l-blue-500"
            sub={`${summary.sccWins ?? 0} contracts`}
          />
          <SummaryCard
            label="SCC Win Rate"
            value={summary.sccWinRate != null ? `${summary.sccWinRate}%` : '—'}
            accent="border-l-emerald-500"
            sub={`${summary.sccWins ?? 0} / ${summary.totalWins ?? 0} contracts`}
          />
          <SummaryCard
            label="SCC's Toughest Rival"
            value={summary.toughestRival ?? '—'}
            accent="border-l-red-500"
            sub={sccLostTo?.[0] ? `SCC lost ${sccLostTo[0].count} tenders to them` : 'By contracts won'}
          />
        </div>
        {/* Year filter for summary */}
        <div className="flex-shrink-0">
          <select
            value={summaryYear}
            onChange={e => setSummaryYear(e.target.value)}
            className="bg-[#0F172A] border border-[#334155] text-[#8896b0] text-[10px] rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
          >
            <option value="all">All years</option>
            {allYears.map(y => (
              <option key={y} value={String(y)}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={380}>
        <BarChart
          data={chartData}
          margin={{ top: 5, right: 15, left: 10, bottom: 5 }}
          barGap={isStacked ? 0 : 2}
          barCategoryGap={isStacked ? '20%' : '30%'}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2a42" vertical={false} />
          <XAxis
            dataKey="year"
            tick={{ fill: '#5a6a85', fontSize: 11, fontFamily: 'monospace' }}
            axisLine={{ stroke: '#1e2a42' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#5a6a85', fontSize: 10 }}
            axisLine={{ stroke: '#1e2a42' }}
            tickLine={false}
            tickFormatter={v => isOMR ? (v >= 1_000_000 ? `${(v / 1_000_000).toFixed(0)}M` : v >= 1_000 ? `${(v / 1000).toFixed(0)}K` : v) : v}
            width={isOMR ? 50 : 35}
          />
          <Tooltip
            content={<ActivityTooltip metric={metric} />}
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          />
          <Legend
            wrapperStyle={{ fontSize: 10, paddingTop: 12 }}
            formatter={(value) => (
              <span style={{ color: COMPETITOR_COLORS[value] || '#8896b0' }}>{value}</span>
            )}
          />
          {TRACKED.map(company => (
            <Bar
              key={company}
              dataKey={company}
              stackId={isStacked ? 'stack' : company}
              fill={COMPETITOR_COLORS[company] || '#6B7280'}
              stroke={company === 'Sarooj' ? '#fff' : 'transparent'}
              strokeWidth={company === 'Sarooj' ? 1 : 0}
              radius={
                isStacked
                  ? (company === 'Sarooj' ? [2, 2, 0, 0] : [0, 0, 0, 0])
                  : [2, 2, 0, 0]
              }
              opacity={0.85}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>

      {/* Chart mode note */}
      <p className="text-[10px] text-[#5a6a85] mt-2 text-right">
        {isStacked ? 'Stacked bars — total height = all companies combined' : 'Grouped bars — side-by-side per company'}
        {' · '}Source: awarded tender records
      </p>
    </div>
  )
}
