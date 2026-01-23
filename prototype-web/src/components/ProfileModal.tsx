import type { Profile } from '../types'
import { BadgePill } from './BadgePill'
import { Modal } from './Modal'

export function ProfileModal(props: {
  profile: Profile
  onClose: () => void
  onChat: () => void
  onInvite?: () => void
}) {
  const p = props.profile

  return (
    <Modal
      title={`${p.name} · ${p.kind === 'ai' ? 'AI' : 'Human'} · ${p.presence === 'online' ? 'Online' : 'Offline'}`}
      onClose={props.onClose}
      footer={
        <div className="row">
          <button className="btn btnGhost" onClick={props.onClose} type="button">
            Close
          </button>
          {p.kind === 'human' && props.onInvite ? (
            <button className="btn btnGhost" onClick={props.onInvite} type="button">
              Send calendar invite (mock)
            </button>
          ) : null}
          <button className="btn" onClick={props.onChat} type="button">
            Chat
          </button>
        </div>
      }
    >
      <div className="stack">
        <div className="muted">
          Match score: <b>{p.score}/100</b> · {p.city}
        </div>

        {p.aiNote ? <div className="callout">{p.aiNote}</div> : null}

        {p.badges.length ? (
          <div>
            <div className="sectionTitle">Vetting badges</div>
            <div className="badgeRow">
              {p.badges.map((b) => (
                <BadgePill key={b.id} badge={b} />
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <div className="sectionTitle">Basics</div>
          <ul className="list">
            {p.about.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>

        <div>
          <div className="sectionTitle">Why you match</div>
          <ul className="list">
            {p.matchReasons.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>

        {p.healingReasons?.length ? (
          <div>
            <div className="sectionTitle">Why this might help</div>
            <ul className="list">
              {p.healingReasons.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div>
          <div className="sectionTitle">Conversation topics</div>
          <div className="tagRow">
            {p.topics.map((t) => (
              <span className="tag" key={t}>
                {t}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  )
}
