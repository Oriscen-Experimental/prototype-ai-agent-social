import type { CaseDefinition, CaseId, Group, GroupMember, Profile, VettingBadge } from '../types'

const BADGES: Record<string, VettingBadge> = {
  photo: {
    id: 'photo',
    label: 'Photo Verified',
    description: 'Completed a photo/liveness check (mock).',
  },
  linkedin: {
    id: 'linkedin',
    label: 'LinkedIn Verified',
    description: 'LinkedIn connected (mock).',
  },
  id: {
    id: 'id',
    label: 'ID Verified',
    description: 'Basic identity verification (mock).',
  },
}

const drinkProfiles: Profile[] = [
  {
    id: 'u-han',
    kind: 'human',
    name: 'Sam',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Craft beer nerd—also down for movies or a city walk',
    score: 88,
    badges: [BADGES.photo, BADGES.linkedin],
    about: ['Usually grabs a drink in Hayes Valley', 'No pressure / no shot culture', 'Prefers breweries and chill bars'],
    matchReasons: ['Same city (SF)', 'Overlapping interests: beer + movies', 'You want a regular buddy—same vibe'],
    topics: ['What you watched recently', 'Best breweries in SF', 'IPA vs sour beers'],
  },
  {
    id: 'u-ling',
    kind: 'human',
    name: 'Lena',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Weekend “one or two drinks” person—into jazz and board games',
    score: 84,
    badges: [BADGES.photo],
    about: ['Likes quieter bar seats', 'Can chat music—or just hang', 'Board-game-friendly (newbies welcome)'],
    matchReasons: ['Same city (SF)', 'You picked “no gender/age limits”', 'You’re okay with a one-off hang'],
    topics: ['Jazz playlist swap', 'Board games to try', 'How to pace a night out'],
  },
  {
    id: 'u-zhou',
    kind: 'human',
    name: 'Jordan',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Socially anxious but trying—looking for a low-pressure drink buddy',
    score: 79,
    badges: [BADGES.id],
    about: ['Prefers a 10-minute chat before meeting', 'Likes cocktail bars', 'Cares about boundaries and safety'],
    matchReasons: ['Same city (SF)', 'You’re open to “chat first, then meet”', 'Not picky about age'],
    topics: ['Social anxiety hacks', 'Cocktail bars vs breweries', 'Weekend plans'],
  },
  {
    id: 'u-xu',
    kind: 'human',
    name: 'Maya',
    presence: 'offline',
    city: 'San Francisco',
    headline: 'Cocktail fan—happy to talk travel and photography',
    score: 82,
    badges: [BADGES.photo, BADGES.id],
    about: ['Likes “balanced” cocktails (not too sweet)', 'Recent trips: Mexico / Japan', 'Shoots portraits on weekends'],
    matchReasons: ['Same city (SF)', 'You want a regular buddy—she’s open to weekly plans', 'Shared topics: travel + photography'],
    topics: ['Cocktail preferences', 'Next trip ideas', 'Camera gear and composition'],
  },
  {
    id: 'u-li',
    kind: 'human',
    name: 'Ethan',
    presence: 'offline',
    city: 'San Francisco',
    headline: 'Down for a drink (no pressure) — happy to talk startups/product',
    score: 74,
    badges: [BADGES.linkedin],
    about: ['Sometimes has work happy hours', 'Likes product & growth chats', 'You pick the place'],
    matchReasons: ['Same city (SF)', 'You picked “age doesn’t matter”', 'Shared topic: work/product'],
    topics: ['Startup lessons', 'Product growth', 'Work-life boundaries'],
  },
]

const tennisProfiles: Profile[] = [
  {
    id: 'u-chen-tennis',
    kind: 'human',
    name: 'Chris',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Upper-intermediate—loves rallying and footwork drills',
    score: 90,
    badges: [BADGES.photo, BADGES.id],
    about: ['Plays 2–3x/week', 'Prefers drilling: groundstrokes + serve', 'Can book courts or drop-in'],
    matchReasons: ['Same city (SF)', 'You want a tennis partner—he’s training-oriented', 'Steady schedule (good for recurring)'],
    topics: ['Serve rhythm', 'Topspin vs slice', 'Footwork and recovery'],
  },
  {
    id: 'u-luo-tennis',
    kind: 'human',
    name: 'Nora',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Beginner—wants to groove the basics with someone consistent',
    score: 85,
    badges: [BADGES.photo],
    about: ['Free on weekend mornings', 'Likes slow drills—no pressure', 'Would love a regular accountability buddy'],
    matchReasons: ['Same city (SF)', 'If you picked “try once and see”, she’s a great fit', 'Low-pressure practice style'],
    topics: ['Grip and takeback', 'Forehand swing path', 'Beginner racket/strings'],
  },
  {
    id: 'u-gao-tennis',
    kind: 'human',
    name: 'Miles',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Competitive—looking for similar level to play points',
    score: 82,
    badges: [BADGES.linkedin, BADGES.id],
    about: ['Prefers match play: points + tiebreaks', 'Open to a simple training plan', 'Okay if you’re slightly lower—but wants effort'],
    matchReasons: ['Same city (SF)', 'If you picked “play points”, he’s a strong match', 'Could improve together'],
    topics: ['First-serve %', 'Return positioning', 'Big-point mindset'],
  },
  {
    id: 'u-song-tennis',
    kind: 'human',
    name: 'Taylor',
    presence: 'offline',
    city: 'San Francisco',
    headline: 'Casual tennis—fun first, but wants to improve a bit',
    score: 78,
    badges: [BADGES.photo],
    about: ['“Happy workout” energy', 'Open to one-off or recurring', 'Likes grabbing coffee after'],
    matchReasons: ['Same city (SF)', 'If you picked “any level”, this fits well', 'Easygoing style'],
    topics: ['Tennis partner etiquette', 'Warmups and stretching', 'Recovery tips'],
  },
  {
    id: 'u-wei-tennis',
    kind: 'human',
    name: 'Avery',
    presence: 'offline',
    city: 'San Francisco',
    headline: 'Routine-driven: same time, same courts',
    score: 80,
    badges: [BADGES.id],
    about: ['Usually Wed/Sat', 'Likes repetition and reps', 'Open to splitting a coach (mock)'],
    matchReasons: ['Same city (SF)', 'If you picked “long-term”, this is stable', 'Great for consistent training'],
    topics: ['Drill ideas', 'Fitness and core work', 'Avoiding injuries'],
  },
]

function member(id: string, name: string, headline: string, badges: VettingBadge[]): GroupMember {
  return { id, name, headline, badges }
}

function nextTime(hour: number, minute: number) {
  const d = new Date()
  d.setHours(hour, minute, 0, 0)
  if (d.getTime() < Date.now() - 5 * 60 * 1000) d.setDate(d.getDate() + 1)
  return d.getTime()
}

const werewolfGroups: Group[] = [
  {
    id: 'g-yulin-9',
    title: 'Mission District · 9-player Mafia/Werewolf (friendly table)',
    city: 'San Francisco',
    location: 'Mission District · board game cafe (mock)',
    availability: { status: 'open' },
    capacity: 9,
    memberCount: 7,
    level: 'Intermediate: friendly table, logic-forward, no toxicity',
    memberAvatars: ['S', 'K', 'R', 'E', 'Z', 'A', 'J'],
    members: [
      member('m-a', 'Sam', 'Clear speaker—likes to reason out loud', [BADGES.photo]),
      member('m-b', 'Kiki', 'Plays for fun, keeps the vibe light', [BADGES.photo]),
      member('m-c', 'Rex', 'Claims a “high win rate” as wolf', [BADGES.linkedin]),
      member('m-d', 'Evan', 'Self-declared “best seer”', [BADGES.id]),
      member('m-e', 'Zoe', 'Newbie-friendly, doesn’t hard-push', [BADGES.photo]),
      member('m-f', 'Alex', 'New-ish, wants more reps', []),
      member('m-g', 'Jules', 'Likes post-game debriefs', [BADGES.id]),
    ],
    notes: ['You can join now (2 spots left)', 'Your party can join together (mock)', 'Show a check-in code at the door (mock)'],
  },
  {
    id: 'g-gaoxin-12',
    title: 'SoMa · 12-player competitive Mafia/Werewolf (scheduled)',
    city: 'San Francisco',
    location: 'SoMa · tabletop club (mock)',
    availability: { status: 'scheduled', startAt: nextTime(20, 0) },
    capacity: 12,
    memberCount: 10,
    level: 'Advanced: timed turns, heavier on debriefs',
    memberAvatars: ['J', 'Q', 'W', 'L', 'M', 'N', 'T', 'Y', 'P', 'V'],
    members: [
      member('m-h', 'Juno', 'Strong host—keeps pace and rules tight', [BADGES.linkedin]),
      member('m-i', 'Quinn', 'Confident speaker—good for competitive tables', [BADGES.id]),
      member('m-j', 'Wen', 'Detail-oriented, tracks claims', [BADGES.photo]),
      member('m-k', 'Leo', 'Formation/positioning talk', [BADGES.photo]),
      member('m-l', 'Mina', '“No fluff” style', []),
      member('m-m', 'Noah', 'Analytical / logic-heavy', [BADGES.linkedin]),
      member('m-n', 'Tina', 'Not beginner-friendly (but you can spectate)', [BADGES.id]),
      member('m-o', 'Yoyo', 'Steady pace', [BADGES.photo]),
      member('m-p', 'Paco', 'Takes notes, loves debriefs', []),
      member('m-q', 'Vivi', 'High energy, not disruptive', [BADGES.photo]),
    ],
    notes: ['Not open to drop-in: RSVP for 8:00 PM', 'Your party can reserve together (mock)'],
  },
  {
    id: 'g-jinniu-9-full',
    title: 'Oakland · 9-player beginner table (full)',
    city: 'Bay Area',
    location: 'Downtown Oakland · cafe game night (mock)',
    availability: { status: 'full', startAt: nextTime(19, 30) },
    capacity: 9,
    memberCount: 9,
    level: 'Beginner: rules walkthrough + light debrief',
    memberAvatars: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'],
    members: [
      member('m-r', 'Ava', 'Facilitator: explains rules clearly', [BADGES.photo, BADGES.id]),
      member('m-s', 'Ben', 'New player—learning', []),
      member('m-t', 'Cici', 'New player—learning', [BADGES.photo]),
      member('m-u', 'Dio', 'Likes taking notes', []),
      member('m-v', 'Elle', 'Friendly vibes', [BADGES.photo]),
      member('m-w', 'Finn', 'Plays occasionally', []),
      member('m-x', 'Gus', 'New player', []),
      member('m-y', 'Hana', 'Likes debriefs', [BADGES.id]),
      member('m-z', 'Ian', 'New player', []),
    ],
    notes: ['Full—join the waitlist (mock)', 'You’ll be notified if someone drops (mock)'],
  },
]

const comfortProfiles: Profile[] = [
  {
    id: 'u-yan',
    kind: 'human',
    name: 'Kai',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Great listener—starts with feelings, not fixing',
    score: 91,
    badges: [BADGES.photo, BADGES.id],
    about: ['Did mental health volunteering (mock)', 'Gentle, non-judgmental style', 'Can do a short walk or grab something warm'],
    matchReasons: ['You said “I feel awful today”', 'You picked “I want to be heard”', 'Same city—online or in-person'],
    topics: ['What’s weighing on you', 'Naming the emotion', 'Small steps for tonight'],
    healingReasons: [
      'Leads with empathy before advice—good when emotions are intense',
      'Has been through a similar low and knows “being understood” matters',
      'Slow pace—won’t rush you to “feel better”',
    ],
  },
  {
    id: 'u-qin',
    kind: 'human',
    name: 'Riley',
    presence: 'online',
    city: 'San Francisco',
    headline: 'Action-based support: food, a walk, doing one small thing',
    score: 86,
    badges: [BADGES.linkedin],
    about: ['Breaks big feelings into tiny steps', 'Good at companion walks/light runs', 'Less pep talk, more doing'],
    matchReasons: ['You picked “distraction / doing something”', 'Same city (SF)', 'You want it today'],
    topics: ['A comforting meal spot', 'Easy walking route', 'One small goal for tomorrow'],
    healingReasons: [
      '“Do it together” energy can pull you out of spiraling thoughts',
      'No clichés—just practical, doable plans',
    ],
  },
  {
    id: 'u-tang',
    kind: 'human',
    name: 'Taylor',
    presence: 'online',
    city: 'San Francisco',
    headline: 'High empathy—you can start with “I’m hurting” and that’s enough',
    score: 83,
    badges: [BADGES.photo],
    about: ['Journals and tracks moods', 'Can help you unpack feelings gently', 'Also happy to chat about lighter stuff'],
    matchReasons: ['You want a friend, not a fix', 'You picked “online first”', 'Topics fit: mood tracking'],
    topics: ['What happened today', 'How to track moods', 'Music/movies as a soft landing'],
    healingReasons: [
      'Can hold space even if you can’t fully articulate it yet',
      'Helps turn messy feelings into words',
    ],
  },
  {
    id: 'u-wu',
    kind: 'human',
    name: 'Morgan',
    presence: 'offline',
    city: 'San Francisco',
    headline: 'Practical support: break the problem down (if you want)',
    score: 78,
    badges: [BADGES.id],
    about: ['Best when you’re ready for causes/solutions', 'Can make a simple decision matrix', 'Respects privacy and boundaries'],
    matchReasons: ['You picked “advice / break it down”', 'Same city (SF)', 'You’re okay taking it slower this week'],
    topics: ['What’s the core issue', 'What you can/can’t control', 'The next small decision'],
    healingReasons: [
      'Helps convert helplessness into controllable pieces',
      'Good when you want to regain a sense of agency',
    ],
  },
]

const aiProfiles: Profile[] = [
  {
    id: 'ai-warm',
    kind: 'ai',
    name: 'Ava · AI',
    presence: 'online',
    city: 'Online',
    headline: 'Warm companion: starts with empathy and presence',
    score: 100,
    badges: [],
    about: ['More like a kind friend', 'Good at reflecting and naming emotions', 'Will remind you about self-care and boundaries'],
    matchReasons: ['You picked “talk to an AI”', 'You want understanding and company'],
    topics: ['Emotions', 'Self-care checklist', 'Safety and boundaries'],
    aiNote: 'This is an AI profile (mock), not a real person.',
  },
  {
    id: 'ai-coach',
    kind: 'ai',
    name: 'Rational Coach · AI',
    presence: 'online',
    city: 'Online',
    headline: 'Coach mode: break goals down and pick a next step',
    score: 100,
    badges: [],
    about: ['Structured questions', 'Turns messy problems into actionable steps', 'Can help with lists and priorities'],
    matchReasons: ['You picked “talk to an AI”', 'You want actionable advice'],
    topics: ['Goal breakdown', 'Decisions and tradeoffs', 'Action plans'],
    aiNote: 'This is an AI profile (mock), not a real person.',
  },
  {
    id: 'ai-creative',
    kind: 'ai',
    name: 'Creative Muse · AI',
    presence: 'online',
    city: 'Online',
    headline: 'Creative mode: stories, metaphors, and fresh perspectives',
    score: 100,
    badges: [],
    about: ['Great when you want a new angle', 'Writing/metaphors/role-play', 'Helps you “shift scenes” emotionally'],
    matchReasons: ['You picked “talk to an AI”', 'You want a quick perspective shift'],
    topics: ['Role-play', 'Write a letter to yourself', 'Turn it into a story'],
    aiNote: 'This is an AI profile (mock), not a real person.',
  },
]

export const CASES: CaseDefinition[] = [
  {
    id: 'drink',
    title: 'Find a drink buddy',
    exampleQuery: 'I want to find someone to grab a drink',
    assistantIntro: 'I can match faster—tap a few details first:',
    resultType: 'profiles',
    questions: [
      {
        key: 'gender',
        question: 'Any gender preference?',
        required: true,
        options: [
          { value: 'any', label: 'No preference' },
          { value: 'male', label: 'Men' },
          { value: 'female', label: 'Women' },
          { value: 'other', label: 'Any / other' },
        ],
      },
      {
        key: 'age',
        question: 'Any age preference?',
        required: true,
        options: [
          { value: 'any', label: 'No preference' },
          { value: '18-25', label: '18–25' },
          { value: '26-35', label: '26–35' },
          { value: '36-45', label: '36–45' },
          { value: '45+', label: '45+' },
        ],
      },
      {
        key: 'frequency',
        question: 'One-time hang or a regular buddy?',
        required: true,
        options: [
          { value: 'oneoff', label: 'One-time' },
          { value: 'longterm', label: 'Regular buddy' },
        ],
      },
    ],
    profiles: drinkProfiles,
  },
  {
    id: 'tennis',
    title: 'Find a tennis partner',
    exampleQuery: 'I want a tennis partner (I want to practice)',
    assistantIntro: 'Great—tap a few details so I can match the right partner:',
    resultType: 'profiles',
    questions: [
      {
        key: 'gender',
        question: 'Any gender preference?',
        required: true,
        options: [
          { value: 'any', label: 'No preference' },
          { value: 'male', label: 'Men' },
          { value: 'female', label: 'Women' },
          { value: 'other', label: 'Any / other' },
        ],
      },
      {
        key: 'age',
        question: 'Any age preference?',
        required: true,
        options: [
          { value: 'any', label: 'No preference' },
          { value: '18-25', label: '18–25' },
          { value: '26-35', label: '26–35' },
          { value: '36-45', label: '36–45' },
          { value: '45+', label: '45+' },
        ],
      },
      {
        key: 'frequency',
        question: 'Long-term, one-time, or try once and see?',
        required: true,
        options: [
          { value: 'oneoff', label: 'One-time' },
          { value: 'longterm', label: 'Long-term' },
          { value: 'try', label: 'Try once' },
        ],
      },
      {
        key: 'myLevel',
        question: 'Roughly your level?',
        required: true,
        options: [
          { value: 'beginner', label: 'Beginner' },
          { value: 'casual', label: 'Casual (can rally a bit)' },
          { value: 'intermediate', label: 'Intermediate' },
          { value: 'advanced', label: 'Advanced / competitive' },
        ],
      },
      {
        key: 'targetLevel',
        question: 'What level partner do you want?',
        required: true,
        options: [
          { value: 'any', label: 'No preference' },
          { value: 'similar', label: 'Similar level' },
          { value: 'stronger', label: 'Stronger (help me level up)' },
          { value: 'weaker', label: 'Weaker (I can help)' },
        ],
      },
      {
        key: 'mode',
        question: 'What kind of session?',
        required: true,
        options: [
          { value: 'drills', label: 'Rally / drills' },
          { value: 'match', label: 'Play points' },
          { value: 'either', label: 'Either' },
        ],
      },
      {
        key: 'time',
        question: 'When works best?',
        required: true,
        options: [
          { value: 'weekday-night', label: 'Weeknights' },
          { value: 'weekend', label: 'Weekends' },
          { value: 'daytime', label: 'Daytime' },
          { value: 'any', label: 'Anytime' },
        ],
      },
    ],
    profiles: tennisProfiles,
  },
  {
    id: 'werewolf',
    title: 'Play Mafia/Werewolf (find a table)',
    exampleQuery: "I want to play Werewolf/Mafia. I've got two people.",
    assistantIntro: "Got it—tap a few details and I'll suggest games you can join (groups):",
    resultType: 'groups',
    questions: [
      {
        key: 'partySize',
        question: 'How many people are in your party?',
        required: true,
        options: [
          { value: '1', label: '1' },
          { value: '2', label: '2' },
          { value: '3', label: '3' },
          { value: '4+', label: '4+' },
        ],
      },
      {
        key: 'myLevel',
        question: 'Your experience level?',
        required: true,
        options: [
          { value: 'new', label: 'New' },
          { value: 'casual', label: 'Casual (rules are familiar)' },
          { value: 'intermediate', label: 'Intermediate (logic-focused)' },
          { value: 'advanced', label: 'Advanced (competitive / debrief)' },
        ],
      },
      {
        key: 'targetLevel',
        question: 'What kind of table do you want?',
        required: true,
        options: [
          { value: 'any', label: 'No preference' },
          { value: 'casual', label: 'Casual / fun' },
          { value: 'intermediate', label: 'Intermediate / logic' },
          { value: 'advanced', label: 'Advanced / competitive' },
        ],
      },
      {
        key: 'time',
        question: 'When do you want to play?',
        required: true,
        options: [
          { value: 'tonight', label: 'Tonight' },
          { value: 'weekend', label: 'Weekend' },
          { value: 'any', label: 'Anytime' },
        ],
      },
      {
        key: 'mode',
        question: 'What style do you prefer?',
        required: true,
        options: [
          { value: 'standard', label: 'Standard' },
          { value: 'teaching', label: 'Beginner / teaching' },
          { value: 'competitive', label: 'Competitive' },
          { value: 'either', label: 'Either' },
        ],
      },
      {
        key: 'location',
        question: 'Location preference?',
        required: true,
        options: [
          { value: 'nearby', label: 'Close to me' },
          { value: 'any', label: 'No preference' },
        ],
      },
    ],
    groups: werewolfGroups,
  },
  {
    id: 'comfort',
    title: "Make a friend (I'm having a rough day)",
    exampleQuery: "I want to make a friend. I'm feeling really down today.",
    assistantIntro: 'I hear you. Tap a few options so I can match you with the right kind of support:',
    resultType: 'profiles',
    questions: [
      {
        key: 'mode',
        question: 'What kind of support do you want right now?',
        required: true,
        options: [
          { value: 'listen', label: 'Someone to listen' },
          { value: 'advice', label: 'Advice / break it down' },
          { value: 'distract', label: 'Distraction / do something' },
        ],
      },
      {
        key: 'channel',
        question: 'How do you want to connect?',
        required: true,
        options: [
          { value: 'online', label: 'Chat online first' },
          { value: 'offline', label: 'Meet in person' },
          { value: 'either', label: 'Either' },
        ],
      },
      {
        key: 'pace',
        question: 'What pace do you want?',
        required: true,
        options: [
          { value: 'now', label: 'Right now' },
          { value: 'today', label: 'Today' },
          { value: 'week', label: 'This week' },
        ],
      },
    ],
    profiles: comfortProfiles,
  },
  {
    id: 'talk-ai',
    title: 'Talk to an AI',
    exampleQuery: 'I want to talk to an AI',
    assistantIntro: 'Here are 3 different AI styles (clearly labeled as AI). Pick one to start chatting:',
    resultType: 'profiles',
    profiles: aiProfiles,
  },
]

export function getCase(caseId: string | undefined): CaseDefinition | null {
  return CASES.find((c) => c.id === caseId) ?? null
}

export function getCaseById(caseId: CaseId): CaseDefinition {
  const found = CASES.find((c) => c.id === caseId)
  if (!found) throw new Error(`Unknown caseId: ${caseId}`)
  return found
}

export function findProfile(caseId: CaseId, profileId: string): Profile | null {
  const c = getCaseById(caseId)
  if (c.resultType !== 'profiles') return null
  return c.profiles.find((p) => p.id === profileId) ?? null
}
