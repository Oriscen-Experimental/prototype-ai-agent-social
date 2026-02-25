import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../lib/AuthContext.tsx'
import { useOnboarding } from '../lib/useOnboarding.ts'

export function LoginPage() {
  const { user, loading, signInWithGoogle } = useAuth()
  const { isCompleted } = useOnboarding()
  const [error, setError] = useState<string | null>(null)

  if (loading) {
    return (
      <div className="centerWrap">
        <div className="panel loginPanel">
          <div className="h1">Loading...</div>
        </div>
      </div>
    )
  }

  if (user) {
    return <Navigate to={isCompleted ? '/app' : '/onboarding'} replace />
  }

  return (
    <div className="centerWrap">
      <div className="panel loginPanel">
        <div className="panelHeader" style={{ textAlign: 'center' }}>
          <div className="loginLogo">A</div>
          <div className="h1">Agent Social</div>
          <div className="muted" style={{ marginTop: 8 }}>
            Connect with people who share your interests
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16 }}>
          <GoogleLogin
            onSuccess={async (response) => {
              if (response.credential) {
                try {
                  setError(null)
                  await signInWithGoogle(response.credential)
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'Login failed')
                }
              }
            }}
            onError={() => setError('Google login failed')}
            theme="outline"
            size="large"
            text="signin_with"
          />
        </div>

        {error && (
          <div className="hint" style={{ textAlign: 'center', marginTop: 12, color: '#c53030' }}>
            {error}
          </div>
        )}

        <div className="hint" style={{ textAlign: 'center', marginTop: 12 }}>
          This is a prototype. Your data is stored locally in your browser.
        </div>
      </div>
    </div>
  )
}
