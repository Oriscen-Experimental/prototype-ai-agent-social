import type { Group } from '../types'
import { AvatarStack } from './AvatarStack'
import { BadgePill } from './BadgePill'
import { Modal } from './Modal'

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function availabilityText(av: Group['availability']) {
  if (av.status === 'open') return '当前可加入'
  if (av.status === 'full') return av.startAt ? `已满 · ${formatTime(av.startAt)} 开始` : '已满'
  return `预约 · ${formatTime(av.startAt)} 开始`
}

export function GroupModal(props: {
  group: Group
  onClose: () => void
  onNavigate: () => void
  onJoin: () => void
  joined: boolean
}) {
  const g = props.group
  const canJoin = g.availability.status !== 'full'

  return (
    <Modal
      title={g.title}
      onClose={props.onClose}
      footer={
        <div className="row">
          <button className="btn btnGhost" onClick={props.onClose} type="button">
            关闭
          </button>
          <button className="btn btnGhost" onClick={props.onNavigate} type="button">
            导航过去（mock）
          </button>
          <button className="btn" onClick={props.onJoin} type="button" disabled={!canJoin || props.joined}>
            {props.joined ? '已报名（mock）' : g.availability.status === 'scheduled' ? '预约报名（mock）' : '报名参加（mock）'}
          </button>
        </div>
      }
    >
      <div className="stack">
        <div className="muted">
          {availabilityText(g.availability)} · {g.location} · {g.memberCount}/{g.capacity}
        </div>

        <div>
          <div className="sectionTitle">局信息</div>
          <ul className="list">
            <li>地点：{g.location}</li>
            <li>人数：{g.memberCount}/{g.capacity}</li>
            <li>水平：{g.level}</li>
            <li>城市：{g.city}</li>
          </ul>
        </div>

        <div>
          <div className="sectionTitle">已有成员</div>
          <AvatarStack avatars={g.memberAvatars} />
          <div className="hint" style={{ marginTop: 8 }}>
            点击报名后会把你“占位”（mock），不代表真实加入。
          </div>
        </div>

        <div>
          <div className="sectionTitle">成员详情（mock）</div>
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
          <div className="sectionTitle">备注</div>
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

