import { useMemo, useState } from 'react'

type TabKey = 'plannerInput' | 'plannerOutput'

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
  const [tab, setTab] = useState<TabKey>('plannerInput')

  const plannerInput = useMemo(() => (isRecord(props.trace) ? props.trace.plannerInput : null), [props.trace])
  const plannerOutput = useMemo(() => (isRecord(props.trace) ? props.trace.plannerOutput : null), [props.trace])

  const content = useMemo(() => {
    if (tab === 'plannerInput') return plannerInput
    return plannerOutput
  }, [tab, plannerInput, plannerOutput])

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
          <button
            className={tab === 'plannerInput' ? 'debugTab debugTabActive' : 'debugTab'}
            type="button"
            onClick={() => setTab('plannerInput')}
          >
            Planner Input
          </button>
          <button
            className={tab === 'plannerOutput' ? 'debugTab debugTabActive' : 'debugTab'}
            type="button"
            onClick={() => setTab('plannerOutput')}
          >
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
