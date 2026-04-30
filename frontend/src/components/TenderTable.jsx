import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import { api } from '../utils/api'

export default function TenderTable({ title }) {
  const [tenders, setTenders] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [search, setSearch] = useState('')
  const [lang, setLang] = useState('en')
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('scc') // 'scc' | 'all' | 'sub'

  const sccOnly = tab === 'scc' ? true : tab === 'sub' ? undefined : undefined
  const subContract = tab === 'sub' ? true : undefined

  useEffect(() => {
    setLoading(true)
    api.getTenders({
      scc_only: tab === 'scc' ? true : undefined,
      sub_contract: tab === 'sub' ? true : undefined,
      search: search || undefined,
      page,
    })
      .then((res) => {
        setTenders(res.tenders)
        setTotal(res.total)
        setPages(res.pages)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [tab, search, page])

  const getName = (t) => lang === 'en' ? (t.tender_name_en || t.tender_name_ar) : (t.tender_name_ar || t.tender_name_en)
  const getEntity = (t) => lang === 'en' ? (t.entity_en || t.entity_ar) : (t.entity_ar || t.entity_en)
  const getCat = (t) => lang === 'en' ? (t.category_en || t.category_ar) : (t.category_ar || t.category_en)
  const getGrade = (t) => lang === 'en' ? (t.grade_en || t.grade_ar) : (t.grade_ar || t.grade_en)

  const tabs = [
    { key: 'scc', label: 'SCC Relevant' },
    { key: 'all', label: 'All Tenders' },
    { key: 'sub', label: 'Sub-Contract' },
  ]

  return (
    <div className="bg-[#1E293B] border border-[#334155] rounded-xl p-6">
      {title && (
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider">{title}</h3>
          <span className="text-xs font-bold bg-blue-500 text-white px-3 py-0.5 rounded-full">{total}</span>
        </div>
      )}

      {/* Tab Pills */}
      <div className="flex gap-2 mb-4">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setPage(1) }}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-colors
              ${tab === t.key ? 'bg-blue-500 text-white' : 'bg-[#0F172A] border border-[#334155] text-[#8896b0] hover:text-[#e8ecf4]'}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex justify-between items-center mb-3 gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#5a6a85]" />
          <input
            type="text"
            placeholder="Search tenders..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="pl-9 pr-3 py-2 bg-[#0F172A] border border-[#334155] rounded-lg text-sm text-[#e8ecf4] placeholder:text-[#5a6a85] focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 w-72"
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[#8896b0]">{total} tenders</span>
          <div className="inline-flex border border-[#334155] rounded-full overflow-hidden text-xs font-semibold">
            <button
              onClick={() => setLang('en')}
              className={`px-3 py-1 transition-colors ${lang === 'en' ? 'bg-blue-500 text-white' : 'text-[#5a6a85]'}`}
            >EN</button>
            <button
              onClick={() => setLang('ar')}
              className={`px-3 py-1 transition-colors ${lang === 'ar' ? 'bg-blue-500 text-white' : 'text-[#5a6a85]'}`}
            >AR</button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-[#334155]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="bg-[#0F172A]">
              {['Tender No', 'Name', 'Entity', 'Category', 'Grade', 'Bid Closing'].map((h) => (
                <th key={h} className="px-3 py-2.5 text-left text-[11px] font-semibold text-[#5a6a85] uppercase tracking-wider border-b border-[#334155] whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[#5a6a85]">Loading...</td></tr>
            ) : tenders.length === 0 ? (
              <tr><td colSpan={6} className="px-3 py-8 text-center text-[#5a6a85]">No tenders found</td></tr>
            ) : (
              tenders.map((t) => (
                <tr
                  key={t.id}
                  className={`border-b border-[#334155]/50 hover:bg-blue-500/5 transition-colors
                    ${t.is_retender ? 'bg-amber-500/5 border-l-[3px] border-l-amber-500' : ''}`}
                >
                  <td className="px-3 py-2 text-[#e8ecf4] whitespace-nowrap font-mono text-xs">{t.tender_number}</td>
                  <td className="px-3 py-2 text-[#e8ecf4] max-w-[260px] truncate" title={getName(t)}>{getName(t)}</td>
                  <td className="px-3 py-2 text-[#8896b0]">{getEntity(t)}</td>
                  <td className="px-3 py-2 text-[#8896b0]">{getCat(t)}</td>
                  <td className="px-3 py-2 text-[#8896b0]">{getGrade(t)}</td>
                  <td className="px-3 py-2 text-[#e8ecf4] whitespace-nowrap">{t.bid_closing_date || '\u2014'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="px-3 py-1 border border-[#334155] rounded-md text-xs text-[#8896b0] hover:bg-[#253347] disabled:opacity-30"
          >\u2190 Prev</button>
          {[...Array(Math.min(pages, 7))].map((_, i) => (
            <button
              key={i}
              onClick={() => setPage(i + 1)}
              className={`px-3 py-1 border rounded-md text-xs transition-colors
                ${page === i + 1 ? 'bg-blue-500 text-white border-blue-500' : 'border-[#334155] text-[#8896b0] hover:bg-[#253347]'}`}
            >{i + 1}</button>
          ))}
          <button
            onClick={() => setPage(Math.min(pages, page + 1))}
            disabled={page >= pages}
            className="px-3 py-1 border border-[#334155] rounded-md text-xs text-[#8896b0] hover:bg-[#253347] disabled:opacity-30"
          >Next \u2192</button>
        </div>
      )}
    </div>
  )
}
