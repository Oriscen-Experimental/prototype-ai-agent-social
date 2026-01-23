import type { ReactNode } from 'react'
import { Component } from 'react'

type Props = { children: ReactNode }
type State = { hasError: boolean; message: string }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : String(error)
    return { hasError: true, message }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="centerWrap">
        <div className="panel">
          <div className="h1">Something went wrong (prototype)</div>
          <div className="muted" style={{ marginTop: 8 }}>
            {this.state.message || 'An unknown error occurred.'}
          </div>

          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn btnGhost" type="button" onClick={() => window.history.back()}>
              Go back
            </button>
            <a className="btn btnGhost" href="/app">
              Back to search
            </a>
            <a className="btn" href="/">
              Home
            </a>
          </div>

          <div className="hint" style={{ marginTop: 10 }}>
            This is a frontend-only mock prototype. If you see a blank screen in some environments (private browsing, strict
            privacy settings), your browser may be blocking local storage or scripts.
          </div>
        </div>
      </div>
    )
  }
}
