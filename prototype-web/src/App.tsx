import { Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import { useAuth } from './lib/AuthContext.tsx'
import { useOnboarding } from './lib/useOnboarding.ts'
import { AppShell } from './components/AppShell.tsx'
import { AgentPage } from './pages/AgentPage.tsx'
import { CaseFlowRoutePage } from './pages/CaseFlowRoutePage.tsx'
import { ChatPage } from './pages/ChatPage.tsx'
import { AdminPage } from './pages/AdminPage.tsx'
import { LoginPage } from './pages/LoginPage.tsx'
import { NewOnboardingPage } from './pages/NewOnboardingPage.tsx'
import { HomePage } from './pages/HomePage.tsx'
import { DemoChatPage } from './pages/DemoChatPage.tsx'

export default function App() {
  const { user, loading } = useAuth()
  const { isCompleted } = useOnboarding()

  if (loading) {
    return (
      <div className="centerWrap">
        <div className="panel loginPanel">
          <div className="h1" style={{ textAlign: 'center' }}>Loading...</div>
        </div>
      </div>
    )
  }

  return (
    <Routes>
      {/* Public: login */}
      <Route
        path="/login"
        element={user ? <Navigate to={isCompleted ? '/app' : '/onboarding'} replace /> : <LoginPage />}
      />

      {/* Requires auth, not yet onboarded */}
      <Route
        path="/onboarding"
        element={
          !user ? <Navigate to="/login" replace /> :
          isCompleted ? <Navigate to="/app" replace /> :
          <NewOnboardingPage />
        }
      />

      {/* Requires auth + onboarding */}
      <Route
        path="/app"
        element={
          !user ? <Navigate to="/login" replace /> :
          !isCompleted ? <Navigate to="/onboarding" replace /> :
          <AppShell />
        }
      >
        <Route index element={<HomePage />} />
        <Route path="demo-chat" element={<DemoChatPage />} />
        <Route path="agent" element={<AgentPage />} />
        <Route path="case/:caseId" element={<CaseFlowRoutePage />} />
        <Route path="chat/:threadId" element={<ChatPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>

      {/* Catch-all */}
      <Route
        path="*"
        element={<Navigate to={user ? (isCompleted ? '/app' : '/onboarding') : '/login'} replace />}
      />
    </Routes>
  )
}
