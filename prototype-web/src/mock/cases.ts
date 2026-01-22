import type { CaseDefinition, CaseId, Profile, VettingBadge } from '../types'

const BADGES: Record<string, VettingBadge> = {
  photo: {
    id: 'photo',
    label: '真人照片验证',
    description: '已完成真人照片/活体校验（mock）',
  },
  linkedin: {
    id: 'linkedin',
    label: 'LinkedIn 验证',
    description: '已绑定 LinkedIn（mock）',
  },
  id: {
    id: 'id',
    label: '身份验证',
    description: '已完成基础身份验证（mock）',
  },
}

const drinkProfiles: Profile[] = [
  {
    id: 'u-han',
    kind: 'human',
    name: '韩森',
    presence: 'online',
    city: '成都',
    headline: '精酿爱好者，聊电影/城市散步也行',
    score: 88,
    badges: [BADGES.photo, BADGES.linkedin],
    about: ['周五下班常去玉林路', '不劝酒，偏轻松聊天局', '更喜欢小酒馆/精酿吧'],
    matchReasons: ['同城成都', '兴趣重合：精酿/电影', '你偏“长期酒友”，他也更喜欢固定搭子'],
    topics: ['最近看的电影', '成都小酒馆地图', '精酿口味：IPA vs 酸啤'],
  },
  {
    id: 'u-ling',
    kind: 'human',
    name: '林潇',
    presence: 'online',
    city: '成都',
    headline: '周末微醺派，喜欢爵士/桌游',
    score: 84,
    badges: [BADGES.photo],
    about: ['喜欢人少一点的吧台位', '能聊音乐，也能安静喝', '桌游新手友好'],
    matchReasons: ['同城成都', '你选择“不限性别/年龄”，她比较好约', '偏“一次性也OK”'],
    topics: ['爵士歌单交换', '桌游：阿瓦隆/卡坦', '微醺不醉的节奏'],
  },
  {
    id: 'u-zhou',
    kind: 'human',
    name: '周一凡',
    presence: 'online',
    city: '成都',
    headline: '社恐但想社交：找个一起喝一杯的人',
    score: 79,
    badges: [BADGES.id],
    about: ['可以先线上聊十分钟再决定见面', '更喜欢清吧', '在意边界与安全感'],
    matchReasons: ['同城成都', '你选择“先聊再约”，匹配他的节奏', '对“年龄限制”不敏感'],
    topics: ['社交焦虑怎么破', '清吧 vs 小酒馆', '周末活动清单'],
  },
  {
    id: 'u-xu',
    kind: 'human',
    name: '许晴',
    presence: 'offline',
    city: '成都',
    headline: '喜欢鸡尾酒，聊旅行/摄影',
    score: 82,
    badges: [BADGES.photo, BADGES.id],
    about: ['鸡尾酒入门：酸甜平衡', '旅行碎片：东南亚', '拍人像更有经验'],
    matchReasons: ['同城成都', '你偏“长期酒友”，她也愿意固定周末', '话题：旅行/摄影'],
    topics: ['鸡尾酒偏好', '旅行计划', '摄影器材与构图'],
  },
  {
    id: 'u-li',
    kind: 'human',
    name: '李响',
    presence: 'offline',
    city: '成都',
    headline: '无酒不欢（但不灌你），聊创业/产品',
    score: 74,
    badges: [BADGES.linkedin],
    about: ['偶尔应酬多', '喜欢聊产品与增长', '见面地点可以你定'],
    matchReasons: ['同城成都', '你选择“年龄不限”，他范围更广', '可聊工作/产品'],
    topics: ['创业踩坑', '产品增长', '应酬与边界'],
  },
]

const comfortProfiles: Profile[] = [
  {
    id: 'u-yan',
    kind: 'human',
    name: '严可',
    presence: 'online',
    city: '成都',
    headline: '擅长倾听：先把情绪放下再说事',
    score: 91,
    badges: [BADGES.photo, BADGES.id],
    about: ['做过心理学相关志愿者（mock）', '聊天偏温和，不评判', '可以陪你一起散步/吃点热的'],
    matchReasons: ['你输入“今天心情好差”', '你选择“需要被倾听”', '同城，见面/线上都可'],
    topics: ['最近让你难受的那件事', '把情绪“命名”', '小步行动：今晚怎么过'],
    healingReasons: [
      '他习惯先共情、再给建议，适合“情绪很满”的当下',
      '经历过类似低谷，知道“被理解”比“被指导”更重要',
      '节奏慢，不会逼你立刻变好',
    ],
  },
  {
    id: 'u-qin',
    kind: 'human',
    name: '秦然',
    presence: 'online',
    city: '成都',
    headline: '用行动疗愈：一起吃饭/散步/做点小事',
    score: 86,
    badges: [BADGES.linkedin],
    about: ['喜欢把大情绪拆成小步骤', '擅长陪伴式运动：散步/慢跑', '不强行安慰，更多陪你做事'],
    matchReasons: ['你选择“想转移注意力”', '同城成都', '你偏“今天就需要”'],
    topics: ['去哪里吃点热的', '轻松路线散步', '明天的一个小目标'],
    healingReasons: [
      '更偏“陪你行动”，能把情绪从脑内循环拉回现实',
      '不说鸡汤，提供可执行的小安排',
    ],
  },
  {
    id: 'u-tang',
    kind: 'human',
    name: '唐棠',
    presence: 'online',
    city: '成都',
    headline: '同理心强：你可以只说“我很难受”',
    score: 83,
    badges: [BADGES.photo],
    about: ['喜欢写日记/做情绪记录', '能陪你做“情绪复盘”', '也可以聊点轻松的'],
    matchReasons: ['你想“交个朋友”而不是找解决方案', '你选择“线上先聊”', '话题适配：情绪记录'],
    topics: ['今天发生了什么', '情绪记录怎么做', '喜欢的歌/电影当作缓冲'],
    healingReasons: [
      '允许你不完整表达，也能接住',
      '她会帮你把混乱的感受整理成可说的句子',
    ],
  },
  {
    id: 'u-wu',
    kind: 'human',
    name: '吴泽',
    presence: 'offline',
    city: '成都',
    headline: '理性支持：一起把问题拆开（如果你愿意）',
    score: 78,
    badges: [BADGES.id],
    about: ['更适合你准备好“聊原因/解决”时', '可以一起做决策表', '尊重隐私与边界'],
    matchReasons: ['你选择“需要建议”', '同城成都', '你偏“这周内慢慢聊”'],
    topics: ['困扰的核心是什么', '你能控制/不能控制的部分', '下一个小决定'],
    healingReasons: [
      '不急着安慰，而是帮你把“无力感”拆成可控项',
      '适合你想重新获得掌控感的阶段',
    ],
  },
]

const aiProfiles: Profile[] = [
  {
    id: 'ai-warm',
    kind: 'ai',
    name: '小暖 · AI',
    presence: 'online',
    city: '线上',
    headline: '共情陪伴型：先接住情绪，再慢慢走',
    score: 100,
    badges: [],
    about: ['更像一个温柔的朋友', '擅长共情复述与情绪命名', '会提醒你照顾身体与边界'],
    matchReasons: ['你选择“想和 AI 聊聊”', '你想要被理解与陪伴'],
    topics: ['情绪表达', '自我照顾清单', '安全感与边界'],
    aiNote: '这是 AI 账号（mock），不会代表真人。',
  },
  {
    id: 'ai-coach',
    kind: 'ai',
    name: 'Rational Coach · AI',
    presence: 'online',
    city: '线上',
    headline: '教练型：把目标拆小，给你下一步',
    score: 100,
    badges: [],
    about: ['擅长结构化提问', '会把复杂问题拆成可执行步骤', '可以用列表/优先级帮助你'],
    matchReasons: ['你选择“想和 AI 聊聊”', '你想要可执行的建议'],
    topics: ['目标拆解', '决策与取舍', '行动计划'],
    aiNote: '这是 AI 账号（mock），不会代表真人。',
  },
  {
    id: 'ai-creative',
    kind: 'ai',
    name: '灵感伙伴 · AI',
    presence: 'online',
    city: '线上',
    headline: '创意型：用故事、比喻、脑洞带你走出来',
    score: 100,
    badges: [],
    about: ['适合你想换个视角', '擅长写作/比喻/角色扮演', '可以陪你做“情绪转场”'],
    matchReasons: ['你选择“想和 AI 聊聊”', '你想快速换个心境'],
    topics: ['角色扮演', '写一封给自己的信', '把问题变成故事'],
    aiNote: '这是 AI 账号（mock），不会代表真人。',
  },
]

export const CASES: CaseDefinition[] = [
  {
    id: 'drink',
    title: '找人出去喝酒',
    exampleQuery: '我想找一个人出去喝酒',
    assistantIntro: '我可以帮你更快匹配。先补齐几个关键信息：',
    questions: [
      {
        key: 'gender',
        question: '男女有限制吗？',
        required: true,
        options: [
          { value: 'any', label: '不限' },
          { value: 'male', label: '男' },
          { value: 'female', label: '女' },
          { value: 'other', label: '其他/都可' },
        ],
      },
      {
        key: 'age',
        question: '年龄有限制吗？',
        required: true,
        options: [
          { value: 'any', label: '不限' },
          { value: '18-25', label: '18–25' },
          { value: '26-35', label: '26–35' },
          { value: '36-45', label: '36–45' },
          { value: '45+', label: '45+' },
        ],
      },
      {
        key: 'frequency',
        question: '一次性还是长期酒友？',
        required: true,
        options: [
          { value: 'oneoff', label: '一次性就行' },
          { value: 'longterm', label: '长期酒友' },
        ],
      },
    ],
    profiles: drinkProfiles,
  },
  {
    id: 'comfort',
    title: '交个朋友（心情很差）',
    exampleQuery: '我想交个朋友 今天心情好差',
    assistantIntro: '我懂。为了更“接得住”你，我想确认几个点（直接点选即可）：',
    questions: [
      {
        key: 'mode',
        question: '你更需要哪种支持？',
        required: true,
        options: [
          { value: 'listen', label: '被倾听/被理解' },
          { value: 'advice', label: '想要建议/一起拆解' },
          { value: 'distract', label: '转移注意力/做点事' },
        ],
      },
      {
        key: 'channel',
        question: '你希望怎么连接？',
        required: true,
        options: [
          { value: 'online', label: '先线上聊聊' },
          { value: 'offline', label: '可以线下见面' },
          { value: 'either', label: '都可以' },
        ],
      },
      {
        key: 'pace',
        question: '你希望的节奏？',
        required: true,
        options: [
          { value: 'now', label: '现在就需要' },
          { value: 'today', label: '今天内' },
          { value: 'week', label: '这周慢慢聊' },
        ],
      },
    ],
    profiles: comfortProfiles,
  },
  {
    id: 'talk-ai',
    title: '和 AI 聊聊',
    exampleQuery: '我想和AI聊聊',
    assistantIntro: '我给你 3 个不同风格的 AI（都明确是 AI）。选一个直接开聊：',
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
  return getCaseById(caseId).profiles.find((p) => p.id === profileId) ?? null
}

