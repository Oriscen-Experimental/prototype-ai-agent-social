import { Outlet, useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding'
import { readJson, writeJson, subscribe } from '../lib/storage'
import { useSyncExternalStore, useCallback } from 'react'
import type { PlannerModel } from '../lib/agentApi'

const PLANNER_MODEL_KEY = 'plannerModel'
const DEFAULT_MODEL: PlannerModel = 'light'

const PLANNER_OPTIONS: { value: PlannerModel; label: string }[] = [
  { value: 'light', label: 'light and fast' },
  { value: 'medium', label: 'medium' },
  { value: 'heavy', label: 'heavy and slow' },
]

function getPlannerModel(): PlannerModel {
  return readJson<PlannerModel>(PLANNER_MODEL_KEY, DEFAULT_MODEL)
}

export function usePlannerModel() {
  const model = useSyncExternalStore(subscribe, getPlannerModel)
  const setModel = useCallback((m: PlannerModel) => {
    writeJson(PLANNER_MODEL_KEY, m)
  }, [])
  return { model, setModel }
}

export function AppShell() {
  const { data, reset } = useOnboarding()
  const navigate = useNavigate()
  const { model, setModel } = usePlannerModel()

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brandMark">A</div>
          <div className="brandText">
            <div className="brandName">Agent Social (Prototype)</div>
            <div className="brandSub">Gemini orchestrator + AI-generated results</div>
          </div>
        </div>
        <div className="topbarRight">
          <select
            className="plannerModelSelect"
            value={model}
            onChange={(e) => setModel(e.target.value as PlannerModel)}
          >
            {PLANNER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="userChip">
            <span className="dot online" />
            <span>{data?.name || 'You'}</span>
            <span className="muted">· {data?.city || '—'}</span>
          </div>
          <button
            className="btn btnGhost"
            onClick={() => {
              reset()
              navigate('/')
            }}
            type="button"
          >
            Restart onboarding
          </button>
        </div>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
