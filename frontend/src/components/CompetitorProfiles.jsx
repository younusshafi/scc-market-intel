import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const THREAT_STYLES = {
  high: 'bg-red-500 text-white',
  medium: 'bg-amber-500 text-white',
  low: 'bg-green-500 text-white',
}

function ProfileCard({ profile, expanded, onToggle }) {
  const threatStyle = THREAT_STYLES[profile.threat_level?.toLowerCase()] || THREAT_STYLES.low

  return (
    <div
      className={`bg-[#111827] border border-[#1e2a42] rounded-lg p-5 hover:border-[#2a3a5c] transition-all cursor-pointer ${
        expanded ? 'col-span-full' : 'min-w-[280px] max-w-[340px]'
      }`}
      onClick={onToggle}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-bold text-[#e8ecf4]">{profile.competitor_name}</h4>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${threatStyle}`}>
          {profile.threat_level?.toUpperCase()}
        </span>
      </div>

      {/* One-line summary */}
      <p className={`text-sm text-[#8896b0] leading-relaxed mb-3 ${expanded ? '' : 'line-clamp-2'}`}>
        {profile.behaviour_summary}
      </p>

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs">
        <span className="font-mono font-bold text-[#e8ecf4]">{profile.conversion_rate}%</span>
        <span className="text-[#5a6a85]">conversion</span>
        <span className="font-mono font-bold text-[#e8ecf4]">{profile.overlap_with_scc}</span>
        <span className="text-[#5a6a85]">SCC overlap</span>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-[#1e2a42]">
          {profile.scc_strategy && (
            <div className="border-l-2 border-blue-500 bg-[#0a0e17] rounded-r-lg px-4 py-3 mb-3">
              <p className="text-sm text-[#8896b0] italic">
                <span className="text-blue-400 font-semibold not-italic mr-1">Strategy:</span>
                {profile.scc_strategy}
              </p>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {(profile.top_categories || []).map((cat, i) => (
              <span key={`cat-${i}`} className="text-xs font-semibold px-2.5 py-1 rounded-full border border-blue-500/40 text-blue-400">
                {cat}
              </span>
            ))}
            {(profile.top_governorates || []).map((gov, i) => (
              <span key={`gov-${i}`} className="text-xs font-semibold px-2.5 py-1 rounded-full border border-purple-500/40 text-purple-400">
                {gov}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function CompetitorProfiles() {
  const { data, loading, error, refetch } = useAPI(api.getCompetitorProfiles, [])
  const [building, setBuilding] = useState(false)
  const [expandedId, setExpandedId] = useState(null)

  const profiles = data?.profiles || []

  async function handleBuild() {
    setBuilding(true)
    try {
      await api.buildCompetitorProfiles()
      await refetch()
    } catch (e) {
      console.error('Profile build failed:', e)
    } finally {
      setBuilding(false)
    }
  }

  return (
    <div className="mt-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold text-[#5a6a85] uppercase tracking-wider">
          Competitor Profiles
        </h3>
        {profiles.length > 0 && (
          <button
            onClick={handleBuild}
            disabled={building}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
          >
            {building ? 'Building...' : 'Rebuild'}
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#111827] border border-[#1e2a42] rounded-lg p-5 animate-pulse min-w-[280px]">
              <div className="h-5 w-24 bg-[#1e2a42] rounded mb-3" />
              <div className="h-4 w-full bg-[#1e2a42] rounded mb-2" />
              <div className="h-4 w-2/3 bg-[#1e2a42] rounded" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#111827] border border-red-900/50 rounded-lg p-6 text-center">
          <p className="text-sm text-red-400">Failed to load profiles</p>
        </div>
      )}

      {/* Empty */}
      {!loading && !error && profiles.length === 0 && (
        <div className="bg-[#111827] border border-[#1e2a42] rounded-lg p-8 text-center">
          <p className="text-sm text-[#5a6a85]">No profiles built yet</p>
          <button
            onClick={handleBuild}
            disabled={building}
            className="mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
          >
            {building ? 'Building...' : 'Build Profiles'}
          </button>
        </div>
      )}

      {/* Horizontal scrollable row */}
      {!loading && !error && profiles.length > 0 && (
        expandedId !== null ? (
          <ProfileCard
            profile={profiles.find(p => p.id === expandedId) || profiles[0]}
            expanded={true}
            onToggle={() => setExpandedId(null)}
          />
        ) : (
          <div className="flex gap-3 overflow-x-auto pb-2">
            {profiles.map((profile) => (
              <ProfileCard
                key={profile.id}
                profile={profile}
                expanded={false}
                onToggle={() => setExpandedId(profile.id)}
              />
            ))}
          </div>
        )
      )}
    </div>
  )
}
