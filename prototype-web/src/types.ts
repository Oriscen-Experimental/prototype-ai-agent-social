export type Presence = 'online' | 'offline'

export type BadgeId = 'photo' | 'linkedin' | 'id'

export type VettingBadge = {
  id: BadgeId
  label: string
  description: string
}

export type ProfileKind = 'human' | 'ai'

export type Profile = {
  id: string
  kind: ProfileKind
  name: string
  presence: Presence
  city: string
  headline: string
  score: number
  badges: VettingBadge[]
  about: string[]
  matchReasons: string[]
  topics: string[]
  healingReasons?: string[]
  aiNote?: string
}

export type ClarificationQuestion = {
  key: string
  question: string
  options: Array<{ value: string; label: string }>
  required?: boolean
}

export type CaseId = 'drink' | 'comfort' | 'talk-ai' | 'tennis'

export type CaseDefinition = {
  id: CaseId
  title: string
  exampleQuery: string
  assistantIntro: string
  questions?: ClarificationQuestion[]
  profiles: Profile[]
}

export type OnboardingData = {
  name: string
  gender: string
  age: string
  city: string
  address: string
  interests: string[]
  goals?: string[]
  vibe?: string
}

export type ChatMessage = {
  id: string
  role: 'me' | 'other' | 'system'
  text: string
  at: number
}

export type ChatThread = {
  threadId: string
  title: string
  caseId: CaseId
  profileId: string
  profileKind: ProfileKind
  messages: ChatMessage[]
}
