import React from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'
import { AlertTriangle, FileText, TrendingUp } from 'lucide-react'

export default function EarlyWarnings() {
  const { data, loading, error } = useAPI(() => api.getCompetitiveIntel(), [])

  if (loading) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#1E293B] rounded-xl h-16 border border-[#334155]" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-[#0F172A] p-6">
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-red-400 text-sm">
          Failed to load warnings: {error}
        </div>
      </div>
    )
  }

  const activitySummary = data?.activity_summary || []
  const majorProjects = data?.major_projects || []
  const totalProbed = data?.total_probed ?? majorProjects.length

  const warnings = []

  // Competitor withdrawal warnings
  activitySummary.forEach(comp => {
    if (comp.withdrawals > 0) {
      warnings.push({
        type: 'withdrawal',
        icon: <FileText size={16} className="text-amber-400" />,
        message: `${comp.name} purchased docs but did not bid on ${comp.withdrawals} tender${comp.withdrawals > 1 ? 's' : ''}`,
        severity: 'amber',
      })
    }
  })

  // Sarooj active warnings
  majorProjects.forEach(project => {
    if (project.sarooj_present) {
      warnings.push({
        type: 'sarooj_active',
        icon: <TrendingUp size={16} className="text-blue-400" />,
        message: `SCC is active on ${project.name || project.tender_name}`,
        severity: 'blue',
      })
    }
  })

  // No probe data
  if (totalProbed === 0) {
    warnings.push({
      type: 'no_data',
      icon: <AlertTriangle size={16} className="text-[#5a6a85]" />,
      message: 'No probe data available',
      severity: 'muted',
    })
  }

  const severityBorder = {
    amber: 'border-l-amber-400',
    blue: 'border-l-blue-400',
    red: 'border-l-red-400',
    muted: 'border-l-[#5a6a85]',
  }

  return (
    <div className="bg-[#0F172A] p-6">
      <h2 className="text-[#e8ecf4] font-bold text-xl mb-6 flex items-center gap-2">
        <AlertTriangle size={22} className="text-amber-400" /> Early Warnings
      </h2>

      {warnings.length === 0 ? (
        <div className="bg-[#1E293B] rounded-xl border border-[#334155] p-6 text-center text-[#5a6a85]">
          No warnings at this time
        </div>
      ) : (
        <div className="space-y-3">
          {warnings.map((w, idx) => (
            <div key={idx}
              className={`bg-[#1E293B] rounded-xl border border-[#334155] border-l-4 ${severityBorder[w.severity]} p-4 flex items-start gap-3`}>
              <div className="mt-0.5">{w.icon}</div>
              <p className="text-[#e8ecf4] text-sm">{w.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
