import { useState, useEffect } from 'react'
import { getTenderPipelineStatus, setPipelineStatus, removePipelineStatus } from '../utils/api'

const STATUSES = [
  {
    value: 'PURSUING',
    label: 'Pursuing',
    activeClass: 'bg-green-600 text-white border-green-600',
    inactiveClass: 'border-green-600 text-green-500 hover:bg-green-600/10',
  },
  {
    value: 'WATCHING',
    label: 'Watching',
    activeClass: 'bg-amber-500 text-white border-amber-500',
    inactiveClass: 'border-amber-500 text-amber-400 hover:bg-amber-500/10',
  },
  {
    value: 'PASS',
    label: 'Pass',
    activeClass: 'bg-slate-500 text-white border-slate-500',
    inactiveClass: 'border-slate-400 text-slate-400 hover:bg-slate-500/10',
  },
]

export default function PipelineStatusButton({ tenderNumber, tenderTitle, entity, closingDate }) {
  const [currentStatus, setCurrentStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getTenderPipelineStatus(tenderNumber).then(data => {
      if (!cancelled) {
        setCurrentStatus(data?.status ?? null)
        setLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [tenderNumber])

  const handleClick = async (statusValue) => {
    if (loading) return
    setLoading(true)
    try {
      if (currentStatus === statusValue) {
        // Toggle off — remove from pipeline
        await removePipelineStatus(tenderNumber)
        setCurrentStatus(null)
      } else {
        // Set new status
        const closingStr = closingDate
          ? (closingDate instanceof Date ? closingDate.toISOString().split('T')[0] : String(closingDate))
          : null
        await setPipelineStatus(tenderNumber, tenderTitle, entity, statusValue, closingStr)
        setCurrentStatus(statusValue)
      }
    } finally {
      setLoading(false)
    }
  }

  if (loading && currentStatus === null) {
    return (
      <div className="flex items-center gap-1 mt-2">
        <div className="h-6 w-20 bg-slate-700/50 rounded animate-pulse" />
        <div className="h-6 w-20 bg-slate-700/50 rounded animate-pulse" />
        <div className="h-6 w-14 bg-slate-700/50 rounded animate-pulse" />
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1 mt-2">
      {STATUSES.map(({ value, label, activeClass, inactiveClass }) => (
        <button
          key={value}
          onClick={() => handleClick(value)}
          disabled={loading}
          className={[
            'px-2 py-0.5 text-xs font-medium rounded border transition-colors',
            currentStatus === value ? activeClass : inactiveClass,
            loading ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
          ].join(' ')}
        >
          {loading && currentStatus === value ? '...' : label}
        </button>
      ))}
    </div>
  )
}
