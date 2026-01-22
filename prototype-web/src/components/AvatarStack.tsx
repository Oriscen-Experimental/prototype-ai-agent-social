export function AvatarStack(props: { avatars: string[] }) {
  const shown = props.avatars.slice(0, 8)
  const rest = Math.max(0, props.avatars.length - shown.length)
  return (
    <div className="avatarStack" aria-label="members">
      {shown.map((a, idx) => (
        <span key={`${a}-${idx}`} className="avatarPill" title={a}>
          {a}
        </span>
      ))}
      {rest ? <span className="avatarPill avatarMore">+{rest}</span> : null}
    </div>
  )
}

