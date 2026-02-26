import type { Profile } from '../types'
import { RunnerCard } from './RunnerCard'

export type RescheduleVoteEntry = {
  userId: string
  vote: 'accept' | 'decline' | 'pending' | 'expired'
  profile: Profile
}

export type RescheduleVoteCardProps = {
  activity: string
  location: string
  responses: RescheduleVoteEntry[]
  onProfileClick?: (profile: Profile) => void
}

function voteIcon(vote: string): string {
  switch (vote) {
    case 'accept': return '✅'
    case 'decline': return '❌'
    case 'expired': return '⏰'
    default: return '⏳'
  }
}

function voteLabel(vote: string): string {
  switch (vote) {
    case 'accept': return 'Accepted'
    case 'decline': return 'Declined'
    case 'expired': return 'No response'
    default: return 'Waiting...'
  }
}

export function RescheduleVoteCard(props: RescheduleVoteCardProps) {
  const { activity, location, responses, onProfileClick } = props
  const accepted = responses.filter(r => r.vote === 'accept').length
  const declined = responses.filter(r => r.vote === 'decline' || r.vote === 'expired').length
  const pending = responses.filter(r => r.vote === 'pending').length
  const total = responses.length
  const responded = total - pending

  return (
    <div className="bookingProgressCard">
      <div className="bookingProgressHeader">
        <div className="bookingProgressTitle">
          <span className="bookingProgressIcon">{pending > 0 ? '🔄' : '✅'}</span>
          <span>Rescheduling {activity} in {location}</span>
        </div>
      </div>

      <div className="bookingProgressStats">
        <div className="bookingProgressStat">
          <span className="bookingProgressStatValue">{accepted}</span>
          <span className="bookingProgressStatLabel"> accepted</span>
        </div>
        <div className="bookingProgressStat">
          <span className="bookingProgressStatValue">{declined}</span>
          <span className="bookingProgressStatLabel"> declined</span>
        </div>
        <div className="bookingProgressStat">
          <span className="bookingProgressStatValue">{pending}</span>
          <span className="bookingProgressStatLabel"> waiting</span>
        </div>
      </div>

      <div className="bookingProgressBar">
        <div
          className="bookingProgressBarFill"
          style={{
            width: `${(responded / Math.max(total, 1)) * 100}%`,
            backgroundColor: pending === 0 ? '#22c55e' : '#3b82f6',
          }}
        />
      </div>

      {/* Per-participant vote status with RunnerCards */}
      <div style={{ marginTop: 12 }}>
        <div className="runnerCardGrid">
          {responses.map(r => (
            <div key={r.userId} style={{ position: 'relative' }}>
              <RunnerCard
                profile={r.profile}
                compact
                onClick={() => onProfileClick?.(r.profile)}
              />
              <div style={{
                position: 'absolute', top: 4, right: 4,
                fontSize: 11, padding: '2px 6px',
                borderRadius: 6, background: 'rgba(0,0,0,0.6)', color: '#fff',
              }}>
                {voteIcon(r.vote)} {voteLabel(r.vote)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
