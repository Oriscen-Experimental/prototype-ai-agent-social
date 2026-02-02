export type SocialArchetype = 'Explorer' | 'Builder' | 'Artist' | 'Guardian'

export type SortingAnswers = {
  restaurant: 'A' | 'B'
  travel: 'A' | 'B'
  birthday: 'A' | 'B'
  weather: 'A' | 'B' | 'C' | 'D'
  noResponse: 'A' | 'B' | 'C' | 'D'
  awkwardWave: 'A' | 'B'
}

export type WarningLabel = {
  warnings: string[]
  bestConsumed: string[]
  doNot: string[]
}

export type NutritionFacts = {
  servingSize: string
  servingsPerWeek: string
  amountPerServing: Array<{ label: string; value: string }>
  energyDrainPerHour: string
  recoveryTimeNeeded: string
  ingredients: string
  contains: string
  mayContain: string
}

export type UserManual = {
  modelName: string
  quickStart: string[]
  optimalOperatingConditions: string[]
  troubleshooting: Array<{ issue: string; fix: string }>
  warranty: string
}

export type SortingQuizResult = {
  noveltyScore: number
  securityScore: number
  archetype: SocialArchetype
  warningLabel: WarningLabel
  nutritionFacts: NutritionFacts
  userManual: UserManual
}

export type SortingQuestion = {
  key: keyof SortingAnswers
  title: string
  options: Array<{ value: SortingAnswers[keyof SortingAnswers]; label: string }>
}

export const SORTING_QUESTIONS: SortingQuestion[] = [
  {
    key: 'restaurant',
    title: 'You are choosing a restaurant for Friday night. What appeals to you more?',
    options: [
      { value: 'A', label: 'A. A place that has made the dish the exact same way for 50 years.' },
      { value: 'B', label: 'B. A fusion spot mixing two totally different cuisines.' },
    ],
  },
  {
    key: 'travel',
    title: "You're traveling to a foreign city where you don't speak the language. How do you spend your day?",
    options: [
      { value: 'A', label: "A. I book a guided tour. I want an expert to show me the history and ensure I don't miss the important sights." },
      { value: 'B', label: 'B. I just start walking. I want to get lost, find hidden gems, and figure it out on my own.' },
    ],
  },
  {
    key: 'birthday',
    title: "It's your birthday. What is the ideal vibe?",
    options: [
      { value: 'A', label: 'A. Going to a favorite neighborhood spot with my closest friends.' },
      { value: 'B', label: "B. Going on an adventure doing something I've never tried before." },
    ],
  },
  {
    key: 'weather',
    title: 'Which weather describes your current emotional climate?',
    options: [
      { value: 'A', label: 'A. Sunrise — I feel hopeful and energetic' },
      { value: 'B', label: 'B. Clear Skies — I feel grounded, steady' },
      { value: 'C', label: 'C. Lightning Storm — I feel tense, overwhelmed' },
      { value: 'D', label: 'D. Fog — I feel a bit lost, uncertain' },
    ],
  },
  {
    key: 'noResponse',
    title: "You text a new friend. It's been a few hours and no response. What is your honest gut reaction?",
    options: [
      { value: 'A', label: "A. I don't worry about it. They're probably busy." },
      { value: 'B', label: 'B. I re-read the text to check if I said something weird or came on too strong.' },
      { value: 'C', label: "C. I'll check my phone more often while I'm waiting for their response." },
      { value: 'D', label: "D. I notice, but don't chase after a response. If they want to reply they will." },
    ],
  },
  {
    key: 'awkwardWave',
    title: "You think someone is waving at you so you smile and wave back. Turns out they were waving to someone else. Now, it's awkward. What happens next?",
    options: [
      { value: 'A', label: 'A. I physically cringe and think about it for the rest of the day.' },
      { value: 'B', label: 'B. I laugh at myself and after a while forget it ever happened.' },
    ],
  },
]
