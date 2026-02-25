import { useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding.ts'

const OPTIONS = [
  {
    id: 'hobby-match',
    emoji: '\u{1F3AF}',
    title: "I want to find people to do my hobby activities with",
    subtitle: "Tell me what you want to do — I'll arrange everything",
    route: '/app/agent',
  },
  {
    id: 'casual-meetup',
    emoji: '\u{2615}',
    title: "I want to meet someone for a relaxing, casual experience",
    subtitle: "A low-key hangout — just tell me what sounds good",
    route: '/app/agent?q=I want a casual meetup',
  },
]

export function HomePage() {
  const navigate = useNavigate()
  const { data } = useOnboarding()

  return (
    <div className="page">
      <div className="hero">
        <div className="heroTitle">
          Hey{data?.name ? `, ${data.name}` : ''}! What brings you here today?
        </div>
        <div className="muted" style={{ fontSize: 15 }}>
          Choose the option that resonates with you most.
        </div>
      </div>

      <div className="homeCards">
        {OPTIONS.map(opt => (
          <button
            key={opt.id}
            className="homeCard"
            type="button"
            onClick={() => navigate(opt.route)}
          >
            <div className="homeCardEmoji">{opt.emoji}</div>
            <div className="homeCardTitle">{opt.title}</div>
            <div className="muted">{opt.subtitle}</div>
            <div className="homeCardCta">Explore this path &rarr;</div>
          </button>
        ))}
      </div>
    </div>
  )
}
