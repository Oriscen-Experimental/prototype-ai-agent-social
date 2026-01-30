import type { Group, Profile } from '../types'
import type { FormSubmission, UIBlock } from '../lib/agentApi'
import { CompactProfileCard, CompactGroupCard } from './CompactResultCard'
import { FormQuestionStepper } from './FormQuestionStepper'

export type BlockRendererProps = {
  block: UIBlock
  onProfileClick?: (profile: Profile) => void
  onGroupClick?: (group: Group) => void
  onFormSubmit?: (submission: FormSubmission) => void
}

export function BlockRenderer({ block, onProfileClick, onGroupClick, onFormSubmit }: BlockRendererProps) {
  switch (block.type) {
    case 'text':
      return <p className="msgText">{block.text}</p>

    case 'profiles':
      if (!block.profiles?.length) return null
      return (
        <div className="blockSection">
          <div className="muted">People &middot; {block.profiles.length}</div>
          <div className="compactRow">
            {block.profiles.map((p) => (
              <CompactProfileCard
                key={p.id}
                profile={p}
                onClick={() => onProfileClick?.(p)}
              />
            ))}
          </div>
        </div>
      )

    case 'groups':
      if (!block.groups?.length) return null
      return (
        <div className="blockSection">
          <div className="muted">Things &middot; {block.groups.length}</div>
          <div className="compactRow">
            {block.groups.map((g) => (
              <CompactGroupCard
                key={g.id}
                group={g}
                onClick={() => onGroupClick?.(g)}
              />
            ))}
          </div>
        </div>
      )

    case 'form':
      if (!block.form || !onFormSubmit) return null
      return <FormQuestionStepper form={block.form} onSubmit={onFormSubmit} />

    default:
      return null
  }
}

export type BlockListProps = {
  blocks: UIBlock[]
  onProfileClick?: (profile: Profile) => void
  onGroupClick?: (group: Group) => void
  onFormSubmit?: (submission: FormSubmission) => void
}

export function BlockList({ blocks, onProfileClick, onGroupClick, onFormSubmit }: BlockListProps) {
  return (
    <>
      {blocks.map((block, idx) => (
        <BlockRenderer
          key={idx}
          block={block}
          onProfileClick={onProfileClick}
          onGroupClick={onGroupClick}
          onFormSubmit={onFormSubmit}
        />
      ))}
    </>
  )
}
