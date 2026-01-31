import type { NutritionFacts } from '../lib/sortingQuiz'

function padRight(s: string, n: number) {
  if (s.length >= n) return s
  return s + ' '.repeat(n - s.length)
}

export function SocialNutritionFacts(props: { facts: NutritionFacts; archetype: string }) {
  const rows = props.facts.amountPerServing
  const labelWidth = Math.min(28, Math.max(18, ...rows.map((r) => r.label.length)))

  const lines: string[] = []
  lines.push('SOCIAL NUTRITION FACTS')
  lines.push('--------------------------------')
  lines.push(`Serving Size: ${props.facts.servingSize}`)
  lines.push(`Servings Per Week: ${props.facts.servingsPerWeek}`)
  lines.push('--------------------------------')
  lines.push('Amount Per Serving')
  lines.push('--------------------------------')
  for (const r of rows) {
    lines.push(`${padRight(r.label, labelWidth)}  ${r.value}`)
  }
  lines.push('--------------------------------')
  lines.push(`${padRight('Energy Drain (per hour)', labelWidth)}  ${props.facts.energyDrainPerHour}`)
  lines.push(`${padRight('Recovery Time Needed', labelWidth)}  ${props.facts.recoveryTimeNeeded}`)
  lines.push('--------------------------------')
  lines.push('')
  lines.push(`INGREDIENTS: ${props.facts.ingredients}`)
  lines.push('')
  lines.push(`CONTAINS: ${props.facts.contains}`)
  lines.push(`MAY CONTAIN: ${props.facts.mayContain}`)

  return (
    <div className="warningLabel">
      <div className="warningHeader">
        <span className="warningIcon">⚠</span>
        <span>SOCIAL NUTRITION FACTS</span>
        <span className="warningHeaderRight">{props.archetype}</span>
      </div>
      <div className="warningBody">
        <pre className="labelAscii">{lines.join('\n')}</pre>
      </div>
    </div>
  )
}

