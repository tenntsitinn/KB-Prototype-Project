import { useCallback, useEffect, useState } from 'react'
import api from '../../services/api'
import { useAuthStore } from '../../stores/authStore'
import { RankingBarChart, TokenTrendChart } from './components/Charts'
import { type MetricData, type RankingItem, type TimeRange, type TrendPoint } from './model'

export default function Dashboard() {
  useAuthStore() // ensure auth context is available

  const [timeRange, setTimeRange] = useState<TimeRange>('month')
  const [metrics, setMetrics] = useState<MetricData | null>(null)
  const [trends, setTrends] = useState<TrendPoint[]>([])
  const [questions, setQuestions] = useState<RankingItem[]>([])
  const [units, setUnits] = useState<RankingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [windowWidth, setWindowWidth] = useState(window.innerWidth)

  // Responsive resize handler
  useEffect(() => {
    const handler = () => setWindowWidth(window.innerWidth)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  function formatTokens(n: number): string {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
    if (n >= 1000) return (n / 1000).toFixed(0) + 'K'
    return n.toString()
  }

  const fetchDashboardData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [metricsRes, questionsRes, unitsRes, trendsRes] = await Promise.all([
        api.get('/api/dashboard/metrics', { params: { range: timeRange } }),
        api.get('/api/dashboard/rankings/questions', { params: { range: timeRange, limit: 10 } }),
        api.get('/api/dashboard/rankings/units', { params: { range: timeRange, limit: 10 } }),
        api.get('/api/dashboard/stats/tokens', { params: { days: timeRange === 'today' ? 1 : timeRange === 'week' ? 7 : 30 } }),
      ])

      const m = metricsRes.data
      setMetrics({
        visits: m.total_visits || 0,
        users: m.unique_users || 0,
        units: m.knowledge_unit_count || 0,
        tokens: formatTokens(m.total_tokens || 0),
        response: m.avg_response_ms || 0,
      })

      setQuestions(
        (questionsRes.data.items || []).map((it: { text: string; count: number }) => ({
          name: it.text,
          count: it.count,
        }))
      )

      setUnits(
        (unitsRes.data.items || []).map((it: { text: string; count: number }) => ({
          name: it.text,
          count: it.count,
        }))
      )

      setTrends(
        (trendsRes.data.items || []).map((it: { date: string; total_tokens: number; request_count: number }) => ({
          date: it.date,
          tokens: it.total_tokens || 0,
          requests: it.request_count || 0,
        }))
      )
    } catch (e: any) {
      setError(e?.response?.data?.detail || '加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [timeRange])

  useEffect(() => {
    fetchDashboardData()
  }, [fetchDashboardData])

  // Responsive column counts
  const metricsCols = windowWidth <= 768 ? 2 : windowWidth <= 1200 ? 3 : 5
  const chartsCols = windowWidth <= 1200 ? 1 : 2

  // ==================== Render ====================

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        height: 56, borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', flexShrink: 0,
      }}>
        <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text)' }}>
          数据看板
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            display: 'flex', background: 'var(--bg-input)', borderRadius: 'var(--radius)',
            padding: 3, gap: 2,
          }}>
            {(['today', 'week', 'month'] as TimeRange[]).map(range => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                style={{
                  padding: '5px 12px', borderRadius: 'var(--radius-sm)', fontSize: 13,
                  color: timeRange === range ? 'var(--primary)' : 'var(--text-secondary)',
                  cursor: 'pointer', border: 'none', background: timeRange === range ? 'var(--bg)' : 'transparent',
                  fontFamily: 'var(--font)', transition: 'all 0.15s',
                  fontWeight: timeRange === range ? 500 : 400,
                  boxShadow: timeRange === range ? 'var(--shadow-sm)' : 'none',
                }}
              >
                {range === 'today' ? '今天' : range === 'week' ? '近7天' : '近30天'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{
        flex: 1, overflow: 'auto', padding: windowWidth <= 768 ? 16 : 24,
        display: 'flex', flexDirection: 'column', gap: 24,
        background: '#F5F6F8',
      }}>
        {/* Error State */}
        {error && !loading && (
          <div style={{
            padding: 16, borderRadius: 'var(--radius)',
            background: '#FDECEA', color: 'var(--danger)',
            border: '1px solid rgba(234,67,53,0.2)', fontSize: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span>{error}</span>
            <button
              onClick={fetchDashboardData}
              style={{
                padding: '4px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--danger)',
                background: 'transparent', color: 'var(--danger)', cursor: 'pointer',
                fontSize: 12, fontFamily: 'var(--font)',
              }}
            >
              重试
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexDirection: 'column', gap: 12, minHeight: 300,
          }}>
            <div style={{
              width: 36, height: 36, border: '3px solid var(--border)',
              borderTopColor: 'var(--primary)', borderRadius: '50%',
              animation: 'spin 0.8s linear infinite',
            }} />
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>加载中...</span>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {/* Dashboard Content */}
        {!loading && (
          <>
            {/* Metrics Cards */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${metricsCols}, 1fr)`,
              gap: 16,
            }}>
              {/* Card: 总访问量 */}
              <div style={cardStyle}>
                <div style={metricLabelStyle}>
                  <span style={{ ...metricIconStyle, background: 'var(--primary)' }} />
                  总访问量
                </div>
                <div style={metricValueStyle}>
                  {metrics ? metrics.visits.toLocaleString() : '--'}
                </div>
                <div style={metricSubStyle}>
                  {timeRange === 'today' ? '今日' : timeRange === 'week' ? '近7天' : '近30天'}
                </div>
              </div>

              {/* Card: 独立用户数 */}
              <div style={cardStyle}>
                <div style={metricLabelStyle}>
                  <span style={{ ...metricIconStyle, background: 'var(--info)' }} />
                  独立用户数
                </div>
                <div style={metricValueStyle}>
                  {metrics ? metrics.users.toLocaleString() : '--'}
                </div>
                <div style={metricSubStyle}>
                  {timeRange === 'today' ? '今日' : timeRange === 'week' ? '近7天' : '近30天'}
                </div>
              </div>

              {/* Card: 知识单元数 */}
              <div style={cardStyle}>
                <div style={metricLabelStyle}>
                  <span style={{ ...metricIconStyle, background: 'var(--success)' }} />
                  知识单元数
                </div>
                <div style={metricValueStyle}>
                  {metrics ? metrics.units.toLocaleString() : '--'}
                </div>
                <div style={metricSubStyle}>
                  当前总计
                </div>
              </div>

              {/* Card: Token 总量 */}
              <div style={cardStyle}>
                <div style={metricLabelStyle}>
                  <span style={{ ...metricIconStyle, background: 'var(--warning)' }} />
                  Token 总量
                </div>
                <div style={metricValueStyle}>
                  {metrics ? metrics.tokens : '--'}
                </div>
                <div style={metricSubStyle}>
                  {timeRange === 'today' ? '今日' : timeRange === 'week' ? '近7天' : '近30天'}
                </div>
              </div>

              {/* Card: 平均响应时间 */}
              <div style={cardStyle}>
                <div style={metricLabelStyle}>
                  <span style={{ ...metricIconStyle, background: 'var(--text-muted)' }} />
                  平均响应时间
                </div>
                <div style={metricValueStyle}>
                  {metrics ? `${metrics.response}ms` : '--'}
                </div>
                <div style={metricSubStyle}>
                  {timeRange === 'today' ? '今日' : timeRange === 'week' ? '近7天' : '近30天'}
                </div>
              </div>
            </div>

            {/* Empty State (no metrics + no charts data) */}
            {!metrics && trends.length === 0 && questions.length === 0 && units.length === 0 && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', padding: 48, gap: 12,
              }}>
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <line x1="3" y1="9" x2="21" y2="9" />
                  <line x1="3" y1="15" x2="21" y2="15" />
                  <line x1="9" y1="3" x2="9" y2="21" />
                </svg>
                <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>暂无数据</span>
              </div>
            )}

            {/* Token 消耗趋势 */}
            <div style={{ ...chartCardStyle }}>
              <h3 style={chartTitleStyle}>Token 消耗趋势</h3>
              <div style={{ minHeight: 400 }}>
                <TokenTrendChart data={trends} />
              </div>
            </div>

            {/* Rankings Row */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${chartsCols}, 1fr)`,
              gap: 16,
            }}>
              {/* 高频问题排行 */}
              <div style={chartCardStyle}>
                <h3 style={chartTitleStyle}>高频问题排行</h3>
                <div style={{ minHeight: 320 }}>
                  <RankingBarChart data={questions} barColor="#263238" />
                </div>
              </div>

              {/* 热门知识单元 */}
              <div style={chartCardStyle}>
                <h3 style={chartTitleStyle}>热门知识单元</h3>
                <div style={{ minHeight: 320 }}>
                  <RankingBarChart data={units} barColor="#4285F4" />
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ==================== Shared Styles ====================

const cardStyle: React.CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: 20,
  transition: 'box-shadow 0.15s',
}

const metricLabelStyle: React.CSSProperties = {
  fontSize: 13,
  color: 'var(--text-muted)',
  marginBottom: 8,
  display: 'flex',
  alignItems: 'center',
  gap: 6,
}

const metricIconStyle: React.CSSProperties = {
  width: 8,
  height: 8,
  borderRadius: 2,
  display: 'inline-block',
  flexShrink: 0,
}

const metricValueStyle: React.CSSProperties = {
  fontSize: 28,
  fontWeight: 700,
  color: 'var(--text)',
  lineHeight: 1,
}

const metricSubStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--text-muted)',
  marginTop: 6,
}

const chartCardStyle: React.CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)',
  padding: 20,
}

const chartTitleStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--text)',
  marginBottom: 16,
}
