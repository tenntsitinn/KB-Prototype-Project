// ──────────────── Types ────────────────
export interface FaqRecommendation {
  id: string;
  question: string;
  answer: string;
  related_unit_id: string;
  related_unit_title: string;
  source_type: 'auto_mined' | 'manual';
  hit_count: number;
  status: 'pending_review';
}

export interface FaqPublished {
  id: string;
  question: string;
  answer: string;
  source_type: 'auto_mined' | 'manual';
  hit_count: number;
  cache_active: boolean;
  reviewer_id: string;
  reviewed_at: string;
  created_at: string;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}
