import { Outlet, useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding'
import type { PlannerModel } from '../lib/agentApi'
import { PLANNER_OPTIONS, usePlannerModel } from '../lib/usePlannerModel'

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
