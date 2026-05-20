import { useState, useEffect } from 'react'
import { getPipeline } from '../utils/api'

function daysUntil(dateStr) {
  if (!dateStr) return null
  const d = new Date(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.ceil((d - today) / (1000 * 60 * 60 * 24))
}

function DaysRemaining({ dateStr }) {
  const days = daysUntil(dateStr)
  if (days === null) return null
  const color = days <= 7 ? 'text-red-400' : days <= 14 ? 'text-amber-400' : 'text-green-400'
  const label = days < 0 ? 'Closed' : days === 0 ? 'Closes today' : `${days}d left`
  return <span className={`text-xs font-mono font-semibold ${color}`}>{label}</span>
}

export default function ActiveBids() {
  const [entries, setEntries] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getPipeline().then(data => {
      setEntries(data || [])
      setLoading(false)
    })
  }, [])

  if (loading) {
    return (
      <div className="bg-[#111827] border border-[#1e2a42] rounded-xl p-5">
        <div className="h-4 w-32 bg-slate-700/50 rounded animate-pulse mb-3" />
        <div className="space-y-2">
          {[1, 2].map(i => <div key={i} className="h-10 bg-slate-700/30 rounded animate-pulse" />)}
        </div>
      </div>
    )
  }

  const pursuing = (entries || []).filter(e => e.status === 'PURSUING')
  const watching = (entries || []).filter(e => e.status === 'WATCHING')
  const pass = (entries || []).filter(e => e.status === 'PASS')
  const total = (entries || []).length

  return (
    <div className="bg-[#111827] border border-[#1e2a42] rounded-xl p-5">
      <h2 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">
        Your Active Bids
      </h2>

      {total === 0 ? (
        <p className="text-sm text-[#5a6a85] italic">
          No active bids marked yet. Go to Opportunities to mark tenders you&apos;re pursuing.
        </p>
      ) : (
        <>
          {/* Count badges */}
          <div className="flex items-center gap-3 mb-4">
            <span className="px-2.5 py-1 rounded border bg-green-600/20 text-green-400 border-green-600/40 text-xs font-semibold">
              Pursuing ({pursuing.length})
            </span>
            <span className="px-2.5 py-1 rounded border bg-amber-500/20 text-amber-400 border-amber-500/40 text-xs font-semibold">
              Watching ({watching.length})
            </span>
            <span className="px-2.5 py-1 rounded border bg-slate-500/20 text-slate-400 border-slate-500/40 text-xs font-semibold">
              Pass ({pass.length})
            </span>
          </div>

          {/* Pursuing tenders list */}
          {pursuing.length === 0 ? (
            <p className="text-xs text-[#5a6a85] italic">No tenders marked as Pursuing yet.</p>
          ) : (
            <div className="space-y-2">
              {pursuing.map(entry => (
                <div key={entry.tender_number} className="flex items-start justify-between gap-4 py-2.5 px-3 bg-[#0a0e17] rounded-lg border border-[#1e2a42]">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#e8ecf4] truncate">
                      {entry.tender_title ? entry.tender_title.slice(0, 60) + (entry.tender_title.length > 60 ? '…' : '') : entry.tender_number}
                    </p>
                    {entry.entity && (
                      <p className="text-xs text-[#5a6a85] truncate mt-0.5">{entry.entity}</p>
                    )}
                  </div>
                  <div className="flex-shrink-0">
                    <DaysRemaining dateStr={entry.closing_date} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
