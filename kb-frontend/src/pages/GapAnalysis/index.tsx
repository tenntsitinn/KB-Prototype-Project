import { useState, useEffect } from 'react'
import api from '../../services/api'

interface GapItem {
  id: string
  question_pattern: string
  sample_questions: string[]
  ask_count: number
  status: string
  created_at: string
  last_asked_at: string | null
}

export default function GapAnalysis() {
  const [gaps, setGaps] = useState<GapItem[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('unresolved')
  const [toast, setToast] = useState({ msg: '', type: '' })
  const pageSize = 20

  function showToast(msg: string, type: string) {
    setToast({ msg, type })
    setTimeout(() => setToast({ msg: '', type: '' }), 3000)
  }

  async function fetchGaps() {
    setLoading(true)
    try {
      const res = await api.get('/api/settlement/knowledge-gaps', {
        params: { offset: (page - 1) * pageSize, limit: pageSize, status: statusFilter || undefined },
      })
      setGaps(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch {
      showToast('加载失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchGaps() }, [page, statusFilter])

  async function handleResolve(id: string) {
    try {
      await api.post(`/api/settlement/knowledge-gaps/${id}/resolve`)
      showToast('已标记为已解决', 'success')
      fetchGaps()
    } catch {
      showToast('操作失败', 'error')
    }
  }

  async function handleIgnore(id: string) {
    try {
      await api.post(`/api/settlement/knowledge-gaps/${id}/ignore`)
      showToast('已忽略', 'success')
      fetchGaps()
    } catch {
      showToast('操作失败', 'error')
    }
  }

  const tabs = [
    { key: 'unresolved', label: '待处理' },
    { key: 'resolved', label: '已解决' },
    { key: 'ignored', label: '已忽略' },
  ]
  const totalPages = Math.ceil(total / pageSize)

  const pageContainer: React.CSSProperties = {
    flex: 1, overflow: 'auto', padding: 24,
  }

  return (
    <div style={pageContainer}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {tabs.map(t => (
          <button
            key={t.key}
            className={statusFilter === t.key ? 'btn btn-primary' : 'btn btn-ghost'}
            onClick={() => { setStatusFilter(t.key); setPage(1) }}
          >{t.label}</button>
        ))}
      </div>

      <div style={{
        background: 'var(--bg)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-card)' }}>
              <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>问题</th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', width: 80 }}>频次</th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', width: 100 }}>相似问题</th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', width: 160 }}>时间</th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', width: 160 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr>
            ) : gaps.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>暂无数据</td></tr>
            ) : gaps.map(gap => (
              <tr key={gap.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                <td style={{ padding: '12px 16px', fontSize: 14 }}>{gap.question_pattern}</td>
                <td style={{ padding: '12px 16px', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>{gap.ask_count}</td>
                <td style={{ padding: '12px 16px', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>{(gap.sample_questions || []).length}</td>
                <td style={{ padding: '12px 16px', textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>{gap.created_at}</td>
                <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                  {gap.status === 'unresolved' ? (
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
                      <button className="btn btn-primary" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => handleResolve(gap.id)}>已解决</button>
                      <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => handleIgnore(gap.id)}>忽略</button>
                    </div>
                  ) : (
                    <span style={{
                      fontSize: 12, padding: '2px 8px', borderRadius: 10,
                      background: gap.status === 'resolved' ? 'rgba(52,168,83,0.1)' : 'rgba(154,160,166,0.1)',
                      color: gap.status === 'resolved' ? 'var(--success)' : 'var(--text-muted)',
                    }}>
                      {gap.status === 'resolved' ? '已解决' : '已忽略'}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span style={{ padding: '6px 12px', fontSize: 13, color: 'var(--text-secondary)' }}>第 {page}/{totalPages} 页</span>
          <button className="btn btn-ghost" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}

      {toast.msg && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}