import { useState } from 'react'
import { useAPI } from '../hooks/useAPI'
import { api } from '../utils/api'

const COMP_COLORS = {
  'Sarooj': '#3B82F6', 'Galfar': '#EF4444', 'Strabag': '#F59E0B',
  'Al Tasnim': '#10B981', 'L&T': '#8B5CF6', 'Towell': '#EC4899',
  'Hassan Allam': '#F97316', 'Arab Contractors': '#06B6D4', 'Ozkar': '#84CC16',
}

export default function CompetitiveIntel() {
  const { data, loading } = useAPI(api.getCompetitiveIntel, [])
  const [tab, setTab] = useState('activity')

  if (loading) {
    return (
      <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Competitive Intelligence</h3>
        <p className="text-slate-500 text-sm">Loading...</p>
      </div>
    )
  }

  if (!data || data.total_probed === 0) {
    return (
      <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Competitive Intelligence</h3>
        <p className="text-slate-500 text-sm">No probe data available yet. Competitive intelligence will populate once tender detail probing is active.</p>
      </div>
    )
  }

  const tabs = [
    { key: 'activity', label: 'Competitor Activity', count: data.activity_summary?.length },
    { key: 'major', label: 'Major Projects', count: data.major_projects?.length },
    { key: 'h2h', label: 'Head-to-Head', count: data.head_to_head?.length },
    { key: 'live', label: 'Live Competition', count: data.live_competitive?.length },
  ]

  return (
    <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Competitive Intelligence</h3>
        <span className="text-xs text-slate-500">{data.total_probed} tenders probed</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 bg-slate-900 rounded-lg p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
              tab === t.key ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {t.label} {t.count > 0 && <span className="ml-1 opacity-70">({t.count})</span>}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'activity' && <ActivityTab data={data.activity_summary} />}
      {tab === 'major' && <MajorProjectsTab data={data.major_projects} />}
      {tab === 'h2h' && <HeadToHeadTab data={data.head_to_head} />}
      {tab === 'live' && <LiveCompTab data={data.live_competitive} />}
    </div>
  )
}


function ActivityTab({ data }) {
  if (!data?.length) return <Empty msg="No competitor activity detected yet." />
  const maxActivity = Math.max(...data.map(d => d.docs + d.bids), 1)

  return (
    <div className="space-y-2">
      {data.map((c) => (
        <div key={c.name} className="flex items-center gap-3 py-2">
          <span className="text-sm font-medium w-32 truncate" style={{ color: COMP_COLORS[c.name] || '#94A3B8' }}>
            {c.name}
          </span>
          <div className="flex-1 flex items-center gap-2">
            <div className="flex-1 bg-slate-800 rounded-full h-3 overflow-hidden flex">
              <div
                className="h-full rounded-l-full"
                style={{ width: `${(c.docs / maxActivity) * 100}%`, backgroundColor: COMP_COLORS[c.name] || '#94A3B8', opacity: 0.4 }}
                title={`${c.docs} docs purchased`}
              />
              <div
                className="h-full"
                style={{ width: `${(c.bids / maxActivity) * 100}%`, backgroundColor: COMP_COLORS[c.name] || '#94A3B8' }}
                title={`${c.bids} bids submitted`}
              />
            </div>
          </div>
          <div className="flex gap-4 text-xs text-slate-400 w-48 justify-end">
            <span title="Documents purchased">{c.docs} docs</span>
            <span title="Bids submitted">{c.bids} bids</span>
            <span title="Conversion rate">{c.conv}% conv</span>
          </div>
        </div>
      ))}
      <div className="flex gap-4 mt-3 text-[10px] text-slate-600">
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-slate-500 opacity-40 rounded" /> Docs purchased</span>
        <span className="flex items-center gap-1"><span className="w-3 h-2 bg-slate-500 rounded" /> Bids submitted</span>
      </div>
    </div>
  )
}


function MajorProjectsTab({ data }) {
  if (!data?.length) return <Empty msg="No major projects (fee >= 200 OMR) found in probed data." />

  return (
    <div className="space-y-3 max-h-[400px] overflow-y-auto">
      {data.map((p, i) => (
        <div key={i} className="bg-slate-900 rounded-lg p-4 border-l-4" style={{ borderColor: p.border_colour }}>
          <div className="flex justify-between items-start mb-2">
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-slate-200 truncate" title={p.name}>{p.name || p.tender_number}</h4>
              <p className="text-xs text-slate-500">{p.entity} &middot; {p.tender_number}</p>
            </div>
            <div className="text-right ml-3">
              <span className="text-sm font-bold text-white">{p.fee} OMR</span>
              <p className="text-[10px] text-slate-500">{p.num_bidders} bidders &middot; {p.num_purchasers} purchasers</p>
            </div>
          </div>
          {p.competitors?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {p.competitors.map((c, j) => (
                <span
                  key={j}
                  className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                    c.name === 'Sarooj' ? 'bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/50' :
                    c.role === 'BID' ? 'bg-slate-700 text-slate-300' : 'bg-slate-800 text-slate-500'
                  }`}
                >
                  {c.name} {c.role === 'BID' && c.value > 0 ? `(${c.value.toLocaleString()})` : `[${c.role}]`}
                </span>
              ))}
            </div>
          )}
          {p.sarooj_present && (
            <div className="mt-2 text-[10px] text-blue-400 font-medium">SCC participating</div>
          )}
        </div>
      ))}
    </div>
  )
}


function HeadToHeadTab({ data }) {
  if (!data?.length) return <Empty msg="No head-to-head bid comparisons available. Requires Sarooj and competitors to have bid on the same tender." />

  return (
    <div className="space-y-4 max-h-[400px] overflow-y-auto">
      {data.map((h, i) => (
        <div key={i} className="bg-slate-900 rounded-lg p-4">
          <h4 className="text-sm font-medium text-slate-200 truncate mb-1" title={h.project}>{h.project || h.tender_number}</h4>
          <p className="text-xs text-slate-500 mb-3">{h.tender_number}</p>
          <div className="space-y-1.5">
            {h.rows.map((r, j) => {
              const maxVal = Math.max(...h.rows.map(x => x.value), 1)
              return (
                <div key={j} className="flex items-center gap-2">
                  <span className={`text-xs w-28 truncate ${r.is_scc ? 'text-blue-400 font-bold' : 'text-slate-400'}`}>
                    {r.name}
                  </span>
                  <div className="flex-1 bg-slate-800 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(r.value / maxVal) * 100}%`,
                        backgroundColor: r.is_scc ? '#3B82F6' : COMP_COLORS[r.name] || '#64748B',
                      }}
                    />
                  </div>
                  <span className="text-xs text-slate-300 w-20 text-right">{r.value.toLocaleString()}</span>
                  {!r.is_scc && (
                    <span className={`text-[10px] w-16 text-right ${r.diff > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {r.diff > 0 ? '+' : ''}{r.diff_pct}%
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}


function LiveCompTab({ data }) {
  if (!data?.length) return <Empty msg="No tenders with 2+ tracked competitors purchasing documents." />

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700/50 max-h-[400px] overflow-y-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-900">
            <th className="px-3 py-2 text-left text-[11px] font-semibold text-slate-400 uppercase">Tender</th>
            <th className="px-3 py-2 text-left text-[11px] font-semibold text-slate-400 uppercase">Tracked Competitors</th>
            <th className="px-3 py-2 text-right text-[11px] font-semibold text-slate-400 uppercase">Total</th>
            <th className="px-3 py-2 text-center text-[11px] font-semibold text-slate-400 uppercase">Bids?</th>
          </tr>
        </thead>
        <tbody>
          {data.map((t, i) => (
            <tr key={i} className="border-b border-slate-700/30 hover:bg-blue-500/5">
              <td className="px-3 py-2">
                <div className="text-slate-200 text-xs truncate max-w-[200px]" title={t.project}>{t.project || t.tender_number}</div>
                <div className="text-[10px] text-slate-500">{t.tender_number}</div>
              </td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  {t.tracked.map((c, j) => (
                    <span key={j} className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800" style={{ color: COMP_COLORS[c.name] || '#94A3B8' }}>
                      {c.name}
                    </span>
                  ))}
                </div>
              </td>
              <td className="px-3 py-2 text-right text-slate-400 text-xs">{t.total_purchasers}</td>
              <td className="px-3 py-2 text-center text-xs">
                {t.has_bids ? <span className="text-amber-400">Yes</span> : <span className="text-slate-600">No</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


function Empty({ msg }) {
  return <p className="text-sm text-slate-500 py-4">{msg}</p>
}
