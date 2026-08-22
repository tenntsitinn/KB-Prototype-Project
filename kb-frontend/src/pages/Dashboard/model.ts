export interface MetricData {
  visits: number
  users: number
  units: number
  tokens: string
  response: number
}

export interface TrendPoint {
  date: string
  tokens: number
  requests: number
}

export interface RankingItem {
  name: string
  count: number
}

export type TimeRange = 'today' | 'week' | 'month'

// ==================== SVG Chart Components ====================

/** Token 消耗趋势 - dual-Y-axis line chart with area fill */

