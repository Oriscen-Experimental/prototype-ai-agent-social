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
    if (!trimmed) {
      setToast('Type something to start, or pick a suggestion below.')
      return
    }
    const caseId = trimmed ? guessCaseId(trimmed) : null
    if (!caseId) {
      navigate(`/app/agent?q=${encodeURIComponent(trimmed)}`)
      return
    }
    navigate(`/app/case/${caseId}`)
  }

  return (
    <div className="page">
      <div className="hero">
        <div className="heroTitle">What do you want to do?</div>
        <div className="searchBox">
          <input
            className="searchInput"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type anything or try a suggestion below"
            onKeyDown={(e) => {
              if (e.key === 'Enter') onSubmit()
            }}
          />
          <button className="btn" onClick={onSubmit} type="button">
            Search
          </button>
        </div>
      </div>

      <div className="sectionTitle">Suggested queries</div>
      <div className="gridCards">
        {history.map((c) => (
          <button
            key={c.id}
            className="historyCard"
            type="button"
            onClick={() => {
              setQuery(c.exampleQuery)
              // Use setTimeout to ensure state is updated before submitting
              setTimeout(() => {
                const caseId = guessCaseId(c.exampleQuery)
                if (!caseId) {
                  navigate(`/app/agent?q=${encodeURIComponent(c.exampleQuery)}`)
                } else {
                  navigate(`/app/case/${caseId}`)
                }
              }, 0)
            }}
          >
            <div className="historyTitle">{c.exampleQuery}</div>
            <div className="muted">{c.title}</div>
            <div className="historyCta">Try this →</div>
          </button>
        ))}
      </div>

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
