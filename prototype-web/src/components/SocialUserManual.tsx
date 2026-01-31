import type { UserManual } from '../lib/sortingQuiz'

export function SocialUserManual(props: { manual: UserManual; archetype: string }) {
  const lines: string[] = []
  lines.push('USER MANUAL')
  lines.push(`Model: ${props.manual.modelName}`)
  lines.push('--------------------------------')
  lines.push('')
  lines.push('QUICK START GUIDE')
  props.manual.quickStart.forEach((s, i) => lines.push(`${i + 1}. ${s}`))
  lines.push('')
  lines.push('--------------------------------')
  lines.push('')
  lines.push('OPTIMAL OPERATING CONDITIONS')
  props.manual.optimalOperatingConditions.forEach((s) => lines.push(`• ${s}`))
  lines.push('')
  lines.push('--------------------------------')
  lines.push('')
  lines.push('TROUBLESHOOTING')
  for (const t of props.manual.troubleshooting) {
    lines.push(`"${t.issue}"`)
    lines.push(`→ ${t.fix}`)
    lines.push('')
  }
  lines.push('--------------------------------')
  lines.push('')
  lines.push('WARRANTY')
  lines.push(props.manual.warranty)

  return (
    <div className="warningLabel">
      <div className="warningHeader">
        <span className="warningIcon">⚠</span>
        <span>USER MANUAL</span>
        <span className="warningHeaderRight">{props.archetype}</span>
      </div>
      <div className="warningBody">
        <pre className="labelAscii">{lines.join('\n')}</pre>
      </div>
    </div>
  )
}

