import { Outlet, useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding'

export function AppShell() {
  const { data, reset } = useOnboarding()
  const navigate = useNavigate()

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brandMark">A</div>
          <div className="brandText">
            <div className="brandName">Agent Social (Prototype)</div>
            <div className="brandSub">Any-purpose · fully mocked</div>
          </div>
        </div>
        <div className="topbarRight">
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
