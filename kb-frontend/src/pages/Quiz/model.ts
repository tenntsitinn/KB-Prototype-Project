export interface Tag {
  id: string
  name: string
  sort_order: number
}

export interface QuizQuestion {
  question_id: string
  question: string
  from_bank: boolean
  source_unit_id: string
  reference_answer?: string
}

export interface QuizAnswerResult {
  question_id: string
  question: string
  score: number
  feedback: string
  reference_answer: string
  source_unit_id: string
}

export type Phase = 'select' | 'question' | 'grading' | 'result'

export interface DocumentItem {
  id: string
  title: string
  category: string
}

export interface HistoryItem {
  question: string
  score: number
}
