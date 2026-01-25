import { useMemo, useState } from 'react'

type TabKey = 'context' | 'schema' | 'planner'

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === 'object' && !Array.isArray(v)
}

export function DebugDrawer(props: { open: boolean; trace: unknown; onClose: () => void }) {
  const [tab, setTab] = useState<TabKey>('context')

  const context = useMemo(() => (isRecord(props.trace) ? props.trace.context : null), [props.trace])
  const schemas = useMemo(() => (isRecord(props.trace) ? props.trace.toolSchemas : null), [props.trace])
  const planner = useMemo(() => (isRecord(props.trace) ? props.trace.planner : null), [props.trace])

  const content = useMemo(() => {
    if (tab === 'context') return context
    if (tab === 'schema') return schemas
    return planner
  }, [tab, context, schemas, planner])

  if (!props.open) return null

  return (
    <div className="debugOverlay" onMouseDown={props.onClose}>
      <div className="debugDrawer" onMouseDown={(e) => e.stopPropagation()}>
        <div className="debugHeader">
          <div className="debugTitle">Debug</div>
          <button className="iconBtn" type="button" onClick={props.onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="debugTabs">
          <button className={tab === 'context' ? 'debugTab debugTabActive' : 'debugTab'} type="button" onClick={() => setTab('context')}>
            Context
          </button>
          <button className={tab === 'schema' ? 'debugTab debugTabActive' : 'debugTab'} type="button" onClick={() => setTab('schema')}>
            Library Schema
          </button>
          <button className={tab === 'planner' ? 'debugTab debugTabActive' : 'debugTab'} type="button" onClick={() => setTab('planner')}>
            Planner Output
          </button>
        </div>

        <div className="debugBody">
          <pre className="debugPre">{content ? prettyJson(content) : 'No data yet. Send a message to refresh.'}</pre>
        </div>
      </div>
    </div>
  )
}
