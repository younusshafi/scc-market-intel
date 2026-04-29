import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import { api } from '../utils/api'

export default function TenderTable({ title, sccOnly = false }) {
  const [tenders, setTenders] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [search, setSearch] = useState('')
  const [lang, setLang] = useState('en')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getTenders({ scc_only: sccOnly || undefined, search: search || undefined, page })
      .then((res) => {
        setTenders(res.tenders)
        setTotal(res.total)
        setPages(res.pages)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [sccOnly, search, page])

  const getName = (t) => lang === 'en' ? (t.tender_name_en || t.tender_name_ar) : (t.tender_name_ar || t.tender_name_en)
  const getEntity = (t) => lang === 'en' ? (t.entity_en || t.entity_ar) : (t.entity_ar || t.entity_en)
  const getCat = (t) => lang === 'en' ? (t.category_en || t.category_ar) : (t.category_ar || t.category_en)
  const getGrade = (t) => lang === 'en' ? (t.grade_en || t.grade_ar) : (t.grade_ar || t.grade_en)
  const getType = (t) => lang === 'en' ? (t.tender_type_en || t.tender_type_ar) : (t.tender_type_ar || t.tender_type_en)

  return (
    <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
      {title && (
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</h3>
          <span className="text-xs font-bold bg-blue-500 text-white px-3 py-0.5 rounded-full">{total}</span>
        </div>
      )}

      {/* Filters */}
      <div className="flex justify-between items-center mb-3 gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search tenders..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="pl-9 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 w-72"
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">{total} tenders</span>
          <div className="inline-flex border border-slate-700 rounded-full overflow-hidden text-xs font-semibold">
            <button
              onClick={() => setLang('en')}
              className={`px-3 py-1 transition-colors ${lang === 'en' ? 'bg-blue-500 text-white' : 'text-slate-500'}`}
            >EN</button>
            <button
              onClick={() => setLang('ar')}
              className={`px-3 py-1 transition-colors ${lang === 'ar' ? 'bg-blue-500 text-white' : 'text-slate-500'}`}
            >AR</button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-700/50">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-900">
              {['Tender No', 'Name', 'Entity', 'Category', 'Grade', 'Type', 'Bid Closing'].map((h) => (
                <th key={h} className="px-3 py-2.5 text-left text-[11px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-700/50 whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-500">Loading...</td></tr>
            ) : tenders.length === 0 ? (
              <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-500">No tenders found</td></tr>
            ) : (
              tenders.map((t) => (
                <tr
                  key={t.id}
                  className={`border-b border-slate-700/30 hover:bg-blue-500/5 transition-colors
                    ${t.is_retender ? 'bg-amber-500/5 border-l-2 border-l-amber-500' : ''}`}
                >
                  <td className="px-3 py-2 text-slate-300 whitespace-nowrap">{t.tender_number}</td>
                  <td className="px-3 py-2 text-slate-200 max-w-[260px] truncate" title={getName(t)}>{getName(t)}</td>
                  <td className="px-3 py-2 text-slate-400">{getEntity(t)}</td>
                  <td className="px-3 py-2 text-slate-400">{getCat(t)}</td>
                  <td className="px-3 py-2 text-slate-400">{getGrade(t)}</td>
                  <td className="px-3 py-2 text-slate-400">{getType(t)}</td>
                  <td className="px-3 py-2 text-slate-300 whitespace-nowrap">{t.bid_closing_date || '—'}</td>
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
            className="px-3 py-1 border border-slate-700 rounded-md text-xs text-slate-400 hover:bg-surface-hover disabled:opacity-30"
          >← Prev</button>
          {[...Array(Math.min(pages, 7))].map((_, i) => (
            <button
              key={i}
              onClick={() => setPage(i + 1)}
              className={`px-3 py-1 border rounded-md text-xs transition-colors
                ${page === i + 1 ? 'bg-blue-500 text-white border-blue-500' : 'border-slate-700 text-slate-400 hover:bg-surface-hover'}`}
            >{i + 1}</button>
          ))}
          <button
            onClick={() => setPage(Math.min(pages, page + 1))}
            disabled={page >= pages}
            className="px-3 py-1 border border-slate-700 rounded-md text-xs text-slate-400 hover:bg-surface-hover disabled:opacity-30"
          >Next →</button>
        </div>
      )}
    </div>
  )
}
