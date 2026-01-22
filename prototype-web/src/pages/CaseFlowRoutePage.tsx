import { useParams } from 'react-router-dom'
import { CaseFlowPage } from './CaseFlowPage'

export function CaseFlowRoutePage() {
  const { caseId } = useParams()
  return <CaseFlowPage key={caseId} caseId={caseId} />
}

