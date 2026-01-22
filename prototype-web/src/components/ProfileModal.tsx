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
      title={`${p.name} · ${p.kind === 'ai' ? 'AI' : '真人'} · ${p.presence === 'online' ? '在线' : '离线'}`}
      onClose={props.onClose}
      footer={
        <div className="row">
          <button className="btn btnGhost" onClick={props.onClose} type="button">
            关闭
          </button>
          {p.kind === 'human' && props.onInvite ? (
            <button className="btn btnGhost" onClick={props.onInvite} type="button">
              发日历约（mock）
            </button>
          ) : null}
          <button className="btn" onClick={props.onChat} type="button">
            去聊天
          </button>
        </div>
      }
    >
      <div className="stack">
        <div className="muted">
          匹配度：<b>{p.score}/100</b> · {p.city}
        </div>

        {p.aiNote ? <div className="callout">{p.aiNote}</div> : null}

        {p.badges.length ? (
          <div>
            <div className="sectionTitle">Vetting Badge</div>
            <div className="badgeRow">
              {p.badges.map((b) => (
                <BadgePill key={b.id} badge={b} />
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <div className="sectionTitle">基本信息</div>
          <ul className="list">
            {p.about.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>

        <div>
          <div className="sectionTitle">匹配理由</div>
          <ul className="list">
            {p.matchReasons.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </div>

        {p.healingReasons?.length ? (
          <div>
            <div className="sectionTitle">为什么他/她可能“疗愈”你</div>
            <ul className="list">
              {p.healingReasons.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div>
          <div className="sectionTitle">可聊话题</div>
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

