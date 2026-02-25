import type { Profile } from '../types'

// Helper to format slot names
function formatSlot(slot: string): string {
  return slot
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

// Helper to get level emoji
function getLevelEmoji(level?: string): string {
  switch (level) {
    case 'beginner': return '🌱'
    case 'intermediate': return '🏃'
    case 'advanced': return '🔥'
    case 'competitive': return '🏆'
    default: return '🏃'
  }
}

// Helper to get pace label
function getPaceLabel(pace?: string): string {
  switch (pace) {
    case 'easy': return '6:30+/km'
    case 'moderate': return '5:30-6:30/km'
    case 'fast': return '4:30-5:30/km'
    case 'racing': return '<4:30/km'
    default: return ''
  }
}

export function RunnerCard(props: { profile: Profile; onClick?: () => void; compact?: boolean }) {
  const p = props.profile
  const hasRunningInfo = p.runningLevel || p.runningPace || p.availability?.length

  if (props.compact) {
    return (
      <button type="button" className="runnerCard runnerCardCompact" onClick={props.onClick}>
        <div className="runnerCardHeader">
          <div className="runnerCardName">
            <span className={p.presence === 'online' ? 'dot online' : 'dot offline'} />
            <span className="runnerName">{p.name}</span>
            <span className="runnerScore">{p.score}</span>
          </div>
        </div>
        <div className="runnerCardMeta">
          <span className="runnerCity">{p.city}</span>
          {p.runningLevel && (
            <span className="runnerLevel">
              {getLevelEmoji(p.runningLevel)} {p.runningLevel}
            </span>
          )}
        </div>
        {p.runningPace && (
          <div className="runnerPace">{getPaceLabel(p.runningPace)}</div>
        )}
      </button>
    )
  }

  return (
    <button type="button" className="runnerCard" onClick={props.onClick}>
      <div className="runnerCardHeader">
        <div className="runnerCardName">
          <span className={p.presence === 'online' ? 'dot online' : 'dot offline'} />
          <span className="runnerName">{p.name}</span>
          {p.kind === 'ai' ? <span className="tag">AI</span> : <span className="tag">Human</span>}
        </div>
        <div className="runnerScore">{p.score}</div>
      </div>

      <div className="runnerCardBody">
        <div className="runnerCity">{p.city}</div>
        <div className="runnerHeadline">{p.headline}</div>

        {hasRunningInfo && (
          <div className="runnerStats">
            {p.runningLevel && (
              <div className="runnerStat">
                <span className="runnerStatLabel">Level</span>
                <span className="runnerStatValue">
                  {getLevelEmoji(p.runningLevel)} {p.runningLevel}
                </span>
              </div>
            )}
            {p.runningPace && (
              <div className="runnerStat">
                <span className="runnerStatLabel">Pace</span>
                <span className="runnerStatValue">{getPaceLabel(p.runningPace)}</span>
              </div>
            )}
            {p.runningDistance && (
              <div className="runnerStat">
                <span className="runnerStatLabel">Distance</span>
                <span className="runnerStatValue">{p.runningDistance}</span>
              </div>
            )}
          </div>
        )}

        {p.availability && p.availability.length > 0 && (
          <div className="runnerAvailability">
            <span className="runnerAvailLabel">Available:</span>
            <div className="runnerSlots">
              {p.availability.map(slot => (
                <span key={slot} className="runnerSlot">{formatSlot(slot)}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </button>
  )
}
