import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import { SOURCE_MAP, type BankQuestion } from './model'

const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }
const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)', verticalAlign: 'top' }
const inputStyle: React.CSSProperties = {
  padding: '8px 12px', fontSize: 13, borderRadius: 8,
  border: '1px solid var(--border)', background: 'var(--bg-card)',
  color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none',
}

export default function QuizBank() {
  const [questions, setQuestions] = useState<BankQuestion[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [tags, setTags] = useState<{id: string; name: string}[]>([])
  const [categoryFilter, setCategoryFilter] = useState('')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchWorking, setBatchWorking] = useState(false)
  const [editing, setEditing] = useState<BankQuestion | null>(null)
  const [editQuestion, setEditQuestion] = useState('')
  const [editAnswer, setEditAnswer] = useState('')
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
          status: 'pending_review', category: categoryFilter, keyword,
          offset: page * PAGE_SIZE, limit: PAGE_SIZE,
        },
      })
      setQuestions(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } catch { showToast('加载题库失败', 'error') }
    finally { setLoading(false) }
  }, [categoryFilter, keyword, page])

  useEffect(() => { fetchQuestions() }, [fetchQuestions])
  useEffect(() => {
    api.get('/api/tags').then((res) => {
      const list = Array.isArray(res.data) ? res.data : res.data?.data || []
      setTags(list)
    }).catch(() => {})
  }, [])
  useEffect(() => { setPage(0); setSelected(new Set()) }, [categoryFilter, keyword])

  const toggleAll = useCallback((checked: boolean) => {
    setSelected(checked ? new Set(questions.map((q) => q.id)) : new Set())
  }, [questions])

  const toggleOne = useCallback((id: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])

  const review = useCallback(async (id: string, action: string) => {
    try {
      await api.post(`/api/quiz/bank/${id}/review`, { action })
      showToast(action === 'approve' ? '已发布' : action === 'reject' ? '已驳回' : '已下架', 'success')
      setSelected((prev) => { const n = new Set(prev); n.delete(id); return n })
      fetchQuestions()
    } catch { showToast('操作失败', 'error') }
  }, [fetchQuestions])

  const batchApprove = useCallback(async () => {
    if (selected.size === 0 || batchWorking) return
    if (!confirm(`确定批量通过选中的 ${selected.size} 道题？`)) return
    setBatchWorking(true)
    try {
      const results = await Promise.allSettled(
        Array.from(selected).map((id) => api.post(`/api/quiz/bank/${id}/review`, { action: 'approve' }))
      )
      const ok = results.filter((r) => r.status === 'fulfilled').length
      const fail = results.length - ok
      showToast(fail === 0 ? `已批量通过 ${ok} 道题` : `成功 ${ok} 道，失败 ${fail} 道`, fail === 0 ? 'success' : 'error')
      setSelected(new Set())
      fetchQuestions()
    } catch { showToast('批量操作失败', 'error') }
    finally { setBatchWorking(false) }
  }, [selected, batchWorking, fetchQuestions])

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

  const mine = useCallback(async () => {
    try {
      const res = await api.post('/api/quiz/bank/mine', { limit: 20 })
      showToast(`从问答日志挖掘到 ${res.data?.new_count || 0} 道候选题`, 'success')
      fetchQuestions()
    } catch { showToast('挖掘失败', 'error') }
  }, [fetchQuestions])

  const saveEdit = useCallback(async () => {
    if (!editing) return
    try {
      await api.post(`/api/quiz/bank/${editing.id}/review`, {
        action: 'edit',
        question: editQuestion,
        reference_answer: editAnswer,
      })
      showToast('已保存', 'success')
      setEditing(null)
      fetchQuestions()
    } catch { showToast('保存失败', 'error') }
  }, [editing, editQuestion, editAnswer, fetchQuestions])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const allChecked = questions.length > 0 && questions.every((q) => selected.has(q.id))

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '2px 12px',
          borderRadius: 999, background: 'var(--primary-light)', color: 'var(--primary)',
          fontSize: 12, fontWeight: 500, flexShrink: 0,
        }}>
          待审核 {total}
        </div>
        <input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { setKeyword(searchInput.trim()); setPage(0) } }}
          placeholder="搜索题目关键词，回车确认"
          style={{ ...inputStyle, width: 240 }}
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          style={{ padding: '8px 12px', fontSize: 13, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', cursor: 'pointer' }}
        >
          <option value="">全部分类</option>
          {tags.map((t) => (
            <option key={t.id} value={t.name}>{t.name}</option>
          ))}
        </select>
        <div style={{ flex: 1 }} />
        <button className="btn btn-outline" onClick={mine}>从问答日志挖掘候选题</button>
      </div>

      {/* Batch bar */}
      {selected.size > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '8px 14px', marginBottom: 12,
          background: 'var(--primary-light)', borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--primary)',
        }}>
          <span style={{ fontSize: 13, color: 'var(--text)' }}>已选 {selected.size} 道题</span>
          <div style={{ flex: 1 }} />
          <button className="btn btn-primary" style={{ fontSize: 12, padding: '4px 12px' }} disabled={batchWorking} onClick={batchApprove}>
            {batchWorking ? '处理中…' : '批量通过选中'}
          </button>
          <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 12px' }} onClick={() => setSelected(new Set())}>取消选择</button>
        </div>
      )}

      {/* Table */}
      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ background: 'var(--bg-card)' }}>
            <th style={{ ...thStyle, width: 40, textAlign: 'center' }}>
              <input type="checkbox" checked={allChecked} onChange={(e) => toggleAll(e.target.checked)} />
            </th>
            <th style={thStyle}>题目</th>
            <th style={{ ...thStyle, width: 90 }}>来源</th>
            <th style={{ ...thStyle, width: 110 }}>提交时间</th>
            <th style={{ ...thStyle, width: 200 }}>操作</th>
          </tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr>
            ) : questions.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                暂无待审核题目。用户在「智能出题」中作答产生的题目会自动进入待审核列表；也可点击右上角从问答日志挖掘。
              </td></tr>
            ) : questions.map((q) => (
              <tr key={q.id} style={{ background: selected.has(q.id) ? 'var(--primary-light)' : 'transparent' }}>
                <td style={{ ...tdStyle, textAlign: 'center' }}>
                  <input type="checkbox" checked={selected.has(q.id)} onChange={(e) => toggleOne(q.id, e.target.checked)} />
                </td>
                <td style={tdStyle}>
                  <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.5, marginBottom: 4 }}>{q.question}</div>
                  {q.reference_answer && (
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                      参考答案：{q.reference_answer.slice(0, 80)}{q.reference_answer.length > 80 ? '…' : ''}
                    </div>
                  )}
                  {q.source_unit_id && (
                    <a href="#" onClick={(e) => { e.preventDefault(); openSource(q.source_unit_id) }} style={{ fontSize: 12, color: 'var(--primary)' }}>
                      查看来源文档
                    </a>
                  )}
                </td>
                <td style={tdStyle}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{SOURCE_MAP[q.source_type] || q.source_type}</span>
                </td>
                <td style={tdStyle}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {q.created_at ? new Date(q.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                  </span>
                </td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button className="btn btn-primary" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => review(q.id, 'approve')}>通过</button>
                    <button className="btn btn-danger" style={{ fontSize: 12, padding: '4px 10px' }} onClick={() => review(q.id, 'reject')}>驳回</button>
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: 12, padding: '4px 10px' }}
                      onClick={() => { setEditing(q); setEditQuestion(q.question); setEditAnswer(q.reference_answer) }}
                    >
                      编辑
                    </button>
                  </div>
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

      {/* Edit Modal */}
      {editing && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
          onClick={(e) => { if (e.target === e.currentTarget) setEditing(null) }}
        >
          <div style={{
            width: '90%', maxWidth: 640, background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)', padding: 24, maxHeight: '80vh', overflow: 'auto',
          }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: 'var(--text)' }}>编辑题目</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>题目</div>
            <textarea
              value={editQuestion}
              onChange={(e) => setEditQuestion(e.target.value)}
              style={{ width: '100%', minHeight: 80, padding: '10px 12px', fontSize: 14, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontFamily: 'var(--font)', marginBottom: 16, boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.6 }}
            />
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>参考答案</div>
            <textarea
              value={editAnswer}
              onChange={(e) => setEditAnswer(e.target.value)}
              style={{ width: '100%', minHeight: 120, padding: '10px 12px', fontSize: 14, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontFamily: 'var(--font)', marginBottom: 20, boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.6 }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button>
              <button className="btn btn-primary" onClick={saveEdit}>保存</button>
            </div>
          </div>
        </div>
      )}

      {toast.msg && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
