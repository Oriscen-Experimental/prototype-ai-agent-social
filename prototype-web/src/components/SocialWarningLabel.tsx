import type { WarningLabel } from '../lib/sortingQuiz'

export function SocialWarningLabel(props: { label: WarningLabel; archetype: string }) {
  return (
    <div className="warningLabel">
      <div className="warningHeader">
        <span className="warningIcon">⚠</span>
        <span>SOCIAL WARNING LABEL</span>
        <span className="warningHeaderRight">{props.archetype}</span>
      </div>

      <div className="warningBody">
        {props.label.warnings.map((w, idx) => (
          <div key={idx} className="warningRow">
            <span className="warningBullet">⚠</span>
            <span>{w}</span>
          </div>
        ))}

        <div className="warningSectionTitle">BEST CONSUMED:</div>
        <div className="warningBestRow">{props.label.bestConsumed.join(', ')}</div>

        <div className="warningDoNot">
          <span className="warningStop">⛔</span>
          <span>DO NOT</span>
          <span className="warningDoNotText">{props.label.doNot.join(' / ')}</span>
        </div>
      </div>
    </div>
  )
}

