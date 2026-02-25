import type { Profile } from '../types'
import { RunnerCard } from './RunnerCard'

// Helper to format slot names
function formatSlot(slot: string): string {
  return slot
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export type BookingResultProps = {
  activity: string
  location: string
  selectedSlot?: string | null
  desiredTime?: string | null
  level?: string | null
  pace?: string | null
  profiles: Profile[]
  onProfileClick?: (profile: Profile) => void
  bookedTime?: string | null
  bookedLocation?: string | null
}

export function BookingResultCard(props: BookingResultProps) {
  const { activity, location, selectedSlot, desiredTime, level, pace, profiles, onProfileClick, bookedTime, bookedLocation } = props

  // Prefer bookedTime (concrete), fall back to desiredTime, then selectedSlot
  const timeDisplay = bookedTime || desiredTime || (selectedSlot ? formatSlot(selectedSlot) : null)
  // Prefer bookedLocation (specific venue), fall back to city
  const locationDisplay = bookedLocation ? `${bookedLocation}, ${location}` : location

  return (
    <div className="bookingResultCard">
      {/* Header with activity info */}
      <div className="bookingResultHeader">
        <div className="bookingResultTitle">
          <span className="bookingActivityIcon">{'🏃'}</span>
          <span className="bookingActivity">{activity}</span>
          <span className="bookingLocation">{locationDisplay}</span>
        </div>
      </div>

      {/* Prominent booked time display */}
      {timeDisplay && (
        <div className="bookingBookedTime">
          <span className="bookingBookedTimeIcon">{'📅'}</span>
          <span className="bookingBookedTimeText">{timeDisplay}</span>
        </div>
      )}

      {/* Specific meeting location */}
      {bookedLocation && (
        <div className="bookingBookedLocation">
          <span className="bookingBookedLocationIcon">{'📍'}</span>
          <span className="bookingBookedLocationText">{bookedLocation}</span>
        </div>
      )}

      {/* Filters summary */}
      {(level || pace) && (
        <div className="bookingFilters">
          {level && (
            <span className="bookingFilterTag">
              {'🎯'} {level}
            </span>
          )}
          {pace && (
            <span className="bookingFilterTag">
              {'⚡'} {pace} pace
            </span>
          )}
        </div>
      )}

      {/* Confirmed participants */}
      <div className="bookingParticipants">
        <div className="bookingParticipantsHeader">
          <span className="bookingParticipantsTitle">Confirmed Participants</span>
          <span className="bookingParticipantsCount">{profiles.length}</span>
        </div>
        <div className="bookingProfileGrid">
          {profiles.map(profile => (
            <RunnerCard
              key={profile.id}
              profile={profile}
              compact
              onClick={() => onProfileClick?.(profile)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// Progress card shown during booking
export type BookingProgressProps = {
  activity: string
  location: string
  selectedSlot?: string | null
  currentBatch: number
  totalCandidates: number
  totalInvited: number
  acceptedCount: number
  targetCount: number
  candidatesPerSlot?: Record<string, number>
}

export function BookingProgressCard(props: BookingProgressProps) {
  const {
    activity,
    location,
    selectedSlot,
    currentBatch,
    totalCandidates,
    totalInvited,
    acceptedCount,
    targetCount,
    candidatesPerSlot,
  } = props

  const progressPercent = Math.min(100, (acceptedCount / targetCount) * 100)
  const isComplete = acceptedCount >= targetCount

  return (
    <div className="bookingProgressCard">
      <div className="bookingProgressHeader">
        <div className="bookingProgressTitle">
          <span className="bookingProgressIcon">{isComplete ? '✅' : '🔄'}</span>
          <span>Finding {activity} buddies in {location}</span>
        </div>
        {selectedSlot && (
          <div className="bookingProgressSlot">
            <span className="bookingProgressSlotIcon">{'🕐'}</span>
            <span>{formatSlot(selectedSlot)}</span>
          </div>
        )}
      </div>

      {/* Slot breakdown if available */}
      {candidatesPerSlot && Object.keys(candidatesPerSlot).length > 0 && (
        <div className="bookingSlotBreakdown">
          <div className="bookingSlotBreakdownTitle">Availability by time slot:</div>
          <div className="bookingSlotTags">
            {Object.entries(candidatesPerSlot).map(([slot, count]) => (
              <span
                key={slot}
                className={`bookingSlotTag ${slot === selectedSlot ? 'bookingSlotTagSelected' : ''}`}
              >
                {formatSlot(slot)}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Progress stats */}
      <div className="bookingProgressStats">
        <div className="bookingProgressStat">
          <span className="bookingProgressStatValue">{acceptedCount}</span>
          <span className="bookingProgressStatLabel">/ {targetCount} confirmed</span>
        </div>
        <div className="bookingProgressStat">
          <span className="bookingProgressStatValue">{totalInvited}</span>
          <span className="bookingProgressStatLabel">/ {totalCandidates} invited</span>
        </div>
        <div className="bookingProgressStat">
          <span className="bookingProgressStatValue">Batch {currentBatch + 1}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="bookingProgressBar">
        <div
          className="bookingProgressBarFill"
          style={{
            width: `${progressPercent}%`,
            backgroundColor: isComplete ? '#22c55e' : '#3b82f6',
          }}
        />
      </div>
    </div>
  )
}
