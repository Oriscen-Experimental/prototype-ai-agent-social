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
          <div className="h1">页面出错了（prototype）</div>
          <div className="muted" style={{ marginTop: 8 }}>
            {this.state.message || '发生了未知错误'}
          </div>

          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn btnGhost" type="button" onClick={() => window.history.back()}>
              返回
            </button>
            <a className="btn btnGhost" href="/app">
              回到搜索
            </a>
            <a className="btn" href="/">
              回到首页
            </a>
          </div>

          <div className="hint" style={{ marginTop: 10 }}>
            这是一个纯前端 mock 原型。若你在某些环境（无痕/隐私模式）下看到黑屏，可能是浏览器限制了本地存储或脚本执行。
          </div>
        </div>
      </div>
    )
  }
}

