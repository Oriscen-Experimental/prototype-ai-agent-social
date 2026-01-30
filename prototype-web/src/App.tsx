import { Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import { useOnboarding } from './lib/useOnboarding'
import { AppShell } from './components/AppShell'
import { AgentPage } from './pages/AgentPage'
import { CaseFlowRoutePage } from './pages/CaseFlowRoutePage'
import { ChatPage } from './pages/ChatPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { SearchHomePage } from './pages/SearchHomePage'
import { AdminPage } from './pages/AdminPage'

export default function App() {
  const { isCompleted } = useOnboarding()

  return (
    <Routes>
      <Route path="/" element={isCompleted ? <Navigate to="/app" replace /> : <OnboardingPage />} />
      <Route
        path="/app"
        element={isCompleted ? <AppShell /> : <Navigate to="/" replace />}
      >
        <Route index element={<SearchHomePage />} />
        <Route path="agent" element={<AgentPage />} />
        <Route path="case/:caseId" element={<CaseFlowRoutePage />} />
        <Route path="chat/:threadId" element={<ChatPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to={isCompleted ? '/app' : '/'} replace />} />
    </Routes>
  )
}
