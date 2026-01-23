import type { Group } from '../types'
import { AvatarStack } from './AvatarStack'

function formatAvailability(av: Group['availability']) {
  if (av.status === 'open') return { label: 'Open to join', tone: 'good' as const }
  if (av.status === 'full') return { label: av.startAt ? `Full · starts ${formatTime(av.startAt)}` : 'Full', tone: 'bad' as const }
  return { label: `Scheduled · starts ${formatTime(av.startAt)}`, tone: 'warn' as const }
}

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function GroupCard(props: { group: Group; onClick: () => void }) {
  const g = props.group
  const av = formatAvailability(g.availability)

  return (
    <button type="button" className="profileCard" onClick={props.onClick}>
      <div className="profileTop">
        <div className="profileNameRow">
          <span className={av.tone === 'good' ? 'dot online' : av.tone === 'bad' ? 'dot offline' : 'dot warn'} />
          <span className="profileName">{g.title}</span>
          <span className="tag">Group</span>
        </div>
        <div className="score">
          {g.memberCount}/{g.capacity}
        </div>
      </div>

      <div className="profileHeadline">{av.label}</div>
      <div className="muted" style={{ marginTop: 8 }}>
        Location: {g.location}
      </div>
      <div className="muted" style={{ marginTop: 4 }}>
        Level: {g.level}
      </div>
      <div style={{ marginTop: 10 }}>
        <AvatarStack avatars={g.memberAvatars} />
      </div>
    </button>
  )
}
