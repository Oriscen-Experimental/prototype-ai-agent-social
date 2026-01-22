import type { VettingBadge } from '../types'

export function BadgePill(props: { badge: VettingBadge }) {
  return (
    <span className="badge" title={props.badge.description}>
      {props.badge.label}
    </span>
  )
}

