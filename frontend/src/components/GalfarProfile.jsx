// TODO: Replace hardcoded financials with API when available
import React from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { Building2, TrendingDown, AlertCircle } from 'lucide-react'

const FINANCIALS = {
  revenue: '$739M',
  revenueYear: '2024',
  netResult: '-RO 3.9M',
  netResultLabel: 'Net Loss',
  orderBacklog: 'OMR 405M+',
  marketCap: '$86.6M',
}

function StatBox({ label, value, negative }) {
  return (
    <div className="bg-[#0F172A] rounded-lg p-3">
      <p className="text-[#5a6a85] text-xs">{label}</p>
      <p className={`font-mono text-sm font-bold mt-1 ${negative ? 'text-red-400' : 'text-[#e8ecf4]'}`}>
        {value}
      </p>
    </div>
  )
}

export default function GalfarProfile() {
  const { data, loading } = useAPI(() => api.getCompetitiveIntel(), [])

  const galfarData = data?.activity_summary?.find(c => c.name?.toLowerCase().includes('galfar'))

  return (
    <div className="bg-[#0F172A] p-6">
      <h2 className="text-[#e8ecf4] font-bold text-xl mb-6 flex items-center gap-2">
        <Building2 size={22} className="text-[#ef4444]" />
        <span>Galfar Engineering</span>
        <span className="text-xs bg-red-900/30 text-red-400 px-2 py-0.5 rounded-full ml-2">Primary Competitor</span>
      </h2>

      <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6">
        {/* Financial Profile */}
        <h3 className="text-[#8896b0] text-xs uppercase tracking-wide mb-3">Financial Profile ({FINANCIALS.revenueYear})</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatBox label="Revenue" value={FINANCIALS.revenue} />
          <StatBox label={FINANCIALS.netResultLabel} value={FINANCIALS.netResult} negative />
          <StatBox label="Order Backlog" value={FINANCIALS.orderBacklog} />
          <StatBox label="Market Cap" value={FINANCIALS.marketCap} />
        </div>

        {/* Portal Activity */}
        <h3 className="text-[#8896b0] text-xs uppercase tracking-wide mb-3">Portal Activity</h3>
        {loading ? (
          <div className="animate-pulse bg-[#0F172A] rounded-lg h-16" />
        ) : galfarData ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
            <StatBox label="Docs Purchased" value={galfarData.docs || 0} />
            <StatBox label="Bids Submitted" value={galfarData.bids || 0} />
            <StatBox label="Conversion" value={`${galfarData.conv || 0}%`} />
          </div>
        ) : (
          <p className="text-[#5a6a85] text-sm mb-6">No portal activity data available</p>
        )}

        {/* Signal Callout */}
        <div className="bg-amber-900/10 border border-amber-700/30 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-amber-400 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[#e8ecf4] text-sm font-medium">Strategic Signal</p>
            <p className="text-[#8896b0] text-xs mt-1">
              2024 net loss of RO 3.9M signals potential resource constraints on new bids
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
