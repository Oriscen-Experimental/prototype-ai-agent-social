import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

type ClientRow = { clientId: string; updatedAtMs: number; bytes: number; createdAtMs?: number }
type EventRow = {
  at_ms?: number
  type?: string
  sessionId?: string
  page?: string
  payload?: Record<string, unknown>
  userAgent?: string
}

const ADMIN_PW_KEY = 'agent_social_admin_password'

function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  const s = (raw ?? '').trim()
  return s.endsWith('/') ? s.slice(0, -1) : s
}

function fmtTime(ms: number | undefined) {
  if (!ms) return ''
  try {
    return new Date(ms).toLocaleString()
  } catch {
    return String(ms)
  }
}

function fmtBytes(n: number) {
  if (!Number.isFinite(n)) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function asString(v: unknown): string {
  if (typeof v === 'string') return v
  if (v == null) return ''
  try {
    return JSON.stringify(v)
  } catch {
    return String(v)
  }
}

function summarizeEvent(e: EventRow): string {
  const t = e.type ?? 'unknown'
  const p = e.payload ?? {}

  const text = typeof p.text === 'string' ? p.text : ''
  const query = typeof p.query === 'string' ? p.query : ''
  const profileName = typeof p.profileName === 'string' ? p.profileName : ''
  const profileId = typeof p.profileId === 'string' ? p.profileId : ''
  const groupTitle = typeof p.groupTitle === 'string' ? p.groupTitle : ''
  const groupId = typeof p.groupId === 'string' ? p.groupId : ''

  if (t === 'search_submit') {
    return `Search “${query}”`
  }
  if (t === 'search_suggestion_click') {
    return `Clicked suggestion “${query}”`
  }

  if (t === 'agent_message_send') {
    return `Typed “${text}”`
  }
  if (t === 'agent_form_submit') {
    const toolName = typeof p.toolName === 'string' ? p.toolName : ''
    return toolName ? `Submitted form (${toolName})` : 'Submitted form'
  }
  if (t === 'agent_profile_open') {
    if (profileName) return `Opened profile: ${profileName}`
    return profileId ? `Opened profile: ${profileId}` : 'Opened profile'
  }
  if (t === 'agent_group_open') {
    if (groupTitle) return `Opened activity: ${groupTitle}`
    return groupId ? `Opened activity: ${groupId}` : 'Opened activity'
  }
  if (t === 'agent_profile_chat') {
    if (profileName) return `Opened chat (${profileName})`
    return profileId ? `Opened chat (${profileId})` : 'Opened chat'
  }
  if (t === 'agent_group_join') {
    if (groupTitle) return `Clicked join (${groupTitle})`
    return groupId ? `Clicked join (${groupId})` : 'Clicked join'
  }

  if (t === 'chat_message_send') {
    const who = profileName || profileId
    return who ? `Sent message “${text}” → ${who}` : `Sent message “${text}”`
  }

  if (t === 'case_profile_open') {
    if (profileName) return `Opened profile: ${profileName}`
    return profileId ? `Opened profile: ${profileId}` : 'Opened profile'
  }
  if (t === 'case_group_open') {
    if (groupTitle) return `Opened activity: ${groupTitle}`
    return groupId ? `Opened activity: ${groupId}` : 'Opened activity'
  }
  if (t === 'case_profile_chat') {
    if (profileName) return `Opened chat (${profileName})`
    return profileId ? `Opened chat (${profileId})` : 'Opened chat'
  }
  if (t === 'case_group_join') {
    if (groupTitle) return `Clicked join (${groupTitle})`
    return groupId ? `Clicked join (${groupId})` : 'Clicked join'
  }
  if (t === 'case_match_submit') {
    return 'Clicked Match (generate matches)'
  }
  if (t === 'case_option_change') {
    const key = typeof p.key === 'string' ? p.key : ''
    const value = p.value
    return key ? `Selected: ${key} = ${asString(value)}` : 'Selected preference'
  }

  if (t.startsWith('onboarding_')) {
    if (t === 'onboarding_finish') {
      const name = typeof p.name === 'string' ? p.name : ''
      const city = typeof p.city === 'string' ? p.city : ''
      return name || city ? `Finished onboarding (${[name, city].filter(Boolean).join(' · ')})` : 'Finished onboarding'
    }
    return t.replace('onboarding_', 'onboarding: ')
  }

  if (t === 'label_share') {
    const tab = typeof p.tab === 'string' ? p.tab : ''
    const archetype = typeof p.archetype === 'string' ? p.archetype : ''
    const label =
      tab === 'warning' ? 'Warning Label' : tab === 'nutrition' ? 'Nutrition Facts' : tab === 'manual' ? 'User Manual' : tab || 'Label'
    return `Clicked Share (${label}${archetype ? ` · ${archetype}` : ''})`
  }

  return t
}

async function getJson<T>(path: string, adminPassword: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { 'X-Admin-Password': adminPassword },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ''}`)
  }
  return (await res.json()) as T
}

export function AdminPage() {
  const [pw, setPw] = useState(() => {
    try {
      return sessionStorage.getItem(ADMIN_PW_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [authedPw, setAuthedPw] = useState<string | null>(null)
  const [clients, setClients] = useState<ClientRow[]>([])
  const [selectedClientId, setSelectedClientId] = useState<string>('')
  const [events, setEvents] = useState<EventRow[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const [typeFilter, setTypeFilter] = useState('')
  const [q, setQ] = useState('')
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest')

  const filteredEvents = useMemo(() => {
    const qq = q.trim().toLowerCase()
    return events.filter((e) => {
      if (typeFilter && (e.type ?? '') !== typeFilter) return false
      if (!qq) return true
      const hay = JSON.stringify(e).toLowerCase()
      return hay.includes(qq)
    })
  }, [events, q, typeFilter])

  const types = useMemo(() => {
    const s = new Set<string>()
    for (const e of events) {
      if (typeof e.type === 'string' && e.type) s.add(e.type)
    }
    return Array.from(s).sort()
  }, [events])

  const countsByType = useMemo(() => {
    const out: Record<string, number> = {}
    for (const e of events) {
      const t = e.type || 'unknown'
      out[t] = (out[t] ?? 0) + 1
    }
    return Object.entries(out).sort((a, b) => b[1] - a[1])
  }, [events])

  const sortedClients = useMemo(() => {
    return [...clients].sort((a, b) => {
      const timeA = a.createdAtMs ?? a.updatedAtMs ?? 0
      const timeB = b.createdAtMs ?? b.updatedAtMs ?? 0
      return sortOrder === 'newest' ? timeB - timeA : timeA - timeB
    })
  }, [clients, sortOrder])

  const login = async () => {
    const trimmed = pw.trim()
    if (!trimmed) return
    setBusy(true)
    setErr(null)
    try {
      const res = await getJson<{ clients: ClientRow[] }>('/api/v1/admin/clients?limit=2000', trimmed)
      setAuthedPw(trimmed)
      setClients(res.clients ?? [])
      try {
        sessionStorage.setItem(ADMIN_PW_KEY, trimmed)
      } catch {
        // ignore
      }
      if ((res.clients ?? []).length) {
        setSelectedClientId(res.clients[0].clientId)
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Login failed')
      setAuthedPw(null)
      setClients([])
      setSelectedClientId('')
      setEvents([])
    } finally {
      setBusy(false)
    }
  }

  const logout = () => {
    setAuthedPw(null)
    setClients([])
    setSelectedClientId('')
    setEvents([])
    setErr(null)
    try {
      sessionStorage.removeItem(ADMIN_PW_KEY)
    } catch {
      // ignore
    }
  }

  const refreshAll = async () => {
    if (!authedPw) return
    const currentSelected = selectedClientId
    setBusy(true)
    setErr(null)
    try {
      const clientsPromise = getJson<{ clients: ClientRow[] }>('/api/v1/admin/clients?limit=2000', authedPw)
      const eventsPromise = currentSelected
        ? getJson<{ clientId: string; events: EventRow[] }>(`/api/v1/admin/events/${encodeURIComponent(currentSelected)}?limit=5000`, authedPw)
        : Promise.resolve(null)

      const [clientsRes, eventsRes] = await Promise.all([clientsPromise, eventsPromise])
      const nextClients = clientsRes.clients ?? []
      setClients(nextClients)

      const selectedStillExists = currentSelected && nextClients.some((c) => c.clientId === currentSelected)
      const nextSelected = selectedStillExists ? currentSelected : (nextClients[0]?.clientId ?? '')
      if (nextSelected !== currentSelected) setSelectedClientId(nextSelected)

      if (eventsRes && nextSelected === currentSelected) {
        setEvents(eventsRes.events ?? [])
      } else if (!nextSelected) {
        setEvents([])
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to load clients')
    } finally {
      setBusy(false)
    }
  }

  const loadEvents = async (clientId: string) => {
    if (!authedPw) return
    setBusy(true)
    setErr(null)
    try {
      const res = await getJson<{ clientId: string; events: EventRow[] }>(`/api/v1/admin/events/${encodeURIComponent(clientId)}?limit=5000`, authedPw)
      setEvents(res.events ?? [])
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to load events')
      setEvents([])
    } finally {
      setBusy(false)
    }
  }

  const downloadAllZip = async () => {
    if (!authedPw) return
    setBusy(true)
    setErr(null)
    try {
      const res = await fetch(`${apiBase()}/api/v1/admin/download/all.zip`, {
        headers: { 'X-Admin-Password': authedPw },
      })
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`Download failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ''}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'agent-social-events.zip'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Download failed')
    } finally {
      setBusy(false)
    }
  }

  const downloadSelectedJson = async () => {
    if (!authedPw || !selectedClientId) return
    const payload = { clientId: selectedClientId, events }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `events_${selectedClientId}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  useEffect(() => {
    if (!authedPw) return
    if (!selectedClientId) return
    void loadEvents(selectedClientId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedPw, selectedClientId])

  return (
    <div className="page">
      <div className="row spaceBetween">
        <div>
          <div className="muted">
            <Link to="/app" className="link">
              ← Back
            </Link>
          </div>
          <div className="h1">Admin · Event Logs</div>
          <div className="muted">Per-user (clientId) event streams: messages, form submits, card clicks, etc.</div>
        </div>
        {authedPw ? (
          <div className="row">
            <button className="btn btnGhost" type="button" disabled={busy} onClick={() => void refreshAll()}>
              Refresh
            </button>
            <button className="btn btnGhost" type="button" disabled={busy} onClick={() => void downloadAllZip()}>
              Download all (zip)
            </button>
            <button className="btn btnGhost" type="button" disabled={busy || !selectedClientId} onClick={() => void downloadSelectedJson()}>
              Download selected (json)
            </button>
            <button className="btn btnGhost" type="button" disabled={busy} onClick={logout}>
              Logout
            </button>
          </div>
        ) : null}
      </div>

      {!authedPw ? (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="sectionTitle">Login</div>
          <div className="muted" style={{ marginTop: 6 }}>
            Enter admin password to view and export user event logs.
          </div>
          <div className="row" style={{ marginTop: 12, gap: 10 }}>
            <input
              className="input"
              style={{ flex: 1 }}
              value={pw}
              placeholder="Admin password"
              type="password"
              onChange={(e) => setPw(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void login()
              }}
            />
            <button className="btn" type="button" disabled={busy || !pw.trim()} onClick={() => void login()}>
              {busy ? '...' : 'Enter'}
            </button>
          </div>
          {err ? (
            <div className="muted" style={{ marginTop: 10, color: 'rgba(248, 113, 113, 0.95)' }}>
              {err}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="adminLayout" style={{ marginTop: 14 }}>
          <div className="adminSidebar card">
            <div className="row spaceBetween">
              <div className="sectionTitle">Clients</div>
              <div className="muted">{clients.length}</div>
            </div>
            <div className="row spaceBetween" style={{ marginTop: 8, marginBottom: 8 }}>
              <div className="muted" style={{ fontSize: 12 }}>Sort by start time:</div>
              <select
                className="select"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'newest' | 'oldest')}
                style={{ width: 100, fontSize: 12, padding: '4px 8px' }}
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
              </select>
            </div>
            <div className="adminClientList">
              {sortedClients.map((c) => {
                const active = c.clientId === selectedClientId
                return (
                  <button
                    key={c.clientId}
                    type="button"
                    className={active ? 'adminClientRow adminClientRowActive' : 'adminClientRow'}
                    onClick={() => setSelectedClientId(c.clientId)}
                  >
                    <div className="adminClientTop">
                      <div className="adminClientId">{c.clientId}</div>
                      <div className="muted">{fmtBytes(c.bytes)}</div>
                    </div>
                    <div className="muted">Started · {fmtTime(c.createdAtMs)}</div>
                    <div className="muted">Updated · {fmtTime(c.updatedAtMs)}</div>
                  </button>
                )
              })}
            </div>
          </div>

          <div className="adminMain">
            <div className="card">
              <div className="row spaceBetween">
                <div>
                  <div className="sectionTitle">Client</div>
                  <div className="muted">{selectedClientId || '—'}</div>
                </div>
                <div className="row" style={{ gap: 10 }}>
                  <input
                    className="input"
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search in events…"
                    style={{ width: 240 }}
                  />
                  <select className="select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 220 }}>
                    <option value="">All types</option>
                    {types.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="adminStats">
                <div className="muted">Total: {events.length}</div>
                {countsByType.slice(0, 6).map(([t, n]) => (
                  <div key={t} className="adminChip">
                    <span className="adminChipKey">{t}</span>
                    <span className="adminChipVal">{n}</span>
                  </div>
                ))}
              </div>

              {err ? (
                <div className="muted" style={{ marginTop: 10, color: 'rgba(248, 113, 113, 0.95)' }}>
                  {err}
                </div>
              ) : null}
            </div>

            <div className="card" style={{ marginTop: 12 }}>
              <div className="row spaceBetween">
                <div className="sectionTitle">Events</div>
                <div className="muted">
                  Showing {filteredEvents.length}/{events.length}
                </div>
              </div>

              <div className="adminTableWrap" style={{ marginTop: 10 }}>
                <table className="adminTable">
                  <thead>
                    <tr>
                      <th style={{ width: 160 }}>Time</th>
                      <th style={{ width: 340 }}>What happened</th>
                      <th style={{ width: 120 }}>Session</th>
                      <th style={{ width: 220 }}>Page</th>
                      <th>Payload</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEvents.slice(0, 1500).map((e, idx) => (
                      <tr key={`${e.at_ms ?? 0}_${idx}`}>
                        <td className="muted">{fmtTime(e.at_ms)}</td>
                        <td>
                          <div style={{ fontWeight: 800, color: 'rgba(226, 232, 240, 0.95)' }}>{summarizeEvent(e)}</div>
                          <div className="muted">
                            <span className="adminMono">{e.type ?? ''}</span>
                          </div>
                        </td>
                        <td className="muted">
                          {(e.sessionId ?? '').slice(0, 8)}
                          {(e.sessionId ?? '').length > 8 ? '…' : ''}
                        </td>
                        <td className="muted">{e.page ?? ''}</td>
                        <td>
                          <details>
                            <summary className="muted">View payload</summary>
                            <pre className="adminPayload">{JSON.stringify(e.payload ?? {}, null, 2)}</pre>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {filteredEvents.length > 1500 ? (
                <div className="muted" style={{ marginTop: 10 }}>
                  UI shows first 1500 rows for performance. Use Download to get everything.
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
