import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Toast } from '../components/Toast'
import { CASES } from '../mock/cases'
import type { CaseId } from '../types'

function normalize(s: string) {
  return s.replace(/\s+/g, '').toLowerCase()
}

function guessCaseId(query: string): CaseId | null {
  const q = normalize(query)
  const found = CASES.find((c) => normalize(c.exampleQuery) === q || normalize(c.title) === q)
  return (found?.id as CaseId) ?? null
}

export function SearchHomePage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [toast, setToast] = useState<string | null>(null)

  const history = useMemo(() => CASES, [])

  const onSubmit = () => {
    const trimmed = query.trim()
    const caseId = trimmed ? guessCaseId(trimmed) : null
    if (!caseId) {
      setToast('mock 暂不支持自由输入：请选择一个历史体验（下方 3 个）')
      return
    }
    navigate(`/app/case/${caseId}`)
  }

  return (
    <div className="page">
      <div className="hero">
        <div className="heroTitle">你想做什么？</div>
        <div className="searchBox">
          <input
            className="searchInput"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="像谷歌一样输入（原型仅支持下方 3 条历史）"
            onKeyDown={(e) => {
              if (e.key === 'Enter') onSubmit()
            }}
          />
          <button className="btn" onClick={onSubmit} type="button">
            搜索
          </button>
        </div>
        <div className="muted">
          自由输入会提示不支持；点击历史体验即可走完整流程（mock）。
        </div>
      </div>

      <div className="sectionTitle">搜索历史（hard-code）</div>
      <div className="gridCards">
        {history.map((c) => (
          <button key={c.id} className="historyCard" type="button" onClick={() => navigate(`/app/case/${c.id}`)}>
            <div className="historyTitle">{c.exampleQuery}</div>
            <div className="muted">{c.title}</div>
            <div className="historyCta">点我体验 →</div>
          </button>
        ))}
      </div>

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
