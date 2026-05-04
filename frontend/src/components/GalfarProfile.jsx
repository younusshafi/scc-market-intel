import React, { useState, useEffect } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { Building2, AlertCircle, RefreshCw, Clock, TrendingUp, TrendingDown } from 'lucide-react'

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

  useEffect(() => {
    api.getGalfarFinancials()
      .then(setFin)
      .catch(() => setFin(FALLBACK_FINANCIALS))
      .finally(() => setFinLoading(false))
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

  const lastUpdated = data.scraped_at
    ? new Date(data.scraped_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : null

  const netProfit = data.net_profit_omr
  const isLoss = netProfit != null && netProfit < 0
  const profitLabel = isLoss ? 'Net Loss' : 'Net Profit'

  const profitChange = data.profit_change_pct
  const priorProfit = data.net_profit_prior_omr

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
                <span className="flex items-center gap-1 text-[#5a6a85] text-xs">
                  <Clock size={11} />
                  {lastUpdated}
                </span>
              )}
              {isFallback && !finLoading && (
                <span className="text-xs text-amber-500">2024 fallback</span>
              )}
              <button
                onClick={handleRefresh}
                disabled={scraping}
                className="flex items-center gap-1 text-xs text-[#5a6a85] hover:text-[#e8ecf4] transition-colors disabled:opacity-40"
                title="Refresh from MSX"
              >
                <RefreshCw size={12} className={scraping ? 'animate-spin' : ''} />
                {scraping ? 'Fetching…' : 'Refresh'}
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
