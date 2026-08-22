import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import { STATUS_MAP, SOURCE_MAP, type BankQuestion } from '../QuizBank/model'

const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }
const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)', verticalAlign: 'top' }
const selectStyle: React.CSSProperties = { padding: '8px 12px', fontSize: 13, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', cursor: 'pointer' }

const statusBadge = (status: string): React.CSSProperties => ({
  fontSize: 11, padding: '2px 8px', borderRadius: 999, fontWeight: 500,
  background: status === 'published' ? 'rgba(52, 168, 83, 0.12)'
    : status === 'pending_review' ? 'var(--primary-light)'
    : status === 'rejected' ? 'rgba(234, 67, 53, 0.12)'
    : 'var(--bg-hover)',
  color: status === 'published' ? 'var(--success)'
    : status === 'pending_review' ? 'var(--primary)'
    : status === 'rejected' ? 'var(--danger)'
    : 'var(--text-muted)',
})

function fmtDate(v: string | null): string {
  if (!v) return '-'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '-' : d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export default function QuizBrowse() {
  const [questions, setQuestions] = useState<BankQuestion[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [tags, setTags] = useState<{id: string; name: string}[]>([])
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [page, setPage] = useState(0)
  const [detail, setDetail] = useState<BankQuestion | null>(null)
  const [toast, setToast] = useState({ msg: '', type: '' })

  const PAGE_SIZE = 20

  function showToast(msg: string, type: string) {
    setToast({ msg, type })
    setTimeout(() => setToast({ msg: '', type: '' }), 3000)
  }

  const fetchQuestions = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/quiz/bank', {
        params: {
          status: statusFilter, category: categoryFilter, keyword,
          offset: page * PAGE_SIZE, limit: PAGE_SIZE,
        },
      })
      const items: BankQuestion[] = res.data?.items || []
      setQuestions(sourceFilter ? items.filter((q) => q.source_type === sourceFilter) : items)
      setTotal(res.data?.total || 0)
    } catch { showToast('加载题库失败', 'error') }
    finally { setLoading(false) }
  }, [statusFilter, categoryFilter, keyword, page, sourceFilter])

  useEffect(() => { fetchQuestions() }, [fetchQuestions])
  useEffect(() => {
    api.get('/api/tags').then((res) => {
      setTags(Array.isArray(res.data) ? res.data : res.data?.data || [])
    }).catch(() => {})
  }, [])
  useEffect(() => { setPage(0) }, [statusFilter, categoryFilter, keyword, sourceFilter])

  const openSource = useCallback(async (unitId: string) => {
    const win = window.open('about:blank', '_blank')
    try {
      const res = await api.get(`/api/knowledge/units/${unitId}/file-url`)
      const url: string = res.data?.url
      if (!url) throw new Error('no url')
      if (win) win.location.href = url
      else window.open(url, '_blank')
    } catch {
      win?.close()
      showToast('原文档加载失败', 'error')
    }
  }, [])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const metaItem = (k: string, v: React.ReactNode, color?: string) => (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>{k}</div>
      <div style={{ fontSize: 13, fontWeight: 500, color: color || 'var(--text)' }}>{v}</div>
    </div>
  )

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') setKeyword(searchInput.trim()) }}
          placeholder="搜索题目/答案关键词，回车确认"
          style={{
            padding: '8px 12px', fontSize: 13, borderRadius: 8, border: '1px solid var(--border)',
            background: 'var(--bg-card)', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', width: 240,
          }}
        />
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} style={selectStyle}>
          <option value="">全部分类</option>
          {tags.map((t) => (
            <option key={t.id} value={t.name}>{t.name}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={selectStyle}>
          <option value="">全部状态</option>
          <option value="pending_review">待审核</option>
          <option value="published">已发布</option>
          <option value="rejected">已驳回</option>
          <option value="offline">已下架</option>
        </select>
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} style={selectStyle}>
          <option value="">全部来源</option>
          <option value="ai_generated">AI 出题</option>
          <option value="user_question">用户提问</option>
        </select>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>共 {total} 题</span>
      </div>

      {/* Table */}
      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ background: 'var(--bg-card)' }}>
            <th style={{ ...thStyle, width: 48, textAlign: 'center' }}>序号</th>
            <th style={thStyle}>题目</th>
            <th style={{ ...thStyle, width: 90 }}>分类</th>
            <th style={{ ...thStyle, width: 90 }}>来源</th>
            <th style={{ ...thStyle, width: 90 }}>状态</th>
            <th style={{ ...thStyle, width: 64, textAlign: 'center' }}>使用</th>
            <th style={{ ...thStyle, width: 100 }}>创建时间</th>
            <th style={{ ...thStyle, width: 64, textAlign: 'center' }}>操作</th>
          </tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr>
            ) : questions.length === 0 ? (
              <tr><td colSpan={8} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>暂无符合条件的题目</td></tr>
            ) : questions.map((q, idx) => (
              <tr key={q.id}>
                <td style={{ ...tdStyle, textAlign: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{page * PAGE_SIZE + idx + 1}</span>
                </td>
                <td style={tdStyle}>
                  <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.5 }}>
                    {q.question.length > 60 ? `${q.question.slice(0, 60)}…` : q.question}
                  </div>
                </td>
                <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{q.category || '-'}</span></td>
                <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{SOURCE_MAP[q.source_type] || q.source_type}</span></td>
                <td style={tdStyle}><span style={statusBadge(q.status)}>{STATUS_MAP[q.status] || q.status}</span></td>
                <td style={{ ...tdStyle, textAlign: 'center' }}><span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{q.usage_count}</span></td>
                <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{fmtDate(q.created_at)}</span></td>
                <td style={{ ...tdStyle, textAlign: 'center' }}>
                  <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => setDetail(q)}>查看</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16, alignItems: 'center' }}>
          <button className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button>
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{page + 1} / {totalPages}</span>
          <button className="btn btn-ghost" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>下一页</button>
        </div>
      )}

      {/* Detail Modal (read-only) */}
      {detail && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
          onClick={(e) => { if (e.target === e.currentTarget) setDetail(null) }}
        >
          <div style={{
            width: '90%', maxWidth: 640, background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)', padding: 24, maxHeight: '80vh', overflow: 'auto',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)' }}>题目详情</div>
              <span style={{ ...statusBadge(detail.status), fontSize: 12 }}>{STATUS_MAP[detail.status] || detail.status}</span>
            </div>
            <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.7, marginBottom: 12 }}>{detail.question}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>参考答案</div>
            <div style={{
              fontSize: 13, color: 'var(--text)', lineHeight: 1.8, marginBottom: 20,
              padding: 14, background: 'var(--bg)', borderRadius: 8, border: '1px solid var(--border-light)',
              whiteSpace: 'pre-wrap',
            }}>
              {detail.reference_answer || '（暂无参考答案）'}
            </div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
              paddingTop: 16, borderTop: '1px solid var(--border-light)',
            }}>
              {metaItem('分类', detail.category || '-')}
              {metaItem('来源', SOURCE_MAP[detail.source_type] || detail.source_type)}
              {metaItem('使用次数', detail.usage_count)}
              {metaItem('审核人', detail.reviewer_name || '未审核')}
              {metaItem('审核时间', fmtDate(detail.reviewed_at))}
              {metaItem('创建时间', fmtDate(detail.created_at))}
              {metaItem('编号', <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 12 }}>{detail.id}</span>)}
              {metaItem('来源文档', detail.source_unit_id
                ? <a href="#" onClick={(e) => { e.preventDefault(); openSource(detail.source_unit_id) }} style={{ color: 'var(--primary)', cursor: 'pointer' }}>查看原文 →</a>
                : '-')}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
              <button className="btn btn-primary" onClick={() => setDetail(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}

      {toast.msg && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
