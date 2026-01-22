import { useMemo, useState } from 'react'
import { Modal } from './Modal'

function isoLocal() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

export function CalendarInviteModal(props: {
  title: string
  onClose: () => void
  onSend: (payload: { when: string; note: string }) => void
}) {
  const defaultWhen = useMemo(() => isoLocal(), [])
  const [when, setWhen] = useState(defaultWhen)
  const [note, setNote] = useState('喝一杯/散步都可以，你更方便哪个时间？')

  return (
    <Modal
      title={props.title}
      onClose={props.onClose}
      footer={
        <div className="row">
          <button className="btn btnGhost" onClick={props.onClose} type="button">
            取消
          </button>
          <button
            className="btn"
            onClick={() => props.onSend({ when, note })}
            type="button"
            disabled={!when}
          >
            发送邀请（mock）
          </button>
        </div>
      }
    >
      <div className="form">
        <label className="label">
          时间
          <input className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
        </label>
        <label className="label">
          备注
          <textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
        </label>
        <div className="hint">仅展示 UI 行为，不会真的发送。</div>
      </div>
    </Modal>
  )
}

