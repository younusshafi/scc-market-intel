import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const TYPE_CONFIG = {
  act_now: {
    label: 'ACT NOW',
    bg: 'bg-red-500/10',
    border: 'border-l-red-500',
    badge: 'bg-red-500 text-white',
    icon: (
      <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    hint: 'Review bid positioning',
  },
  new_activity: {
    label: 'NEW ACTIVITY',
    bg: 'bg-amber-500/10',
    border: 'border-l-amber-500',
    badge: 'bg-amber-500 text-white',
    icon: (
      <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      </svg>
    ),
    hint: 'Monitor competitor',
  },
  opportunity: {
    label: 'OPPORTUNITY',
    bg: 'bg-blue-500/10',
    border: 'border-l-blue-500',
    badge: 'bg-blue-500 text-white',
    icon: (
      <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    hint: 'Purchase docs',
  },
}

export default function PriorityActions() {
  const { data, loading } = useAPI(api.getPriorityActions, [])

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg h-20 animate-pulse" />
        ))}
      </div>
    )
  }

  const actions = data?.actions || []

  if (actions.length === 0) {
    return (
      <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-6 text-center">
        <p className="text-sm text-[#5a6a85]">No priority actions at this time</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider mb-3">
        Priority Actions
      </h3>
      {actions.map((action, i) => {
        const config = TYPE_CONFIG[action.type] || TYPE_CONFIG.opportunity
        return (
          <div
            key={i}
            className={`${config.bg} border border-[#1e2a42] border-l-4 ${config.border} rounded-lg px-5 py-4 hover:border-[#2a3a5c] transition-colors`}
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex-shrink-0">{config.icon}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${config.badge} tracking-wider`}>
                    {config.label}
                  </span>
                  {action.closing_date && (
                    <span className="text-xs font-mono text-red-400">
                      {new Date(action.closing_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                    </span>
                  )}
                </div>
                <p className="text-sm text-[#e8ecf4] leading-snug">{action.description}</p>
                <p className="text-xs text-[#5a6a85] mt-1">{config.hint}</p>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
