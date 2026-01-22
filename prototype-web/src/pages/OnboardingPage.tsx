import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding'
import type { OnboardingData } from '../types'

const GOALS = ['找搭子', '交朋友', '找恋爱', '找人一起学习/运动', '找人倾诉', '随便逛逛']
const INTERESTS = ['精酿/鸡尾酒', '咖啡', '电影', '音乐', '桌游', '运动', '旅行', '摄影', '读书', '美食', 'AI/科技']

export function OnboardingPage() {
  const navigate = useNavigate()
  const { complete } = useOnboarding()

  const [step, setStep] = useState(0)

  const [goals, setGoals] = useState<string[]>(['找搭子'])
  const [vibe, setVibe] = useState('轻松随意')

  const [name, setName] = useState('')
  const [gender, setGender] = useState('不想说')
  const [age, setAge] = useState('')
  const [city, setCity] = useState('成都')
  const [address, setAddress] = useState('')

  const [interests, setInterests] = useState<string[]>(['电影', '音乐'])

  const canNext = useMemo(() => {
    if (step === 0) return goals.length > 0 && vibe.length > 0
    if (step === 1) return name.trim().length > 0 && city.trim().length > 0
    if (step === 2) return interests.length > 0
    return false
  }, [step, goals, vibe, name, city, interests])

  const next = () => setStep((s) => Math.min(2, s + 1))
  const back = () => setStep((s) => Math.max(0, s - 1))

  const onFinish = () => {
    const data: OnboardingData = {
      name: name.trim(),
      gender,
      age: age.trim(),
      city: city.trim(),
      address: address.trim(),
      interests,
      goals,
      vibe,
    }
    complete(data)
    navigate('/app')
  }

  return (
    <div className="centerWrap">
      <div className="panel">
        <div className="panelHeader">
          <div className="h1">先快速了解你</div>
          <div className="muted">全部为原型 mock：只为展示基本 journey。</div>
        </div>

        <div className="stepper">
          <div className={step === 0 ? 'step stepActive' : 'step'}>1</div>
          <div className="stepLine" />
          <div className={step === 1 ? 'step stepActive' : 'step'}>2</div>
          <div className="stepLine" />
          <div className={step === 2 ? 'step stepActive' : 'step'}>3</div>
        </div>

        {step === 0 ? (
          <div className="stack">
            <div className="sectionTitle">你来这里主要想做什么？（可多选）</div>
            <div className="optionRow">
              {GOALS.map((g) => {
                const active = goals.includes(g)
                return (
                  <button
                    key={g}
                    type="button"
                    className={active ? 'chip chipActive' : 'chip'}
                    onClick={() =>
                      setGoals((prev) => (prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]))
                    }
                  >
                    {g}
                  </button>
                )
              })}
            </div>

            <div className="sectionTitle">你希望平台的氛围更像…</div>
            <div className="optionRow">
              {['轻松随意', '认真严肃', '高效直接'].map((v) => (
                <button
                  key={v}
                  type="button"
                  className={vibe === v ? 'chip chipActive' : 'chip'}
                  onClick={() => setVibe(v)}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="form">
            <label className="label">
              昵称 *
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="比如：小王" />
            </label>
            <div className="grid2">
              <label className="label">
                性别
                <select className="select" value={gender} onChange={(e) => setGender(e.target.value)}>
                  <option value="不想说">不想说</option>
                  <option value="男">男</option>
                  <option value="女">女</option>
                  <option value="其他">其他</option>
                </select>
              </label>
              <label className="label">
                年龄
                <input className="input" value={age} onChange={(e) => setAge(e.target.value)} placeholder="可选" />
              </label>
            </div>
            <label className="label">
              城市 *
              <input className="input" value={city} onChange={(e) => setCity(e.target.value)} placeholder="比如：成都" />
            </label>
            <label className="label">
              地址（可选）
              <input className="input" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="比如：高新区××路" />
            </label>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="stack">
            <div className="sectionTitle">你感兴趣的内容（可多选）</div>
            <div className="optionRow">
              {INTERESTS.map((i) => {
                const active = interests.includes(i)
                return (
                  <button
                    key={i}
                    type="button"
                    className={active ? 'chip chipActive' : 'chip'}
                    onClick={() =>
                      setInterests((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]))
                    }
                  >
                    {i}
                  </button>
                )
              })}
            </div>
            <div className="hint">这些信息只用于原型里展示，不会真的上传。</div>
          </div>
        ) : null}

        <div className="row spaceBetween">
          <div className="muted">Step {step + 1} / 3</div>
          <div className="row">
            {step > 0 ? (
              <button className="btn btnGhost" onClick={back} type="button">
                上一步
              </button>
            ) : null}
            {step < 2 ? (
              <button className="btn" onClick={next} type="button" disabled={!canNext}>
                下一步
              </button>
            ) : (
              <button className="btn" onClick={onFinish} type="button" disabled={!canNext}>
                进入原型
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

