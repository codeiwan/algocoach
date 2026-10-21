export type CoachingAssistanceSource = 'hint' | 'review'

export type CoachingAssistanceTone = 'neutral' | 'issue'

/** A completed user-requested action in the shared agent feed. */
export interface CoachingAssistanceEvent {
  id: number
  source: CoachingAssistanceSource
  title: string
  revision: number
  text: string
  tone: CoachingAssistanceTone
  atMs: number
}

export type CoachingAssistanceActivity =
  | CoachingAssistanceSource
  | null
