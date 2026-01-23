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
  const [note, setNote] = useState('Coffee, a walk, or a drink—what time works best for you?')

  return (
    <Modal
      title={props.title}
      onClose={props.onClose}
      footer={
        <div className="row">
          <button className="btn btnGhost" onClick={props.onClose} type="button">
            Cancel
          </button>
          <button
            className="btn"
            onClick={() => props.onSend({ when, note })}
            type="button"
            disabled={!when}
          >
            Send invite (mock)
          </button>
        </div>
      }
    >
      <div className="form">
        <label className="label">
          Time
          <input className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
        </label>
        <label className="label">
          Note
          <textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
        </label>
        <div className="hint">Prototype UI only—nothing is actually sent.</div>
      </div>
    </Modal>
  )
}
