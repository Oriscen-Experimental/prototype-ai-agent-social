import { useState } from 'react'
import { Modal } from './Modal'
import { SocialWarningLabel } from './SocialWarningLabel'
import { SocialNutritionFacts } from './SocialNutritionFacts'
import { SocialUserManual } from './SocialUserManual'
import type { WarningLabel, NutritionFacts, UserManual } from '../lib/sortingQuiz'

interface OnboardingCompletionModalProps {
  archetype?: string
  warningLabel?: WarningLabel
  nutritionFacts?: NutritionFacts
  userManual?: UserManual
  onProceed: () => void
  canProceed?: boolean
}

function LoadingPlaceholder() {
  return (
    <div className="generating">
      <span className="generatingDot" />
      <span>Generating...</span>
    </div>
  )
}

export function OnboardingCompletionModal(props: OnboardingCompletionModalProps) {
  const [labelTab, setLabelTab] = useState<'warning' | 'nutrition' | 'manual'>('warning')

  const handleClose = () => {
    if (props.canProceed) {
      props.onProceed()
    }
  }

  return (
    <Modal
      title="Onboarding Complete!"
      onClose={handleClose}
      footer={
        <div className="completionFooter">
          <div className="completionMessage">
            {props.canProceed
              ? 'You have finished onboarding! Welcome to the real journey.'
              : 'Generating your personalized results...'}
          </div>
          <button
            className="btn"
            onClick={props.onProceed}
            type="button"
            disabled={!props.canProceed}
          >
            Let's go
          </button>
        </div>
      }
    >
      <div className="stack">
        <div className="labelTabs">
          <button
            type="button"
            className={labelTab === 'warning' ? 'tabChip tabChipActive' : 'tabChip'}
            onClick={() => setLabelTab('warning')}
          >
            Warning Label
            {props.warningLabel ? '' : ' ...'}
          </button>
          <button
            type="button"
            className={labelTab === 'nutrition' ? 'tabChip tabChipActive' : 'tabChip'}
            onClick={() => setLabelTab('nutrition')}
          >
            Nutrition Facts
            {props.nutritionFacts ? '' : ' ...'}
          </button>
          <button
            type="button"
            className={labelTab === 'manual' ? 'tabChip tabChipActive' : 'tabChip'}
            onClick={() => setLabelTab('manual')}
          >
            User Manual
            {props.userManual ? '' : ' ...'}
          </button>
        </div>

        {labelTab === 'warning' ? (
          props.warningLabel ? (
            <SocialWarningLabel label={props.warningLabel} archetype={props.archetype || ''} />
          ) : (
            <LoadingPlaceholder />
          )
        ) : labelTab === 'nutrition' ? (
          props.nutritionFacts ? (
            <SocialNutritionFacts facts={props.nutritionFacts} archetype={props.archetype || ''} />
          ) : (
            <LoadingPlaceholder />
          )
        ) : props.userManual ? (
          <SocialUserManual manual={props.userManual} archetype={props.archetype || ''} />
        ) : (
          <LoadingPlaceholder />
        )}
      </div>
    </Modal>
  )
}
