import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const THREAT_STYLES = {
  high: 'bg-red-600 text-white',
  medium: 'bg-amber-600 text-white',
  low: 'bg-green-600 text-white',
}

function ProfileCard({ profile }) {
  const threatStyle = THREAT_STYLES[profile.threat_level?.toLowerCase()] || THREAT_STYLES.low

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 hover:bg-[#253347] transition-colors">
      {/* Header: name + threat badge */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-bold text-[#e8ecf4]">{profile.competitor_name}</h4>
        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${threatStyle}`}>
          {profile.threat_level?.toUpperCase() || 'UNKNOWN'}
        </span>
      </div>

      {/* Behaviour summary */}
      {profile.behaviour_summary && (
        <p className="text-xs text-[#8896b0] mb-3 leading-relaxed">
          {profile.behaviour_summary}
        </p>
      )}

      {/* Strategy recommendation */}
      {profile.scc_strategy && (
        <div className="border-l-2 border-blue-500 bg-[#0F172A] rounded-r-lg px-3 py-2 mb-3">
          <p className="text-[11px] text-[#8896b0] italic leading-relaxed">
            <span className="text-blue-400 font-semibold not-italic mr-1">SCC Strategy:</span>
            {profile.scc_strategy}
          </p>
        </div>
      )}

      {/* Stats row */}
      <div className="flex items-center gap-4 mb-3">
        <div className="text-center">
          <span className="text-lg font-mono font-bold text-[#e8ecf4]">{profile.conversion_rate}%</span>
          <p className="text-[9px] text-[#5a6a85] uppercase">Conversion</p>
        </div>
        <div className="text-center">
          <span className="text-lg font-mono font-bold text-[#e8ecf4]">{profile.overlap_with_scc}</span>
          <p className="text-[9px] text-[#5a6a85] uppercase">SCC Overlap</p>
        </div>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {(profile.top_categories || []).map((cat, i) => (
          <span key={`cat-${i}`} className="text-[9px] font-semibold px-2 py-0.5 rounded-full border border-blue-500/40 text-blue-400">
            {cat}
          </span>
        ))}
        {(profile.top_governorates || []).map((gov, i) => (
          <span key={`gov-${i}`} className="text-[9px] font-semibold px-2 py-0.5 rounded-full border border-purple-500/40 text-purple-400">
            {gov}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function CompetitorProfiles() {
  const { data, loading, error, refetch } = useAPI(api.getCompetitorProfiles, [])
  const [building, setBuilding] = useState(false)

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
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">
            Competitor Behaviour Profiles
          </h2>
          {profiles.length > 0 && (
            <span className="text-[10px] font-semibold bg-red-600/20 text-red-400 px-2 py-0.5 rounded-full">
              {profiles.length}
            </span>
          )}
        </div>
        {profiles.length > 0 && (
          <button
            onClick={handleBuild}
            disabled={building}
            className="text-[10px] font-semibold text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
          >
            {building ? 'Building...' : 'Rebuild Profiles'}
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[#1E293B] border border-[#334155] rounded-xl p-5 animate-pulse">
              <div className="flex justify-between mb-3">
                <div className="h-4 w-24 bg-[#334155] rounded" />
                <div className="h-4 w-12 bg-[#334155] rounded-full" />
              </div>
              <div className="h-3 bg-[#334155] rounded w-full mb-2" />
              <div className="h-3 bg-[#334155] rounded w-3/4 mb-3" />
              <div className="h-10 bg-[#0F172A] rounded w-full" />
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#1E293B] border border-red-900/50 rounded-xl p-6 text-center">
          <p className="text-sm text-red-400 mb-2">Failed to load competitor profiles</p>
          <p className="text-xs text-[#5a6a85]">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && profiles.length === 0 && (
        <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-8 text-center">
          <p className="text-sm text-[#8896b0] mb-3">No competitor profiles built yet</p>
          <button
            onClick={handleBuild}
            disabled={building}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors"
          >
            {building ? 'Building Profiles...' : 'Build Profiles'}
          </button>
        </div>
      )}

      {/* Profile cards */}
      {!loading && !error && profiles.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {profiles.map((profile) => (
            <ProfileCard key={profile.id} profile={profile} />
          ))}
        </div>
      )}
    </div>
  )
}
