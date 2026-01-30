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

export type CaseId = 'drink' | 'comfort' | 'talk-ai' | 'tennis' | 'agent'

export type GroupAvailability =
  | { status: 'open' }
  | { status: 'scheduled'; startAt: number }
  | { status: 'full'; startAt?: number }

export type GroupMember = {
  id: string
  name: string
  headline: string
  badges: VettingBadge[]
}

export type Group = {
  id: string
  title: string
  city: string
  location: string
  level: string
  availability: GroupAvailability
  memberCount: number
  capacity: number
  memberAvatars: string[]
  members: GroupMember[]
  notes: string[]
}

export type BaseCaseDefinition = {
  id: CaseId
  title: string
  exampleQuery: string
  assistantIntro: string
  questions?: ClarificationQuestion[]
}

export type CaseDefinition =
  | (BaseCaseDefinition & { resultType: 'profiles'; profiles: Profile[] })
  | (BaseCaseDefinition & { resultType: 'groups'; groups: Group[] })

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
  profile?: Profile
}
