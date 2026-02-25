import { Outlet, useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding.ts'
import { useAuth } from '../lib/AuthContext.tsx'
import type { PlannerModel } from '../lib/agentApi.ts'
import { PLANNER_OPTIONS, usePlannerModel } from '../lib/usePlannerModel.ts'

export function AppShell() {
  const { data, reset } = useOnboarding()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { model, setModel } = usePlannerModel()

  const handleLogout = async () => {
    reset()
    await logout()
    navigate('/login')
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand" onClick={() => navigate('/app')} style={{ cursor: 'pointer' }}>
          <div className="brandMark">A</div>
          <div className="brandText">
            <div className="brandName">Agent Social (Prototype)</div>
            <div className="brandSub">All mock data</div>
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
          {user?.photoURL && (
            <img src={user.photoURL} alt="" className="userAvatar" referrerPolicy="no-referrer" />
          )}
          <div className="userChip">
            <span className="dot online" />
            <span>{data?.name || user?.displayName || 'You'}</span>
          </div>
          <button className="btn btnGhost" onClick={handleLogout} type="button">
            Logout
          </button>
        </div>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
