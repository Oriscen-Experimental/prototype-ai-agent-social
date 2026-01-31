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

export type SortingQuizResult = {
  noveltyScore: number
  securityScore: number
  archetype: SocialArchetype
  warningLabel: WarningLabel
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
    title: "You’re traveling to a foreign city where you don't speak the language. How do you spend your day?",
    options: [
      { value: 'A', label: "A. I book a guided tour. I want an expert to show me the history and ensure I don't miss the important sights." },
      { value: 'B', label: 'B. I just start walking. I want to get lost, find hidden gems, and figure it out on my own.' },
    ],
  },
  {
    key: 'birthday',
    title: 'It’s your birthday. What is the ideal vibe?',
    options: [
      { value: 'A', label: 'A. Going to a favorite neighborhood spot with my closest friends.' },
      { value: 'B', label: 'B. Going on an adventure doing something I’ve never tried before.' },
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
    title: 'You text a new friend. It’s been a few hours and no response. What is your honest gut reaction?',
    options: [
      { value: 'A', label: "A. I don’t worry about it. They're probably busy." },
      { value: 'B', label: 'B. I re-read the text to check if I said something weird or came on too strong.' },
      { value: 'C', label: 'C. I’ll check my phone more often while I’m waiting for their response.' },
      { value: 'D', label: 'D. I notice, but don’t chase after a response. If they want to reply they will.' },
    ],
  },
  {
    key: 'awkwardWave',
    title: 'You think someone is waving at you so you smile and wave back. Turns out they were waving to someone else. Now, it’s awkward. What happens next?',
    options: [
      { value: 'A', label: 'A. I physically cringe and think about it for the rest of the day.' },
      { value: 'B', label: 'B. I laugh at myself and after a while forget it ever happened.' },
    ],
  },
]

export function scoreSortingQuiz(answers: SortingAnswers): Pick<SortingQuizResult, 'noveltyScore' | 'securityScore'> {
  const noveltyScore =
    (answers.restaurant === 'B' ? 1 : 0) + (answers.travel === 'B' ? 1 : 0) + (answers.birthday === 'B' ? 1 : 0)

  const securityScore =
    (answers.weather === 'A' || answers.weather === 'B' ? 1 : 0) +
    (answers.noResponse === 'A' || answers.noResponse === 'D' ? 1 : 0) +
    (answers.awkwardWave === 'B' ? 1 : 0)

  return { noveltyScore, securityScore }
}

export function classifyArchetype(noveltyScore: number, securityScore: number): SocialArchetype {
  const noveltyHigh = noveltyScore >= 2
  const securityHigh = securityScore >= 2

  if (noveltyHigh && securityHigh) return 'Explorer'
  if (!noveltyHigh && securityHigh) return 'Builder'
  if (noveltyHigh && !securityHigh) return 'Artist'
  return 'Guardian'
}

function clampScore(score: number) {
  return Math.max(0, Math.min(3, Math.round(score)))
}

export function makeWarningLabel(archetype: SocialArchetype, noveltyScore: number, securityScore: number): WarningLabel {
  const n = clampScore(noveltyScore)
  const s = clampScore(securityScore)

  const securityFlavor =
    s === 3
      ? 'Emotionally waterproof (still has feelings, just carries an umbrella).'
      : s === 2
        ? 'Generally steady; occasional wobble is purely for plot.'
        : s === 1
          ? 'Reads between the lines… then reads between those lines too.'
          : 'May interpret “…” as a full documentary series.'

  const noveltyFlavor =
    n === 3
      ? 'Will say “we should” and then immediately open a map.'
      : n === 2
        ? 'Enjoys a little chaos, as a treat.'
        : n === 1
          ? 'Likes novelty in small, pre-approved doses.'
          : 'If it ain’t broke, don’t “fun” it.'

  if (archetype === 'Explorer') {
    return {
      warnings: [
        'Can turn “quick coffee” into a 6-hour side quest.',
        'Will befriend strangers, bartenders, and at least one dog.',
        'Says “yes” fast; reads details later.',
        noveltyFlavor,
        securityFlavor,
      ],
      bestConsumed: ['small groups', 'spontaneous plans', 'new neighborhoods', 'friends who can walk a lot'],
      doNot: ['trap in the same spot every Friday', 'schedule “fun” in 15-minute blocks'],
    }
  }

  if (archetype === 'Builder') {
    return {
      warnings: [
        'Requires calendar invite (bonus points for location + time).',
        'Friendship is built brick-by-brick; no speedruns.',
        '“Maybe” means “let me check my routine and my emotional bandwidth.”',
        noveltyFlavor,
        securityFlavor,
      ],
      bestConsumed: ['weekly rituals', '1-on-1 catchups', 'low-drama group chats', 'plans made before 9pm'],
      doNot: ['surprise 2am adventures', 'change the plan mid-plan'],
    }
  }

  if (archetype === 'Artist') {
    return {
      warnings: [
        'Feelings arrive in HD with surround sound.',
        'Can go from strangers → soulmates in 12 minutes.',
        'May overthink your “k” for 48 hours (with footnotes).',
        noveltyFlavor,
        securityFlavor,
      ],
      bestConsumed: ['creative hangouts', 'deep talks', 'low-pressure adventures', 'friends who text back like humans'],
      doNot: ['leave on read with zero context', 'force loud group icebreakers'],
    }
  }

  return {
    warnings: [
      'Arrives as an observer; leaves as ride-or-die (eventually).',
      'Trust is earned slowly; once in, you’re family.',
      'May rehearse conversations in the shower.',
      noveltyFlavor,
      securityFlavor,
    ],
    bestConsumed: ['familiar settings', 'predictable plans', 'small circles', 'gentle introductions'],
    doNot: ['spring last-minute plan changes', 'weaponize “just be spontaneous”'],
  }
}

export function computeSortingQuizResult(answers: SortingAnswers): SortingQuizResult {
  const { noveltyScore, securityScore } = scoreSortingQuiz(answers)
  const archetype = classifyArchetype(noveltyScore, securityScore)
  const warningLabel = makeWarningLabel(archetype, noveltyScore, securityScore)
  return { noveltyScore, securityScore, archetype, warningLabel }
}

