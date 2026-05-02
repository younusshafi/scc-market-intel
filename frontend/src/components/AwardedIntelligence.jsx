import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, BarChart, LineChart,
} from 'recharts'

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

const CATEGORY_COLORS = {
  PRICING: '#10B981',
  COMPETITION: '#EF4444',
  OPPORTUNITY: '#3B82F6',
  ENTITY: '#F59E0B',
  TREND: '#8B5CF6',
}

function formatValue(val) {
  if (!val || val === 0) return '--'
  if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
  if (val >= 1000) return `${Math.round(val / 1000)}K`
  return val.toLocaleString()
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-[#1e2a42] border border-[#334155] rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-[#e8ecf4] font-semibold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-[#8896b0]">
          <span style={{ color: p.color }}>{p.name}:</span>{' '}
          {typeof p.value === 'number' && p.value > 1000
            ? formatValue(p.value)
            : p.value}{p.unit || ''}
        </p>
      ))}
    </div>
  )
}

export default function AwardedIntelligence() {
  const { data: analytics, loading: analyticsLoading } = useAPI(api.getAwardedAnalytics, [])
  const { data: insights, loading: insightsLoading } = useAPI(api.getAwardedInsights, [])
  const { data: sccPerf } = useAPI(api.getSCCPerformance, [])
  const { data: stats } = useAPI(api.getAwardedStats, [])
  const [computing, setComputing] = useState(false)

  async function handleCompute() {
    setComputing(true)
    try {
      await api.computeAwardedAnalytics()
      window.location.reload()
    } catch (e) {
      console.error(e)
    }
    setComputing(false)
  }

  if (analyticsLoading && insightsLoading) {
    return (
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-6 animate-pulse">
        <div className="h-5 w-56 bg-[#1e2a42] rounded mb-4" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-20 bg-[#0F172A] rounded-lg" />)}
        </div>
      </div>
    )
  }

  const insightsList = insights?.insights || []
  const yearlyTrends = analytics?.yearly_trends || []
  const pricing = analytics?.pricing || {}
  const competitorDeep = analytics?.competitor_deep || {}

  // Build chart data from yearly trends (2016+)
  const chartData = yearlyTrends
    .filter(y => y.year >= 2016)
    .map(y => ({
      year: y.year,
      total_awards: y.total_awards,
      scc_wins: y.competitors?.Sarooj?.wins || 0,
      scc_bids: y.competitors?.Sarooj?.bids || 0,
      scc_win_rate: y.competitors?.Sarooj?.win_rate || 0,
      total_value: y.total_value,
      avg_bid: y.avg_winning_bid,
    }))

  // Small multiples data for 4 competitors
  const smallMultipleComps = ['Galfar', 'Al Tasnim', 'Strabag', 'Sarooj']
  const smallMultiplesData = smallMultipleComps.map(comp => ({
    name: comp,
    color: COMPETITOR_COLORS[comp],
    data: yearlyTrends
      .filter(y => y.year >= 2016)
      .map(y => ({
        year: y.year,
        win_rate: y.competitors?.[comp]?.win_rate || 0,
      })),
  }))

  return (
    <div className="space-y-5">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[#e8ecf4] uppercase tracking-wider">
          Award Intelligence
        </h3>
        {analytics?.computed_at && (
          <span className="text-[10px] text-[#5a6a85] font-mono">
            Computed: {new Date(analytics.computed_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* AI Strategic Insights */}
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
        <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
          AI Strategic Insights
        </h4>
        {insightsList.length > 0 ? (
          <div className="grid grid-cols-1 gap-3">
            {insightsList.map((ins, i) => (
              <div key={i} className="bg-[#0F172A] border border-[#1e2a42] rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="text-[10px] font-bold uppercase px-2 py-0.5 rounded"
                    style={{
                      backgroundColor: `${CATEGORY_COLORS[ins.category] || '#6B7280'}20`,
                      color: CATEGORY_COLORS[ins.category] || '#6B7280',
                    }}
                  >
                    {ins.category}
                  </span>
                  <span className="text-sm font-semibold text-[#e8ecf4]">{ins.title}</span>
                </div>
                <p className="text-xs text-[#8896b0] leading-relaxed mb-2">{ins.insight}</p>
                <div className="bg-[#111827] border border-[#1e2a42] rounded px-3 py-2">
                  <p className="text-xs text-[#10B981] font-medium">
                    <span className="text-[#5a6a85] mr-1">Action:</span> {ins.action}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-6">
            <p className="text-sm text-[#5a6a85] mb-3">
              No insights computed yet. Run analytics to generate AI strategic insights.
            </p>
            <button
              onClick={handleCompute}
              disabled={computing}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
            >
              {computing ? 'Computing...' : 'Compute Insights'}
            </button>
          </div>
        )}
      </div>

      {/* Yearly Awards Chart */}
      {chartData.length > 0 && (
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
          <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
            Yearly Construction Awards vs SCC Performance
          </h4>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2a42" />
              <XAxis
                dataKey="year"
                tick={{ fill: '#5a6a85', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
                axisLine={{ stroke: '#1e2a42' }}
              />
              <YAxis
                yAxisId="left"
                tick={{ fill: '#5a6a85', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
                axisLine={{ stroke: '#1e2a42' }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fill: '#5a6a85', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}
                axisLine={{ stroke: '#1e2a42' }}
                unit="%"
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 11, color: '#8896b0' }}
              />
              <Bar yAxisId="left" dataKey="total_awards" name="Total Awards" fill="#3b82f6" opacity={0.6} radius={[2, 2, 0, 0]} />
              <Bar yAxisId="left" dataKey="scc_wins" name="SCC Wins" fill="#f59e0b" radius={[2, 2, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="scc_win_rate" name="SCC Win Rate" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} unit="%" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Competitor Win Rates Over Time (small multiples) */}
      {smallMultiplesData.some(d => d.data.some(p => p.win_rate > 0)) && (
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
          <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
            Competitor Win Rate Trends
          </h4>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {smallMultiplesData.map(comp => (
              <div key={comp.name} className="bg-[#0F172A] rounded-lg p-3">
                <p className="text-xs font-semibold mb-2" style={{ color: comp.color }}>
                  {comp.name}
                  {competitorDeep[comp.name] && (
                    <span className="text-[#5a6a85] font-normal ml-1">
                      ({competitorDeep[comp.name].win_rate}%)
                    </span>
                  )}
                </p>
                <ResponsiveContainer width="100%" height={100}>
                  <LineChart data={comp.data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                    <XAxis dataKey="year" tick={{ fontSize: 9, fill: '#5a6a85' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 9, fill: '#5a6a85' }} axisLine={false} tickLine={false} unit="%" />
                    <Line type="monotone" dataKey="win_rate" stroke={comp.color} strokeWidth={1.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pricing Intelligence Panel */}
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
        <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
          Pricing Intelligence
        </h4>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="bg-[#0F172A] rounded-lg p-4 text-center">
            <p className="font-mono text-xl font-bold text-[#e8ecf4]">
              {pricing.lowest_bidder_wins_pct != null ? `${pricing.lowest_bidder_wins_pct}%` : '--'}
            </p>
            <p className="text-[10px] text-[#5a6a85] mt-1">Lowest Bidder Wins</p>
          </div>
          <div className="bg-[#0F172A] rounded-lg p-4 text-center">
            <p className="font-mono text-xl font-bold text-[#e8ecf4]">
              {pricing.avg_bid_spread_pct != null ? `${pricing.avg_bid_spread_pct}%` : '--'}
            </p>
            <p className="text-[10px] text-[#5a6a85] mt-1">Avg Bid Spread</p>
          </div>
          <div className="bg-[#0F172A] rounded-lg p-4 text-center">
            <p className="font-mono text-xl font-bold text-[#e8ecf4]">
              {sccPerf?.avg_bid_position != null ? `#${sccPerf.avg_bid_position}` : '--'}
            </p>
            <p className="text-[10px] text-[#5a6a85] mt-1">SCC Avg Position</p>
          </div>
          <div className="bg-[#0F172A] rounded-lg p-4 text-center">
            <p className="font-mono text-xl font-bold text-[#e8ecf4]">
              {sccPerf?.lowest_bidder_win_rate != null ? `${sccPerf.lowest_bidder_win_rate}%` : '--'}
            </p>
            <p className="text-[10px] text-[#5a6a85] mt-1">SCC Wins When Lowest</p>
          </div>
        </div>
      </div>

      {/* SCC Performance Summary */}
      {sccPerf && sccPerf.total_bids > 0 && (
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
          <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
            SCC Historical Performance
          </h4>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div className="bg-[#0F172A] rounded-lg p-4">
              <p className="font-mono text-lg font-bold text-[#e8ecf4]">
                {sccPerf.total_wins}/{sccPerf.total_bids}
              </p>
              <p className="text-[10px] text-[#5a6a85]">
                Wins/Bids ({sccPerf.win_rate}% win rate)
              </p>
            </div>
            <div className="bg-[#0F172A] rounded-lg p-4">
              <p className="font-mono text-lg font-bold text-[#e8ecf4]">
                {formatValue(sccPerf.total_value_won)} OMR
              </p>
              <p className="text-[10px] text-[#5a6a85]">Total Value Won</p>
            </div>
            <div className="bg-[#0F172A] rounded-lg p-4">
              <p className="font-mono text-lg font-bold text-[#e8ecf4]">
                {formatValue(sccPerf.avg_winning_bid)} OMR
              </p>
              <p className="text-[10px] text-[#5a6a85]">Avg Winning Bid</p>
            </div>
            <div className="bg-[#0F172A] rounded-lg p-4">
              <p className="font-mono text-lg font-bold text-[#e8ecf4]">
                {sccPerf.avg_gap_to_winner_pct != null ? `+${sccPerf.avg_gap_to_winner_pct}%` : '--'}
              </p>
              <p className="text-[10px] text-[#5a6a85]">Avg Gap to Winner</p>
            </div>
          </div>

          {/* Lost to breakdown */}
          {sccPerf.lost_to && sccPerf.lost_to.length > 0 && (
            <div className="bg-[#0F172A] rounded-lg p-4">
              <p className="text-xs text-[#5a6a85] mb-2 font-medium">Tenders Lost To:</p>
              <div className="flex flex-wrap gap-2">
                {sccPerf.lost_to.slice(0, 6).map((item, i) => (
                  <span key={i} className="inline-flex items-center gap-1 text-xs bg-[#111827] border border-[#1e2a42] rounded px-2 py-1">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COMPETITOR_COLORS[item.company] || '#6B7280' }} />
                    <span className="text-[#e8ecf4]">{item.company}</span>
                    <span className="text-[#5a6a85]">({item.count})</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Top Winners Table (enhanced) */}
      {stats?.top_winners && stats.top_winners.length > 0 && (
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5">
          <h4 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-3">
            Top Winners (Construction)
          </h4>
          <div className="bg-[#0F172A] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-[#5a6a85] border-b border-[#1e2a42]">
                  <th className="text-left py-2.5 px-4 font-medium">Competitor</th>
                  <th className="text-right py-2.5 px-4 font-medium">Wins</th>
                  <th className="text-right py-2.5 px-4 font-medium">Win Rate</th>
                  <th className="text-right py-2.5 px-4 font-medium">Avg Contract</th>
                  <th className="text-right py-2.5 px-4 font-medium">Total Value</th>
                </tr>
              </thead>
              <tbody>
                {stats.top_winners.map((w, i) => {
                  const deep = competitorDeep[w.company]
                  return (
                    <tr key={i} className="border-b border-[#1e2a42] last:border-0">
                      <td className="py-2.5 px-4 text-[#e8ecf4]">
                        <span className="inline-block w-2.5 h-2.5 rounded-full mr-2"
                          style={{ backgroundColor: COMPETITOR_COLORS[w.company] || '#6B7280' }} />
                        {w.company}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">{w.wins}</td>
                      <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">
                        {deep?.win_rate != null ? `${deep.win_rate}%` : '--'}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">
                        {deep?.avg_winning_bid ? `${formatValue(deep.avg_winning_bid)} OMR` : '--'}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-[#e8ecf4]">
                        {w.total_value ? `${formatValue(w.total_value)} OMR` : '--'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
