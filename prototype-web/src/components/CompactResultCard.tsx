import type { Group, Profile } from '../types'

export function CompactProfileCard(props: { profile: Profile; onClick: () => void }) {
  const p = props.profile
  return (
    <button type="button" className="compactCard" onClick={props.onClick}>
      <div className="compactTop">
        <div className="compactTitleRow">
          <span className={p.presence === 'online' ? 'dot online' : 'dot offline'} />
          <span className="compactTitle">{p.name}</span>
          <span className="compactMeta">{p.city}</span>
        </div>
        <div className="compactScore">{p.score}</div>
      </div>
      <div className="compactSub">{p.headline}</div>
    </button>
  )
}

function formatAvailability(av: Group['availability']) {
  if (av.status === 'open') return { label: 'Open', tone: 'good' as const }
  if (av.status === 'full') return { label: 'Full', tone: 'bad' as const }
  return { label: 'Scheduled', tone: 'warn' as const }
}

export function CompactGroupCard(props: { group: Group; onClick: () => void }) {
  const g = props.group
  const av = formatAvailability(g.availability)
  return (
    <button type="button" className="compactCard" onClick={props.onClick}>
      <div className="compactTop">
        <div className="compactTitleRow">
          <span className={av.tone === 'good' ? 'dot online' : av.tone === 'bad' ? 'dot offline' : 'dot warn'} />
          <span className="compactTitle">{g.title}</span>
        </div>
        <div className="compactScore">
          {g.memberCount}/{g.capacity}
        </div>
      </div>
      <div className="compactSub">
        {av.label} · {g.location}
      </div>
    </button>
  )
}

