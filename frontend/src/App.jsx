import { useState, useRef } from 'react'
import { api } from './utils/api'
import { useAPI } from './hooks/useAPI'
import TabNavigation from './components/TabNavigation'
import MetricCards from './components/MetricCards'
import TenderTable from './components/TenderTable'
import NewsSection from './components/NewsSection'
import BriefingCard from './components/BriefingCard'
import TrendChart from './components/TrendChart'
import CompetitiveBattlefield from './components/CompetitiveBattlefield'
import EarlyWarnings from './components/EarlyWarnings'
import GalfarProfile from './components/GalfarProfile'
import GeoDistribution from './components/GeoDistribution'
import PTLCContext from './components/PTLCContext'
import RetenderRadar from './components/RetenderRadar'
import ScoredTenders from './components/ScoredTenders'
import NewsIntelligence from './components/NewsIntelligence'
import CompetitorProfiles from './components/CompetitorProfiles'
import EntityIntelligence from './components/EntityIntelligence'

const SCC_CATEGORIES = ['Construction', 'Ports', 'Roads', 'Bridges', 'Pipeline', 'Electromechanical', 'Dams', 'Marine']

export default function App() {
  const { data: stats, loading: statsLoading } = useAPI(api.getTenderStats, [])
  const { data: newsStats } = useAPI(api.getNewsStats, [])
  const { data: briefing } = useAPI(api.getLatestBriefing, [])
  const { data: trend } = useAPI(api.getTenderTrend, [])
  const { data: compIntel } = useAPI(api.getCompetitiveIntel, [])
  const { data: scoredData } = useAPI(api.getScoredTenders, [])
  const { data: newsIntel } = useAPI(api.getNewsIntelligence, [])
  const { data: profiles } = useAPI(api.getCompetitorProfiles, [])
  const { data: entityIntel } = useAPI(api.getEntityIntel, [])

  const [activeTab, setActiveTab] = useState('command-centre')
  const [newsOpen, setNewsOpen] = useState(false)
  const contentRef = useRef(null)

  function handleTabChange(tabId) {
    setActiveTab(tabId)
    contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Notification dots
  const notifications = {}
  const earlyWarnings = compIntel?.activity_summary?.filter(c => c.withdrawals > 0) || []
  if (earlyWarnings.length > 0 || compIntel?.major_projects?.some(p => p.sarooj_present)) {
    notifications['command-centre'] = true
  }
  const highPriorityNews = (newsIntel?.articles || []).filter(a => a.priority?.toLowerCase() === 'high')
  if (highPriorityNews.length > 0) {
    notifications['market-news'] = true
  }

  // Tab summary data
  const tabSummaries = {
    'competitive-intel': [
      `${compIntel?.activity_summary?.length || '—'} tracked competitors`,
      `${compIntel?.major_projects?.length || '—'} major projects`,
      `${compIntel?.live_competitive?.length || '—'} live competitive tenders`,
    ].join(' · '),
    'opportunities': [
      `${scoredData?.total || '—'} tenders scored`,
      `${(scoredData?.tenders || []).filter(t => t.recommendation === 'MUST_BID' || t.recommendation === 'STRONG_FIT').length || '—'} recommended`,
      `${stats?.retenders || '—'} re-tenders detected`,
    ].join(' · '),
    'market-news': [
      `${newsIntel?.total || '—'} analysed articles`,
      `${highPriorityNews.length || '—'} high priority`,
      `${entityIntel?.entities?.length || '—'} entity profiles`,
    ].join(' · '),
    'profiles': [
      `1 deep profile`,
      `${profiles?.profiles?.length || '—'} competitor assessments`,
    ].join(' · '),
  }

  return (
    <div className="min-h-screen bg-[#0F172A]">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-[#020617] border-b border-[#334155] px-8 py-3.5 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 28 28" fill="none" className="w-7 h-7">
            <rect width="28" height="28" rx="6" fill="#3B82F6" />
            <path d="M7 14h4l3-6 3 10 3-4h4" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <span className="text-lg font-bold text-[#e8ecf4] tracking-tight">Market Intelligence</span>
            <span className="text-[11px] text-[#5a6a85] ml-2 font-normal">Sarooj Construction Company</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-red-500 uppercase tracking-wider">
            <span className="w-[7px] h-[7px] rounded-full bg-red-500 animate-pulse" />
            LIVE
          </span>
          <span className="text-[12px] text-[#5a6a85]">
            Powered by <strong className="text-[#8896b0]">Zavia-ai</strong>
          </span>
          <div className="w-8 h-8 rounded-full bg-[#1E293B] border border-[#334155] flex items-center justify-center text-[11px] font-semibold text-[#8896b0]">
            JF
          </div>
        </div>
      </nav>

      {/* Tab Navigation */}
      <TabNavigation activeTab={activeTab} onTabChange={handleTabChange} notifications={notifications} />

      {/* Tab Summary Bar */}
      {activeTab !== 'command-centre' && tabSummaries[activeTab] && (
        <div className="bg-[#0a0e17] border-b border-[#1e2a42] px-8 py-2">
          <div className="max-w-[1400px] mx-auto">
            <p className="text-[11px] text-[#5a6a85] font-mono">{tabSummaries[activeTab]}</p>
          </div>
        </div>
      )}

      {/* Content */}
      <main ref={contentRef} className="max-w-[1400px] mx-auto px-8 py-6 space-y-6">

        {/* TAB 1: Command Centre */}
        {activeTab === 'command-centre' && (
          <>
            <BriefingCard briefing={briefing?.briefing} />
            <MetricCards stats={stats} newsStats={newsStats} loading={statsLoading} />
            <EarlyWarnings />
            <TrendChart data={trend} />
          </>
        )}

        {/* TAB 2: Competitive Intel */}
        {activeTab === 'competitive-intel' && (
          <>
            <CompetitiveBattlefield />
            <CompetitorProfiles />
          </>
        )}

        {/* TAB 3: Opportunities */}
        {activeTab === 'opportunities' && (
          <>
            <ScoredTenders />
            <TenderTable sccOnly={true} />
            <RetenderRadar />
          </>
        )}

        {/* TAB 4: Market & News */}
        {activeTab === 'market-news' && (
          <>
            <NewsIntelligence />
            <EntityIntelligence />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <PTLCContext />
              <GeoDistribution />
            </div>
            {/* Market Composition */}
            {stats && (
              <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
                <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider mb-4">Market Composition</h3>
                <div className="space-y-2.5">
                  {(stats.categories || []).map((cat) => {
                    const pct = stats.total ? Math.round((cat.count / stats.total) * 100) : 0
                    const isScc = SCC_CATEGORIES.some(s => cat.name?.toLowerCase().includes(s.toLowerCase()))
                    return (
                      <div key={cat.name}>
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-xs text-[#e8ecf4]">{cat.name}</span>
                          <span className="text-xs font-mono text-[#8896b0]">{cat.count} ({pct}%)</span>
                        </div>
                        <div className="h-2 bg-[#0F172A] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${isScc ? 'bg-blue-500' : 'bg-slate-500'}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
            {/* Raw News Feed */}
            <div>
              <button
                onClick={() => setNewsOpen(!newsOpen)}
                className="w-full flex items-center justify-between bg-[#1E293B] border border-[#334155] rounded-xl px-6 py-4 hover:bg-[#253347] transition-colors"
              >
                <span className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">Raw News Feed</span>
                <span className="text-[#5a6a85] text-lg">{newsOpen ? '\u2212' : '+'}</span>
              </button>
              {newsOpen && (
                <div className="mt-4">
                  <NewsSection />
                </div>
              )}
            </div>
          </>
        )}

        {/* TAB 5: Profiles */}
        {activeTab === 'profiles' && (
          <>
            <GalfarProfile />
            <CompetitorProfiles />
          </>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-[#334155] px-8 py-6 text-center text-[11px] text-[#5a6a85] mt-8">
        Data sourced from etendering.tenderboard.gov.om &middot; Oman news RSS &middot; Google News
        <br />
        Powered by <strong className="text-[#8896b0]">Zavia-ai</strong> &middot; Intelligence refresh: daily
      </footer>
    </div>
  )
}
