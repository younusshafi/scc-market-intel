import React, { useState, useEffect } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { Building2, AlertCircle, RefreshCw, Clock, TrendingUp, TrendingDown, BarChart3, ChevronDown, ChevronUp, Shield } from 'lucide-react'

// 2024 hardcoded fallback — shown only when scrape hasn't run yet
const FALLBACK_FINANCIALS = {
  net_profit_omr: -3900000,    // 2024 net loss RO 3.9M
  order_backlog_omr: 405000000,
  latest_quarter: '2024',
  scraped_at: null,
  _is_fallback: true,
}

function StatBox({ label, value, negative, subdued, positive }) {
  const color = negative
    ? 'text-red-400'
    : positive
    ? 'text-emerald-400'
    : subdued
    ? 'text-[#5a6a85]'
    : 'text-[#e8ecf4]'
  return (
    <div className="bg-[#0F172A] rounded-lg p-3">
      <p className="text-[#5a6a85] text-xs">{label}</p>
      <p className={`font-mono text-sm font-bold mt-1 ${color}`}>{value}</p>
    </div>
  )
}

function formatOMR(value, decimals = 1) {
  if (value == null) return '—'
  const abs = Math.abs(value)
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(decimals)}M`
  if (abs >= 1_000) return `${(value / 1_000).toFixed(0)}K`
  return value.toFixed(3)
}

export default function GalfarProfile() {
  const { data: intelData, loading: intelLoading } = useAPI(() => api.getCompetitiveIntel(), [])
  const [fin, setFin] = useState(null)
  const [finLoading, setFinLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [structured, setStructured] = useState(null)
  const [selectedPeriod, setSelectedPeriod] = useState(null)
  const [showTrends, setShowTrends] = useState(true)

  useEffect(() => {
    api.getGalfarFinancials()
      .then(setFin)
      .catch(() => setFin(FALLBACK_FINANCIALS))
      .finally(() => setFinLoading(false))
    api.getGalfarStructured()
      .then(d => {
        setStructured(d)
        if (d?.periods) {
          const keys = Object.keys(d.periods)
          setSelectedPeriod(keys[keys.length - 1])
        }
      })
      .catch(() => {})
  }, [])

  const galfarActivity = intelData?.activity_summary?.find(
    c => c.name?.toLowerCase().includes('galfar')
  )

  function handleRefresh() {
    setScraping(true)
    api.scrapeGalfarFinancials()
      .then(res => { if (res?.data) setFin(res.data) })
      .catch(() => {})
      .finally(() => setScraping(false))
  }

  const data = fin ?? FALLBACK_FINANCIALS
  const isFallback = data._is_fallback || !fin

  const lastUpdatedTs = data.file_last_modified || data.scraped_at
  const lastUpdated = lastUpdatedTs
    ? 'Last updated: ' + new Date(lastUpdatedTs).toLocaleString('en-GB', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : null

  const netProfit = data.net_profit_omr
  const isLoss = netProfit != null && netProfit < 0
  const profitLabel = isLoss ? 'Net Loss' : 'Net Profit'

  const profitChange = data.profit_change_pct
  const priorProfit = data.net_profit_prior_omr

  const contracts = data.news_intelligence?.recent_contract_wins ?? []
  const visibleContracts = contracts.slice(0, 5)
  const hiddenCount = contracts.length - 5

  return (
    <div className="bg-[#0F172A] p-6">
      <h2 className="text-[#e8ecf4] font-bold text-xl mb-6 flex items-center gap-2">
        <Building2 size={22} className="text-[#ef4444]" />
        <span>Galfar Engineering</span>
        <span className="text-xs bg-red-900/30 text-red-400 px-2 py-0.5 rounded-full ml-2">Primary Competitor</span>
        <span className="text-xs text-[#5a6a85] ml-1 font-mono">GECS · MSM</span>
      </h2>

      <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 space-y-6">

        {/* ── Market data row ── */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[#8896b0] text-xs uppercase tracking-wide">Live Market Data</h3>
            <div className="flex items-center gap-3">
              {lastUpdated && (
                <span className="flex items-center gap-1 text-[#5a6a85] text-[10px]">
                  <Clock size={10} />
                  {lastUpdated}
                </span>
              )}
              {isFallback && !finLoading && (
                <span className="text-xs text-amber-500">2024 fallback</span>
              )}
              <button
                onClick={handleRefresh}
                disabled={scraping}
                className="flex items-center gap-1 text-xs text-[#5a6a85] hover:text-[#e8ecf4] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                title="Refresh from MSX"
              >
                <RefreshCw size={12} className={scraping ? 'animate-spin' : ''} />
                {scraping ? 'Scraping MSX…' : 'Refresh'}
              </button>
            </div>
          </div>

          {finLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="animate-pulse bg-[#0F172A] rounded-lg h-14" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatBox
                label="Share Price"
                value={data.share_price_omr != null ? `OMR ${data.share_price_omr.toFixed(3)}` : '—'}
                subdued={data.share_price_omr == null}
              />
              <StatBox
                label="Market Cap"
                value={data.market_cap_omr != null ? `OMR ${formatOMR(data.market_cap_omr)}` : '—'}
                subdued={data.market_cap_omr == null}
              />
              <StatBox
                label="Day Range"
                value={
                  data.daily_high_omr != null
                    ? `${data.daily_low_omr?.toFixed(3)} – ${data.daily_high_omr?.toFixed(3)}`
                    : '—'
                }
                subdued={data.daily_high_omr == null}
              />
              <StatBox
                label="Volume"
                value={data.volume != null ? data.volume.toLocaleString() : '—'}
                subdued={data.volume == null}
              />
            </div>
          )}
        </div>

        {/* ── Financial performance ── */}
        <div>
          <h3 className="text-[#8896b0] text-xs uppercase tracking-wide mb-3">
            Financial Performance
            {data.latest_quarter && (
              <span className="ml-2 text-[#5a6a85] normal-case">({data.latest_quarter})</span>
            )}
          </h3>

          {finLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="animate-pulse bg-[#0F172A] rounded-lg h-14" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {/* Revenue — from annual/quarterly report */}
              <StatBox
                label={`Revenue (${data.financial_report_label ?? '2025 Annual'})`}
                value={data.revenue_omr != null ? `OMR ${formatOMR(data.revenue_omr)}` : isFallback ? '~$739M' : '—'}
                subdued={data.revenue_omr == null}
              />

              {/* Net profit — from latest quarterly disclosure */}
              <div className="bg-[#0F172A] rounded-lg p-3">
                <p className="text-[#5a6a85] text-xs">{profitLabel}</p>
                <p className={`font-mono text-sm font-bold mt-1 ${isLoss ? 'text-red-400' : 'text-emerald-400'}`}>
                  {netProfit != null ? `OMR ${formatOMR(Math.abs(netProfit))}` : isFallback ? 'RO -3.9M' : '—'}
                </p>
                {profitChange != null && !isFallback && (
                  <p className={`text-xs mt-0.5 flex items-center gap-0.5 ${profitChange >= 0 ? 'text-emerald-500' : 'text-red-400'}`}>
                    {profitChange >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                    {profitChange >= 0 ? '+' : ''}{profitChange.toFixed(0)}% vs prior period
                  </p>
                )}
              </div>

              {/* EPS or Order Backlog */}
              {data.eps != null ? (
                <StatBox
                  label="EPS"
                  value={`OMR ${data.eps.toFixed(3)}`}
                  negative={data.eps < 0}
                  positive={data.eps > 0}
                />
              ) : (
                <StatBox
                  label="Order Backlog"
                  value={data.order_backlog_omr != null ? `OMR ${formatOMR(data.order_backlog_omr)}` : isFallback ? 'OMR 405M+' : '—'}
                  subdued={data.order_backlog_omr == null && !isFallback}
                />
              )}
            </div>
          )}
        </div>

        {/* ── Order Backlog ── */}
        {!finLoading && data.order_backlog_omr != null && (
          <div>
            <h3 className="text-[#8896b0] text-xs uppercase tracking-wide mb-3">Order Backlog</h3>
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
              <p className="text-emerald-400 text-2xl font-bold font-mono">
                OMR {formatOMR(data.order_backlog_omr, 0)}
              </p>
              {data.news_intelligence?.backlog_sector_concentration && (
                <p className="text-[#94a3b8] text-xs mt-2">
                  Primary sectors: {data.news_intelligence.backlog_sector_concentration}
                </p>
              )}
            </div>
          </div>
        )}

        {/* ── Recent Contract Wins ── */}
        {!finLoading && contracts.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[#8896b0] text-xs uppercase tracking-wide">Recent Contract Wins</h3>
              <span className="text-[#5a6a85] text-xs">{contracts.length} awards tracked</span>
            </div>

            <div className="flex flex-col gap-3 max-h-[400px] overflow-y-auto pr-1">
              {visibleContracts.map((win, i) => {
                const project = win.project
                  ? (win.project.length > 100 ? win.project.substring(0, 100) + '…' : win.project)
                  : null
                const dateStr = win.date
                  ? new Date(win.date).toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' })
                  : null

                return (
                  <div
                    key={i}
                    className="bg-[#0F172A]/60 border border-[#334155]/50 rounded-lg p-3.5 hover:border-blue-500/40 hover:bg-[#0F172A]/80 transition-all"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[#e2e8f0] text-sm font-semibold">
                        {win.client || 'Client undisclosed'}
                      </span>
                      {win.value_omr != null && (
                        <span className="text-emerald-400 text-sm font-bold font-mono">
                          OMR {formatOMR(win.value_omr, 1)}
                        </span>
                      )}
                    </div>
                    {project && (
                      <p className="text-[#94a3b8] text-xs leading-relaxed mb-2">{project}</p>
                    )}
                    <div className="flex items-center justify-between">
                      {dateStr && (
                        <span className="text-[#94a3b8] text-xs">{dateStr}</span>
                      )}
                      {win.source && (
                        <span className="text-[11px] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">
                          {win.source}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {hiddenCount > 0 && (
              <p className="text-center text-[#5a6a85] text-xs mt-3">
                +{hiddenCount} more contract{hiddenCount !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        )}

        {/* ── Multi-Period Financial Trends ── */}
        {structured?.periods && (
          <div>
            <button
              onClick={() => setShowTrends(v => !v)}
              className="flex items-center gap-2 mb-3 w-full"
            >
              <BarChart3 size={14} className="text-blue-400" />
              <h3 className="text-[#8896b0] text-xs uppercase tracking-wide">
                Financial Trends — {Object.keys(structured.periods).length} Periods
              </h3>
              {showTrends ? <ChevronUp size={14} className="text-[#5a6a85] ml-auto" /> : <ChevronDown size={14} className="text-[#5a6a85] ml-auto" />}
            </button>

            {showTrends && (() => {
              const periodKeys = Object.keys(structured.periods).reverse()
              const periods = periodKeys.map(k => structured.periods[k])
              return (
                <div className="space-y-4">
                  {/* Trend table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-[#5a6a85] border-b border-[#334155]">
                          <th className="text-left py-2 pr-3 font-medium">Period</th>
                          <th className="text-right py-2 px-2 font-medium">Revenue</th>
                          <th className="text-right py-2 px-2 font-medium">Net Profit</th>
                          <th className="text-right py-2 px-2 font-medium">EBITDA</th>
                          <th className="text-right py-2 px-2 font-medium">Total Assets</th>
                          <th className="text-right py-2 px-2 font-medium">Equity</th>
                          <th className="text-center py-2 pl-2 font-medium">Threat</th>
                        </tr>
                      </thead>
                      <tbody>
                        {periods.map((p, i) => {
                          const rev = p.revenue_parent_omr ?? p.revenue_group_omr
                          const np = p.net_profit_parent_omr ?? p.net_profit_group_omr
                          const ebitda = p.ebitda_parent_omr ?? p.ebitda_group_omr
                          const assets = p.total_assets_parent_omr ?? p.total_assets_group_omr
                          const equity = p.total_equity_parent_omr ?? p.total_equity_group_omr
                          const threat = p.analysis?.threat_level
                          const isSelected = periodKeys[i] === selectedPeriod
                          const threatColor = threat === 'HIGH' ? 'bg-red-500/20 text-red-400' : threat === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400'

                          return (
                            <tr
                              key={p.period}
                              onClick={() => setSelectedPeriod(periodKeys[i])}
                              className={`border-b border-[#334155]/50 cursor-pointer transition-colors ${isSelected ? 'bg-blue-500/10' : 'hover:bg-[#0F172A]/60'}`}
                            >
                              <td className="py-2 pr-3">
                                <span className={`font-medium ${p.is_annual ? 'text-blue-400' : 'text-[#e8ecf4]'}`}>
                                  {p.label?.replace(' (Audited)', '').replace(' (Un-Audited)', '') ?? p.period}
                                </span>
                              </td>
                              <td className="text-right py-2 px-2 font-mono text-[#e8ecf4]">{rev != null ? formatOMR(rev) : '—'}</td>
                              <td className={`text-right py-2 px-2 font-mono ${np != null && np < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                                {np != null ? formatOMR(np) : '—'}
                              </td>
                              <td className={`text-right py-2 px-2 font-mono ${ebitda != null && ebitda < 0 ? 'text-red-400' : 'text-[#e8ecf4]'}`}>
                                {ebitda != null ? formatOMR(ebitda) : '—'}
                              </td>
                              <td className="text-right py-2 px-2 font-mono text-[#e8ecf4]">{assets != null ? formatOMR(assets) : '—'}</td>
                              <td className="text-right py-2 px-2 font-mono text-[#e8ecf4]">{equity != null ? formatOMR(equity) : '—'}</td>
                              <td className="text-center py-2 pl-2">
                                {threat && (
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${threatColor}`}>{threat}</span>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Selected period AI analysis */}
                  {selectedPeriod && structured.periods[selectedPeriod]?.analysis && (() => {
                    const a = structured.periods[selectedPeriod].analysis
                    const p = structured.periods[selectedPeriod]
                    const threatColor = a.threat_level === 'HIGH' ? 'border-red-500/40 bg-red-500/5' : a.threat_level === 'MEDIUM' ? 'border-amber-500/40 bg-amber-500/5' : 'border-emerald-500/40 bg-emerald-500/5'
                    const threatText = a.threat_level === 'HIGH' ? 'text-red-400' : a.threat_level === 'MEDIUM' ? 'text-amber-400' : 'text-emerald-400'
                    return (
                      <div className={`rounded-lg border p-4 space-y-3 ${threatColor}`}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Shield size={14} className={threatText} />
                            <span className={`text-sm font-semibold ${threatText}`}>
                              {a.threat_level} THREAT — {p.label}
                            </span>
                          </div>
                          {a.pricing_expectation && a.pricing_expectation !== 'UNKNOWN' && (
                            <span className="text-[10px] bg-[#1E293B] text-[#8896b0] px-2 py-0.5 rounded">
                              Pricing: {a.pricing_expectation}
                            </span>
                          )}
                        </div>
                        <p className="text-[#94a3b8] text-xs leading-relaxed">{a.threat_rationale}</p>

                        {a.key_signals?.length > 0 && (
                          <div>
                            <p className="text-[#5a6a85] text-[10px] uppercase tracking-wide mb-1">Key Signals</p>
                            <ul className="space-y-1">
                              {a.key_signals.map((s, i) => (
                                <li key={i} className="text-[#8896b0] text-xs flex gap-1.5">
                                  <span className="text-blue-400 flex-shrink-0">-</span>
                                  <span>{s}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                          {a.scc_implication && (
                            <div>
                              <p className="text-[#5a6a85] text-[10px] uppercase tracking-wide mb-1">SCC Implication</p>
                              <p className="text-[#94a3b8] text-xs">{a.scc_implication}</p>
                            </div>
                          )}
                          {a.bid_watch && (
                            <div>
                              <p className="text-[#5a6a85] text-[10px] uppercase tracking-wide mb-1">Bid Watch</p>
                              <p className="text-[#94a3b8] text-xs">{a.bid_watch}</p>
                            </div>
                          )}
                          {a.capacity_assessment && (
                            <div>
                              <p className="text-[#5a6a85] text-[10px] uppercase tracking-wide mb-1">Capacity Assessment</p>
                              <p className="text-[#94a3b8] text-xs">{a.capacity_assessment}</p>
                            </div>
                          )}
                          {a.backlog_commentary && (
                            <div>
                              <p className="text-[#5a6a85] text-[10px] uppercase tracking-wide mb-1">Backlog Trend ({a.backlog_trend ?? '—'})</p>
                              <p className="text-[#94a3b8] text-xs">{a.backlog_commentary}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })()}
                </div>
              )
            })()}
          </div>
        )}

        {/* ── Portal Activity ── */}
        <div>
          <h3 className="text-[#8896b0] text-xs uppercase tracking-wide mb-3">Portal Activity</h3>
          {intelLoading ? (
            <div className="animate-pulse bg-[#0F172A] rounded-lg h-14" />
          ) : galfarActivity ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <StatBox label="Docs Purchased" value={galfarActivity.docs ?? 0} />
              <StatBox label="Bids Submitted" value={galfarActivity.bids ?? 0} />
              <StatBox label="Conversion" value={`${galfarActivity.conv ?? 0}%`} />
            </div>
          ) : (
            <p className="text-[#5a6a85] text-sm">No portal activity data available</p>
          )}
        </div>

        {/* ── Strategic signal ── */}
        <div className="bg-amber-900/10 border border-amber-700/30 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-amber-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[#e8ecf4] text-sm font-medium">Strategic Signal</p>
            <p className="text-[#8896b0] text-xs mt-1">
              {netProfit != null && netProfit < 0 && !isFallback
                ? `Net loss of OMR ${formatOMR(Math.abs(netProfit))} (${data.latest_quarter}) signals potential resource constraints on new bids`
                : netProfit != null && netProfit > 0 && !isFallback
                ? `Back to profit: OMR ${formatOMR(netProfit)} in ${data.latest_quarter} after 2024 net loss — monitoring for renewed bid aggression`
                : '2024 net loss of RO 3.9M signals potential resource constraints on new bids'
              }
            </p>
          </div>
        </div>

      </div>
    </div>
  )
}
