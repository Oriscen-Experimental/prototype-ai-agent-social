import type { CaseDefinition, CaseId, Group, GroupMember, Profile, VettingBadge } from '../types'

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

const tennisProfiles: Profile[] = [
  {
    id: 'u-chen-tennis',
    kind: 'human',
    name: '陈佑',
    presence: 'online',
    city: '成都',
    headline: '中级偏上：更爱拉球和脚步练习',
    score: 90,
    badges: [BADGES.photo, BADGES.id],
    about: ['一周 2–3 次', '更偏练基本功：正反手/发球', '能一起约球场也能临时拼场'],
    matchReasons: ['同城成都', '你想找人“练网球”，他偏训练型', '节奏稳定，适合长期球友'],
    topics: ['发球节奏', '上旋/切削', '脚步与还原'],
  },
  {
    id: 'u-luo-tennis',
    kind: 'human',
    name: '罗娜',
    presence: 'online',
    city: '成都',
    headline: '初学/新手：想找人一起把动作练顺',
    score: 85,
    badges: [BADGES.photo],
    about: ['周末上午比较有空', '更喜欢慢慢练，不着急打对抗', '也想找固定搭子互相监督'],
    matchReasons: ['同城成都', '你如果选“再看看/约一次试试”，她也很合适', '更偏轻松练习'],
    topics: ['握拍与引拍', '正手发力路径', '新手球拍/线的选择'],
  },
  {
    id: 'u-gao-tennis',
    kind: 'human',
    name: '高远',
    presence: 'online',
    city: '成都',
    headline: '进阶对抗：想找水平相近的练分',
    score: 82,
    badges: [BADGES.linkedin, BADGES.id],
    about: ['更偏实战：练分/对抗', '愿意一起做简单训练计划', '不介意你水平略低，但希望态度认真'],
    matchReasons: ['同城成都', '你如果选“想打对抗/练分”，他很匹配', '可一起提升'],
    topics: ['一发成功率', '接发站位', '关键分心态'],
  },
  {
    id: 'u-song-tennis',
    kind: 'human',
    name: '宋可',
    presence: 'offline',
    city: '成都',
    headline: '休闲网球：打着玩但也想进步一点',
    score: 78,
    badges: [BADGES.photo],
    about: ['更偏“快乐运动”', '可以打一次也可以长期', '喜欢结束后一起喝咖啡'],
    matchReasons: ['同城成都', '你如果选“不限水平”，他更容易匹配', '风格轻松'],
    topics: ['找球友的礼仪', '热身与拉伸', '打完怎么恢复'],
  },
  {
    id: 'u-wei-tennis',
    kind: 'human',
    name: '魏然',
    presence: 'offline',
    city: '成都',
    headline: '训练打卡型：固定时间固定球场',
    score: 80,
    badges: [BADGES.id],
    about: ['每周三/周六固定打卡', '更偏练多球/上手', '愿意一起约教练（mock）'],
    matchReasons: ['同城成都', '你如果选“长期球友”，他节奏稳定', '适合规律训练'],
    topics: ['多球训练', '体能与核心', '如何避免受伤'],
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
    title: '玉林路 · 9人标准局（欢乐但不乱）',
    city: '成都',
    location: '玉林路 · 某桌游店（mock）',
    availability: { status: 'open' },
    capacity: 9,
    memberCount: 7,
    level: '中级/熟人局风格：不喷人，讲逻辑',
    memberAvatars: ['7', '阿', 'K', 'R', 'E', 'Z', '小'],
    members: [
      member('m-a', '阿布', '发言清晰，喜欢盘逻辑', [BADGES.photo]),
      member('m-b', 'Kiki', '偏情绪流，玩得开心最重要', [BADGES.photo]),
      member('m-c', 'Rex', '狼人位胜率高（自称）', [BADGES.linkedin]),
      member('m-d', 'Evan', '更适合当预言家（自称）', [BADGES.id]),
      member('m-e', 'Zoe', '新手友好，不带节奏', [BADGES.photo]),
      member('m-f', '小白', '刚玩不久，想多练', []),
      member('m-g', '7号', '喜欢复盘，节奏稳', [BADGES.id]),
    ],
    notes: ['可直接加入（还差 2 人）', '支持你这边带 2 人一起进', '到店可出示报名码（mock）'],
  },
  {
    id: 'g-gaoxin-12',
    title: '高新区 · 12人进阶局（偏对抗）',
    city: '成都',
    location: '高新区 · 某桌游俱乐部（mock）',
    availability: { status: 'scheduled', startAt: nextTime(20, 0) },
    capacity: 12,
    memberCount: 10,
    level: '进阶：发言时间严格，偏复盘',
    memberAvatars: ['J', 'Q', 'W', 'L', 'M', 'N', 'T', 'Y', 'P', 'V'],
    members: [
      member('m-h', 'Juno', '规则熟，主持控场', [BADGES.linkedin]),
      member('m-i', 'Quinn', '发言强势，适合对抗局', [BADGES.id]),
      member('m-j', 'Wen', '女巫位细节多', [BADGES.photo]),
      member('m-k', 'Leo', '喜欢盘队形', [BADGES.photo]),
      member('m-l', 'Mina', '主打“少说废话”', []),
      member('m-m', 'Noah', '偏理工逻辑流', [BADGES.linkedin]),
      member('m-n', 'Tina', '新手勿入（但可以旁观）', [BADGES.id]),
      member('m-o', 'Yoyo', '发言节奏稳', [BADGES.photo]),
      member('m-p', 'Paco', '喜欢复盘记笔记', []),
      member('m-q', 'Vivi', '氛围组但不搅局', [BADGES.photo]),
    ],
    notes: ['当前不可直接加入：需要预约 20:00 开始', '你这边 2 人可一起预约占位（mock）'],
  },
  {
    id: 'g-jinniu-9-full',
    title: '金牛区 · 9人新手教学局（已满）',
    city: '成都',
    location: '金牛区 · 某咖啡桌游（mock）',
    availability: { status: 'full', startAt: nextTime(19, 30) },
    capacity: 9,
    memberCount: 9,
    level: '新手教学：会讲规则 + 复盘',
    memberAvatars: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'],
    members: [
      member('m-r', 'Ava', '带教：规则讲得很清楚', [BADGES.photo, BADGES.id]),
      member('m-s', 'Ben', '新手，来学习', []),
      member('m-t', 'Cici', '新手，来学习', [BADGES.photo]),
      member('m-u', 'Dio', '喜欢做笔记', []),
      member('m-v', 'Elle', '氛围友好', [BADGES.photo]),
      member('m-w', 'Finn', '偶尔玩', []),
      member('m-x', 'Gus', '新手', []),
      member('m-y', 'Hana', '喜欢复盘', [BADGES.id]),
      member('m-z', 'Ian', '新手', []),
    ],
    notes: ['已满员，可“候补”（mock）', '若有人临时取消会通知（mock）'],
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
    resultType: 'profiles',
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
    id: 'tennis',
    title: '一起练网球',
    exampleQuery: '我想找一个人一起练网球',
    assistantIntro: '好！为了更精准匹配球友，我需要你点选几个问题：',
    resultType: 'profiles',
    questions: [
      {
        key: 'gender',
        question: '性别有限制吗？',
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
        question: '长期还是打一次，还是先约一次再看看？',
        required: true,
        options: [
          { value: 'oneoff', label: '只打一次' },
          { value: 'longterm', label: '长期球友' },
          { value: 'try', label: '先约一次再看看' },
        ],
      },
      {
        key: 'myLevel',
        question: '你大概什么水平？',
        required: true,
        options: [
          { value: 'beginner', label: '新手/刚开始' },
          { value: 'casual', label: '休闲能对拉' },
          { value: 'intermediate', label: '中级（有一定稳定性）' },
          { value: 'advanced', label: '进阶/比赛向' },
        ],
      },
      {
        key: 'targetLevel',
        question: '你想找什么水平的球友？',
        required: true,
        options: [
          { value: 'any', label: '不限' },
          { value: 'similar', label: '水平相近' },
          { value: 'stronger', label: '比我强（带带我）' },
          { value: 'weaker', label: '比我弱（我来带）' },
        ],
      },
      {
        key: 'mode',
        question: '这次更想怎么打？',
        required: true,
        options: [
          { value: 'drills', label: '练基本功/对拉' },
          { value: 'match', label: '打对抗/练分' },
          { value: 'either', label: '都可以' },
        ],
      },
      {
        key: 'time',
        question: '你更方便什么时候？',
        required: true,
        options: [
          { value: 'weekday-night', label: '工作日晚上' },
          { value: 'weekend', label: '周末' },
          { value: 'daytime', label: '白天' },
          { value: 'any', label: '都行' },
        ],
      },
    ],
    profiles: tennisProfiles,
  },
  {
    id: 'werewolf',
    title: '玩狼人杀（找局/找队友）',
    exampleQuery: '我想找一个玩狼人杀的 我这边有两个人',
    assistantIntro: '收到～我先帮你把关键信息补齐，然后给你推荐可加入的“局”（group）：',
    resultType: 'groups',
    questions: [
      {
        key: 'partySize',
        question: '你这边一共几个人？',
        required: true,
        options: [
          { value: '1', label: '1 人' },
          { value: '2', label: '2 人' },
          { value: '3', label: '3 人' },
          { value: '4+', label: '4+ 人' },
        ],
      },
      {
        key: 'myLevel',
        question: '你大概什么水平？',
        required: true,
        options: [
          { value: 'new', label: '新手/刚玩' },
          { value: 'casual', label: '休闲（规则熟）' },
          { value: 'intermediate', label: '中级（会盘逻辑）' },
          { value: 'advanced', label: '进阶（对抗/复盘）' },
        ],
      },
      {
        key: 'targetLevel',
        question: '你想找什么水平的对手/局？',
        required: true,
        options: [
          { value: 'any', label: '不限' },
          { value: 'casual', label: '休闲欢乐' },
          { value: 'intermediate', label: '中级逻辑' },
          { value: 'advanced', label: '进阶对抗' },
        ],
      },
      {
        key: 'time',
        question: '你更方便什么时候开局？',
        required: true,
        options: [
          { value: 'tonight', label: '今晚' },
          { value: 'weekend', label: '周末' },
          { value: 'any', label: '都行' },
        ],
      },
      {
        key: 'mode',
        question: '你更喜欢哪种局？',
        required: true,
        options: [
          { value: 'standard', label: '标准局' },
          { value: 'teaching', label: '教学局' },
          { value: 'competitive', label: '对抗局' },
          { value: 'either', label: '都可以' },
        ],
      },
      {
        key: 'location',
        question: '地点偏好？',
        required: true,
        options: [
          { value: 'nearby', label: '离我近一点' },
          { value: 'any', label: '不限制' },
        ],
      },
    ],
    groups: werewolfGroups,
  },
  {
    id: 'comfort',
    title: '交个朋友（心情很差）',
    exampleQuery: '我想交个朋友 今天心情好差',
    assistantIntro: '我懂。为了更“接得住”你，我想确认几个点（直接点选即可）：',
    resultType: 'profiles',
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
