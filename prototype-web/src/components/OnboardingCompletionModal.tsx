import { useState } from 'react'
import { Modal } from './Modal'
import { SocialWarningLabel } from './SocialWarningLabel'
import { SocialNutritionFacts } from './SocialNutritionFacts'
import { SocialUserManual } from './SocialUserManual'
import type { WarningLabel, NutritionFacts, UserManual } from '../lib/sortingQuiz'

interface OnboardingCompletionModalProps {
  archetype: string
  warningLabel: WarningLabel
  nutritionFacts: NutritionFacts
  userManual: UserManual
  onProceed: () => void
}

export function OnboardingCompletionModal(props: OnboardingCompletionModalProps) {
  const [labelTab, setLabelTab] = useState<'warning' | 'nutrition' | 'manual'>('warning')

  return (
    <Modal
      title="Onboarding Complete!"
      onClose={props.onProceed}
      footer={
        <div className="completionFooter">
          <div className="completionMessage">
            You have finished onboarding! Welcome to the real journey.
          </div>
          <button className="btn" onClick={props.onProceed} type="button">
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
          </button>
          <button
            type="button"
            className={labelTab === 'nutrition' ? 'tabChip tabChipActive' : 'tabChip'}
            onClick={() => setLabelTab('nutrition')}
          >
            Nutrition Facts
          </button>
          <button
            type="button"
            className={labelTab === 'manual' ? 'tabChip tabChipActive' : 'tabChip'}
            onClick={() => setLabelTab('manual')}
          >
            User Manual
          </button>
        </div>

        {labelTab === 'warning' ? (
          <SocialWarningLabel label={props.warningLabel} archetype={props.archetype} />
        ) : labelTab === 'nutrition' ? (
          <SocialNutritionFacts facts={props.nutritionFacts} archetype={props.archetype} />
        ) : (
          <SocialUserManual manual={props.userManual} archetype={props.archetype} />
        )}
      </div>
    </Modal>
  )
}
