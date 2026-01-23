import type { Group } from '../types'
import { AvatarStack } from './AvatarStack'
import { BadgePill } from './BadgePill'
import { Modal } from './Modal'

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function availabilityText(av: Group['availability']) {
  if (av.status === 'open') return 'Open to join'
  if (av.status === 'full') return av.startAt ? `Full · starts ${formatTime(av.startAt)}` : 'Full'
  return `Scheduled · starts ${formatTime(av.startAt)}`
}

export function GroupModal(props: {
  group: Group
  requiredSpots: number
  onClose: () => void
  onNavigate: () => void
  onJoin: () => void
  joined: boolean
}) {
  const g = props.group
  const spots = Math.max(0, g.capacity - g.memberCount)
  const canJoin = g.availability.status !== 'full' && spots >= props.requiredSpots

  return (
    <Modal
      title={g.title}
      onClose={props.onClose}
      footer={
        <div className="row">
          <button className="btn btnGhost" onClick={props.onClose} type="button">
            Close
          </button>
          <button className="btn btnGhost" onClick={props.onNavigate} type="button">
            Navigate (mock)
          </button>
          <button className="btn" onClick={props.onJoin} type="button" disabled={!canJoin || props.joined}>
            {props.joined ? 'Joined (mock)' : g.availability.status === 'scheduled' ? 'RSVP (mock)' : 'Join (mock)'}
          </button>
        </div>
      }
    >
      <div className="stack">
        <div className="muted">
          {availabilityText(g.availability)} · {g.location} · {g.memberCount}/{g.capacity}
        </div>

        <div>
          <div className="sectionTitle">Game info</div>
          <ul className="list">
            <li>Location: {g.location}</li>
            <li>Players: {g.memberCount}/{g.capacity}</li>
            <li>
              Spots left: {spots} · Your party: {props.requiredSpots}
            </li>
            <li>Level: {g.level}</li>
            <li>City: {g.city}</li>
          </ul>
        </div>

        <div>
          <div className="sectionTitle">Current players</div>
          <AvatarStack avatars={g.memberAvatars} />
          <div className="hint" style={{ marginTop: 8 }}>
            Joining will "hold" your spot (mock). This is not a real signup.
          </div>
        </div>

        <div>
          <div className="sectionTitle">Player details (mock)</div>
          <div className="stack">
            {g.members.map((m) => (
              <div key={m.id} className="memberRow">
                <div className="memberLeft">
                  <div className="memberAvatar">{m.name.slice(0, 1)}</div>
                  <div>
                    <div className="memberName">{m.name}</div>
                    <div className="muted">{m.headline}</div>
                  </div>
                </div>
                <div className="badgeRow">
                  {m.badges.map((b) => (
                    <BadgePill key={`${m.id}-${b.id}`} badge={b} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="sectionTitle">Notes</div>
          <ul className="list">
            {g.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      </div>
    </Modal>
  )
}
