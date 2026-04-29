import { useState } from 'react'
import { api } from './utils/api'
import { useAPI } from './hooks/useAPI'
import MetricCards from './components/MetricCards'
import TenderTable from './components/TenderTable'
import NewsSection from './components/NewsSection'
import BriefingCard from './components/BriefingCard'
import TrendChart from './components/TrendChart'
import QueryBar from './components/QueryBar'
import CompetitiveIntel from './components/CompetitiveIntel'

export default function App() {
  const { data: stats, loading: statsLoading } = useAPI(api.getTenderStats, [])
  const { data: newsStats } = useAPI(api.getNewsStats, [])
  const { data: briefing } = useAPI(api.getLatestBriefing, [])
  const { data: trend } = useAPI(api.getTenderTrend, [])

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <nav className="sticky top-0 z-50 bg-slate-950 border-b border-slate-700/50 px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 28 28" fill="none" className="w-7 h-7">
            <rect width="28" height="28" rx="6" fill="#3B82F6" />
            <path d="M7 14h4l3-6 3 10 3-4h4" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-lg font-bold text-white tracking-tight">SCC Tender Intelligence</span>
        </div>
        <span className="text-xs text-slate-500">
          Powered by Zavia-ai
        </span>
      </nav>

      <main className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
        {/* NLP Query Bar */}
        <QueryBar />

        {/* Metric Cards */}
        <MetricCards stats={stats} newsStats={newsStats} loading={statsLoading} />

        {/* Briefing + Trend */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          <div className="lg:col-span-3">
            <BriefingCard briefing={briefing?.briefing} />
          </div>
          <div className="lg:col-span-2">
            <TrendChart data={trend} />
          </div>
        </div>

        {/* Competitive Intelligence */}
        <CompetitiveIntel />

        {/* SCC-Relevant Tenders */}
        <TenderTable title="SCC-Relevant Opportunities" sccOnly={true} />

        {/* All Tenders (collapsed by default) */}
        <CollapsibleSection title="All Tenders" defaultOpen={false}>
          <TenderTable title="" sccOnly={false} />
        </CollapsibleSection>

        {/* News */}
        <CollapsibleSection title="Market & Infrastructure News" defaultOpen={false}>
          <NewsSection />
        </CollapsibleSection>
      </main>

      <footer className="border-t border-slate-700/50 px-6 py-6 text-center text-xs text-slate-500 mt-8">
        Data sourced from etendering.tenderboard.gov.om · Oman news RSS · Google News
        <br />
        Powered by <strong className="text-slate-400">Zavia-ai</strong> · Intelligence refresh: daily
      </footer>
    </div>
  )
}

function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-6 py-4 bg-surface border border-slate-700/50 rounded-xl hover:bg-surface-hover transition-colors"
      >
        <span className={`text-xs text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`}>▶</span>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</h3>
      </button>
      {open && <div className="mt-4">{children}</div>}
    </div>
  )
}
