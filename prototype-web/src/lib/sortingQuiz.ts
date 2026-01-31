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

export function makeWarningLabel(
  archetype: SocialArchetype,
  noveltyScore: number,
  securityScore: number,
  answers: SortingAnswers
): WarningLabel {
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
        answers.noResponse === 'C' ? 'If you don’t reply fast, this unit may refresh notifications like it’s cardio.' : 'Will assume good intent first (then keep moving).',
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
        answers.awkwardWave === 'A' ? 'Stores awkward moments in the cloud for later replay.' : 'Recovers from awkwardness quickly (patch deployed).',
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
        answers.noResponse === 'B' ? 'May run a full post-text “did I sound weird?” audit.' : 'Reads tone like a detective (sometimes too well).',
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
      answers.travel === 'A' ? 'Prefers a clear plan (and will secretly love you for making one).' : 'Will follow the vibe—just don’t call it “random”.',
      noveltyFlavor,
      securityFlavor,
    ],
    bestConsumed: ['familiar settings', 'predictable plans', 'small circles', 'gentle introductions'],
    doNot: ['spring last-minute plan changes', 'weaponize “just be spontaneous”'],
  }
}

function pickModelName(archetype: SocialArchetype): string {
  if (archetype === 'Explorer') return 'Side-Quest Navigator 3000'
  if (archetype === 'Builder') return 'Calendar-First Companion 2.0'
  if (archetype === 'Artist') return 'Feelings-in-HD Edition'
  return 'Loyalty Sentinel (Quiet Mode)'
}

function computeNutritionFacts(archetype: SocialArchetype, noveltyScore: number, securityScore: number, answers: SortingAnswers): NutritionFacts {
  const n = clampScore(noveltyScore)
  const s = clampScore(securityScore)

  const advanceNoticeHours = Math.max(4, Math.min(96, 8 + (3 - n) * 18 + (2 - s) * 6))
  const deepConversation = Math.max(10, Math.min(100, 60 + n * 8 + (2 - s) * 10))
  const spontaneity = Math.max(0, Math.min(100, 10 + n * 25 + (s >= 2 ? 10 : 0)))
  const smallTalkTolerance = Math.max(0, Math.min(100, 70 - deepConversation + (s >= 2 ? 8 : 0)))

  const drainIndex = (3 - s) * 1.1 + (3 - n) * 0.6
  const energyDrainPerHour = drainIndex >= 3.2 ? 'HIGH' : drainIndex >= 2 ? 'MED' : 'LOW'
  const recoveryHours = Math.max(4, Math.min(72, 6 + (3 - s) * 14 + (3 - n) * 6))

  const ingredientsBits: string[] = []
  if (answers.travel === 'B') ingredientsBits.push('detours')
  if (answers.restaurant === 'A') ingredientsBits.push('comfort choices')
  if (answers.noResponse === 'B') ingredientsBits.push('text re-reading')
  if (answers.noResponse === 'C') ingredientsBits.push('notification refresh')
  if (answers.awkwardWave === 'A') ingredientsBits.push('post-event replay')
  if (!ingredientsBits.length) ingredientsBits.push('good intentions')

  const containsBits: string[] = []
  if (s <= 1) containsBits.push('overthinking')
  if (n >= 2) containsBits.push('curiosity')
  if (answers.noResponse === 'D') containsBits.push('healthy boundaries')
  if (!containsBits.length) containsBits.push('quiet confidence')

  const mayContainBits: string[] = []
  if (archetype === 'Explorer') mayContainBits.push('impromptu group selfies')
  if (archetype === 'Builder') mayContainBits.push('spreadsheets (lovingly)')
  if (archetype === 'Artist') mayContainBits.push('unexpected depth')
  if (archetype === 'Guardian') mayContainBits.push('ride-or-die loyalty')

  return {
    servingSize: '1 hangout',
    servingsPerWeek: archetype === 'Explorer' ? '3–5 (if the vibes are right)' : archetype === 'Artist' ? '2–3 (plus a lot of thinking)' : archetype === 'Builder' ? '1–2 (scheduled)' : '1–2 (trusted circle only)',
    amountPerServing: [
      { label: 'Advance Notice Required', value: `${advanceNoticeHours} hrs` },
      { label: 'Deep Conversation', value: `${deepConversation}%` },
      { label: 'Small Talk Tolerance', value: `${smallTalkTolerance}%` },
      { label: 'Spontaneity', value: `${spontaneity}%` },
    ],
    energyDrainPerHour,
    recoveryTimeNeeded: `${recoveryHours} hrs`,
    ingredients: ingredientsBits.join(', '),
    contains: containsBits.join(', '),
    mayContain: mayContainBits.join(', '),
  }
}

function computeUserManual(archetype: SocialArchetype, noveltyScore: number, securityScore: number, answers: SortingAnswers): UserManual {
  const n = clampScore(noveltyScore)
  const s = clampScore(securityScore)

  const groupSize = archetype === 'Explorer' ? '2–6 people' : archetype === 'Artist' ? '1–3 people' : '1–4 people'
  const duration = archetype === 'Explorer' ? '2–5 hours' : archetype === 'Builder' ? '1.5–3 hours' : '2–3 hours'
  const environment =
    archetype === 'Explorer'
      ? 'new spots, walkable neighborhoods'
      : archetype === 'Artist'
        ? 'cozy cafés, low-noise corners'
        : archetype === 'Builder'
          ? 'known venues, clear plans'
          : 'familiar places, low-pressure settings'

  const quickStart: string[] = []
  if (archetype === 'Explorer') {
    quickStart.push('Offer a plan with 2 choices (adventure + fallback).')
    quickStart.push('Be ready to pivot when a cool side quest appears.')
    quickStart.push('Let them talk to strangers; it’s part of the operating system.')
    quickStart.push('Hydrate. This unit forgets time exists.')
  } else if (archetype === 'Builder') {
    quickStart.push('Send a calendar invite with time + location.')
    quickStart.push('Confirm the plan once (not seven times).')
    quickStart.push('Start with something familiar; earn novelty slowly.')
    quickStart.push('Respect the “wrap by X pm” boundary (it’s real).')
  } else if (archetype === 'Artist') {
    quickStart.push('Use full sentences. Warm tone. No “k”.')
    quickStart.push('Pick a vibe-forward place (lighting matters).')
    quickStart.push('Suggest 1–2 real topics (not small-talk trivia).')
    quickStart.push('If they go quiet, assume processing—not disinterest.')
  } else {
    quickStart.push('Start with a gentle invite (details included).')
    quickStart.push('Introduce new people slowly, like adding spice to soup.')
    quickStart.push('Follow through on what you say (trust is the fuel).')
    quickStart.push('Don’t force spontaneity; offer options instead.')
  }

  const troubleshooting: Array<{ issue: string; fix: string }> = []
  troubleshooting.push({
    issue: '“No reply for a few hours”',
    fix:
      answers.noResponse === 'A'
        ? 'Do nothing. This unit is already calm about it.'
        : answers.noResponse === 'D'
          ? 'Do nothing. Let them respond on their timeline.'
          : 'Add context (“no rush”) and step away from the refresh button.',
  })
  troubleshooting.push({
    issue: '“Awkward moment happened”',
    fix: answers.awkwardWave === 'B' ? 'Laugh, move on, never mention it again.' : 'Name it lightly, then change topic. Do not replay in 4K.',
  })
  troubleshooting.push({
    issue: '“Plan feels too random”',
    fix: n >= 2 ? 'Keep the chaos, but add one anchor (time OR place).' : 'Add structure: time, place, and a clear end time.',
  })

  const warranty =
    archetype === 'Guardian'
      ? 'Warranty: loyalty backed by a surprisingly long memory.'
      : archetype === 'Builder'
        ? 'Warranty: consistent friendship, limited-time drama support.'
        : archetype === 'Artist'
          ? 'Warranty: emotional depth included. Handle with care.'
          : 'Warranty: good stories guaranteed; receipts may be lost.'

  return {
    modelName: pickModelName(archetype),
    quickStart,
    optimalOperatingConditions: [
      `Group size: ${groupSize}`,
      `Duration: ${duration}`,
      `Environment: ${environment}`,
      `Vibe: ${s >= 2 ? 'steady + easy' : 'gentle + reassuring'} (no pressure)`,
    ],
    troubleshooting,
    warranty,
  }
}

export function computeSortingQuizResult(answers: SortingAnswers): SortingQuizResult {
  const { noveltyScore, securityScore } = scoreSortingQuiz(answers)
  const archetype = classifyArchetype(noveltyScore, securityScore)
  const warningLabel = makeWarningLabel(archetype, noveltyScore, securityScore, answers)
  const nutritionFacts = computeNutritionFacts(archetype, noveltyScore, securityScore, answers)
  const userManual = computeUserManual(archetype, noveltyScore, securityScore, answers)
  return { noveltyScore, securityScore, archetype, warningLabel, nutritionFacts, userManual }
}
