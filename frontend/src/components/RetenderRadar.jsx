import React from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { RefreshCw, AlertTriangle } from 'lucide-react'

export default function RetenderRadar() {
  // The getTenders API may not support retenders_only param directly,
  // so we fetch all tenders and filter client-side for re-tendered ones
  const { data, loading, error } = useAPI(() => api.getTenders({ retenders_only: true }), [])

  if (loading) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#1E293B] rounded-xl h-28 border border-[#334155]" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-red-400 text-sm">
          Failed to load retender data: {error}
        </div>
      </div>
    )
  }

  // Handle both array response and paginated response
  const tenders = Array.isArray(data) ? data : data?.results || data?.tenders || []

  // Filter for retenders if the API didn't handle the param
  const retenders = tenders.filter(t =>
    t.is_retender || t.retender || t.tender_number?.toLowerCase().includes('re') ||
    t.name?.toLowerCase().includes('re-') || t.name?.toLowerCase().includes('retender')
  )

  return (
    <div className="bg-[#0F172A] p-6">
      <h2 className="text-[#e8ecf4] font-bold text-xl mb-6 flex items-center gap-2">
        <RefreshCw size={22} className="text-[#f97316]" /> Retender Radar
      </h2>

      {retenders.length === 0 ? (
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-center">
          <RefreshCw size={32} className="text-[#5a6a85] mx-auto mb-3" />
          <p className="text-[#5a6a85] text-sm">No re-tendered opportunities detected</p>
          <p className="text-[#5a6a85] text-xs mt-1">Re-floated tenders will appear here when identified</p>
        </div>
      ) : (
        <div className="space-y-3">
          {retenders.map((tender, idx) => (
            <div key={idx} className="bg-[#1E293B] rounded-xl border border-[#334155] p-6">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <p className="font-mono text-xs text-[#5a6a85] mb-1">{tender.tender_number || tender.reference}</p>
                  <h3 className="text-[#e8ecf4] font-bold text-sm">{tender.name || tender.tender_name || tender.title}</h3>
                  <p className="text-[#8896b0] text-xs mt-1">{tender.entity || tender.organization}</p>
                </div>
                {tender.fee && (
                  <span className="font-mono text-[#f59e0b] text-sm">OMR {tender.fee}</span>
                )}
              </div>

              {tender.bid_closing_date && (
                <p className="text-[#8896b0] text-xs mt-2">
                  Original closing: <span className="font-mono">{tender.bid_closing_date}</span>
                </p>
              )}

              <div className="mt-3 flex items-start gap-2 bg-amber-900/10 border border-amber-700/20 rounded-lg p-2.5">
                <AlertTriangle size={14} className="text-amber-400 mt-0.5 flex-shrink-0" />
                <p className="text-[#8896b0] text-xs">
                  Re-floated tender — likely scope revision or all bids rejected
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
