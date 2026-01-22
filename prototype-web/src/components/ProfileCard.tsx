import type { Profile } from '../types'
import { BadgePill } from './BadgePill'

export function ProfileCard(props: { profile: Profile; onClick: () => void }) {
  const p = props.profile
  return (
    <button type="button" className="profileCard" onClick={props.onClick}>
      <div className="profileTop">
        <div className="profileNameRow">
          <span className={p.presence === 'online' ? 'dot online' : 'dot offline'} />
          <span className="profileName">{p.name}</span>
          {p.kind === 'ai' ? <span className="tag">AI</span> : <span className="tag">真人</span>}
          <span className="muted">· {p.presence === 'online' ? '在线' : '离线'}</span>
          <span className="muted">· {p.city}</span>
        </div>
        <div className="score">{p.score}/100</div>
      </div>
      <div className="profileHeadline">{p.headline}</div>
      <div className="badgeRow">
        {p.badges.slice(0, 3).map((b) => (
          <BadgePill key={b.id} badge={b} />
        ))}
      </div>
    </button>
  )
}
