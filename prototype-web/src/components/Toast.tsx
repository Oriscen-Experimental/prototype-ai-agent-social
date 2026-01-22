import { useEffect } from 'react'

export function Toast(props: { message: string; onClose: () => void }) {
  useEffect(() => {
    const t = window.setTimeout(props.onClose, 2600)
    return () => window.clearTimeout(t)
  }, [props])

  return (
    <div className="toast" role="status" aria-live="polite">
      {props.message}
    </div>
  )
}

