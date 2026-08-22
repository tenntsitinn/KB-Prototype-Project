export interface BankQuestion {
  id: string
  question: string
  reference_answer: string
  category: string
  source_unit_id: string
  source_type: string
  status: string
  usage_count: number
  reviewer_id: string
  reviewer_name: string
  reviewed_at: string | null
  created_at: string
}

export interface Tag {
  id: string
  name: string
  sort_order: number
}

export const STATUS_MAP: Record<string, string> = {
  pending_review: '待审核',
  published: '已发布',
  rejected: '已驳回',
  offline: '已下架',
}

export const SOURCE_MAP: Record<string, string> = {
  ai_generated: 'AI 出题',
  user_question: '用户提问',
}
