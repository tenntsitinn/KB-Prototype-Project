import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import { SOURCE_MAP, STATUS_MAP, type BankQuestion, type PointTag } from './model'
import CategoryCascade, { PointPicker, emptyCategory, type CategoryValue } from '../../components/CategoryCascade'
import QuestionDetailModal, { fmtDate, statusBadgeStyle } from '../../components/QuestionDetailModal'

const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }
const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)', verticalAlign: 'top', whiteSpace: 'nowrap' }
const selectStyle: React.CSSProperties = { padding: '8px 12px', fontSize: 13, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', cursor: 'pointer' }

const tagChipStyle: React.CSSProperties = {
  fontSize: 11, padding: '1px 8px', borderRadius: 999,
  background: 'var(--primary-light)', color: 'var(--primary)', fontWeight: 500,
}

export default function QuizBank() {
  const [questions, setQuestions] = useState<BankQuestion[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [category, setCategory] = useState<CategoryValue>(emptyCategory)
  const [sourceFilter, setSourceFilter] = useState('')
  const [reviewStatus, setReviewStatus] = useState('pending')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchWorking, setBatchWorking] = useState(false)
  const [detail, setDetail] = useState<BankQuestion | null>(null)
  const [editing, setEditing] = useState<BankQuestion | null>(null)
  const [editQuestion, setEditQuestion] = useState('')
  const [editAnswer, setEditAnswer] = useState('')
  const [editPoints, setEditPoints] = useState<PointTag[]>([])
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
          review_status: reviewStatus,
          source_type: sourceFilter,
          course_id: category.courseId,
          chapter_id: category.chapterId,
          point_id: category.pointId,
          keyword,
          offset: page * PAGE_SIZE, limit: PAGE_SIZE,
        },
      })
      setQuestions(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } catch { showToast('加载题库失败', 'error') }
    finally { setLoading(false) }
  }, [reviewStatus, sourceFilter, category, keyword, page])

  useEffect(() => { fetchQuestions() }, [fetchQuestions])
  useEffect(() => { setPage(0); setSelected(new Set()) }, [reviewStatus, sourceFilter, category, keyword])
  useEffect(() => { setSelected(new Set()) }, [page])

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
      setDetail(null)
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

  const batchDelete = useCallback(async () => {
    if (selected.size === 0 || batchWorking) return
    if (!confirm(`确定批量删除选中的 ${selected.size} 道题？此操作不可恢复。`)) return
    setBatchWorking(true)
    try {
      const res = await api.delete('/api/quiz/bank', { data: { question_ids: Array.from(selected) } })
      const ok = res.data?.deleted_count ?? selected.size
      showToast(`已删除 ${ok} 道题`, 'success')
      setSelected(new Set())
      fetchQuestions()
    } catch { showToast('批量删除失败', 'error') }
    finally { setBatchWorking(false) }
  }, [selected, batchWorking, fetchQuestions])

  const deleteQuestion = useCallback(async (id: string) => {
    if (!confirm('确定删除该题目？此操作不可恢复。')) return
    try {
      await api.delete(`/api/quiz/bank/${id}`)
      showToast('已删除', 'success')
      setSelected((prev) => { const n = new Set(prev); n.delete(id); return n })
      setDetail(null)
      fetchQuestions()
    } catch { showToast('删除失败', 'error') }
  }, [fetchQuestions])

  const mine = useCallback(async () => {
    try {
      const res = await api.post('/api/quiz/bank/mine', { limit: 20 })
      const n = res.data?.new_count || 0
      const t = res.data?.tagged_count || 0
      showToast(n === 0 ? '没有新的可挖掘提问' : `挖掘到 ${n} 道候选题，其中 ${t} 道已自动挂知识点标签`, 'success')
      fetchQuestions()
    } catch { showToast('挖掘失败', 'error') }
  }, [fetchQuestions])

  const openEdit = (q: BankQuestion) => {
    setEditing(q)
    setEditQuestion(q.question)
    setEditAnswer(q.reference_answer)
    setEditPoints(q.points || [])
  }

  const saveEdit = useCallback(async () => {
    if (!editing) return
    try {
      await api.post(`/api/quiz/bank/${editing.id}/review`, {
        action: 'edit',
        question: editQuestion,
        reference_answer: editAnswer,
        point_ids: editPoints.map((p) => p.id),
      })
      showToast('已保存', 'success')
      setEditing(null)
      fetchQuestions()
    } catch { showToast('保存失败', 'error') }
  }, [editing, editQuestion, editAnswer, editPoints, fetchQuestions])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const allChecked = questions.length > 0 && questions.every((q) => selected.has(q.id))

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 24, minHeight: 0 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
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
        <CategoryCascade value={category} onChange={setCategory} />
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} style={selectStyle}>
          <option value="">全部来源</option>
          <option value="ai_generated">AI 出题</option>
          <option value="user_question">用户提问</option>
          <option value="auto_mined">问答挖掘</option>
          <option value="manual">手工录入</option>
        </select>
        <select value={reviewStatus} onChange={(e) => setReviewStatus(e.target.value)} style={selectStyle}>
          <option value="">全部审核状态</option>
          <option value="reviewed">已审核</option>
          <option value="pending">待审核</option>
        </select>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>共 {total} 题</span>
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
          <button className="btn btn-danger" style={{ fontSize: 12, padding: '4px 12px' }} disabled={batchWorking} onClick={batchDelete}>
            {batchWorking ? '处理中…' : '批量删除选中'}
          </button>
          <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 12px' }} onClick={() => setSelected(new Set())}>取消选择</button>
        </div>
      )}

      {/* Table */}
      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead><tr style={{ background: 'var(--bg-card)' }}>
            <th style={{ ...thStyle, width: 36, textAlign: 'center' }}>
              <input type="checkbox" checked={allChecked} onChange={(e) => toggleAll(e.target.checked)} />
            </th>
            <th style={{ ...thStyle, width: 46, textAlign: 'center' }}>序号</th>
            <th style={{ ...thStyle, width: 'auto' }}>题目</th>
            <th style={{ ...thStyle, width: 60 }}>分类</th>
            <th style={{ ...thStyle, width: 72 }}>来源</th>
            <th style={{ ...thStyle, width: 70 }}>状态</th>
            <th style={{ ...thStyle, width: 46, textAlign: 'center' }}>使用</th>
            <th style={{ ...thStyle, width: 84 }}>创建时间</th>
            <th style={{ ...thStyle, width: 196 }}>操作</th>
          </tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr>
            ) : questions.length === 0 ? (
              <tr><td colSpan={9} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                暂无符合条件的题目。用户在「智能出题」中作答产生的题目会自动进入待审核列表；也可点击右上角从问答日志挖掘。
              </td></tr>
            ) : questions.map((q, idx) => (
              <tr key={q.id} style={{ background: selected.has(q.id) ? 'var(--primary-light)' : 'transparent' }}>
                <td style={{ ...tdStyle, textAlign: 'center' }}>
                  <input type="checkbox" checked={selected.has(q.id)} onChange={(e) => toggleOne(q.id, e.target.checked)} />
                </td>
                <td style={{ ...tdStyle, textAlign: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{page * PAGE_SIZE + idx + 1}</span>
                </td>
                <td style={tdStyle}>
                  <div
                    onClick={() => setDetail(q)}
                    title={q.question}
                    style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.5, cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text)')}
                  >
                    {q.question}
                  </div>
                  {q.points.length > 0 && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                      {q.points.slice(0, 3).map((p) => (
                        <span key={p.id} style={tagChipStyle}>{p.title.length > 12 ? `${p.title.slice(0, 12)}…` : p.title}</span>
                      ))}
                      {q.points.length > 3 && (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center' }}>+{q.points.length - 3}</span>
                      )}
                    </div>
                  )}
                </td>
                <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{q.category || '-'}</span></td>
                <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{SOURCE_MAP[q.source_type] || q.source_type}</span></td>
                <td style={tdStyle}><span style={statusBadgeStyle(q.status)}>{STATUS_MAP[q.status] || q.status}</span></td>
                <td style={{ ...tdStyle, textAlign: 'center' }}><span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{q.usage_count}</span></td>
                <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{fmtDate(q.created_at)}</span></td>
                <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'nowrap' }}>
                    <button className="btn btn-primary" style={{ fontSize: 12, padding: '4px 6px', flexShrink: 0 }} onClick={() => review(q.id, 'approve')}>通过</button>
                    <button className="btn btn-danger" style={{ fontSize: 12, padding: '4px 6px', flexShrink: 0 }} onClick={() => review(q.id, 'reject')}>驳回</button>
                    <button className="btn btn-danger" style={{ fontSize: 12, padding: '4px 6px', flexShrink: 0 }} onClick={() => openEdit(q)}>编辑</button>
                    <button className="btn btn-danger" style={{ fontSize: 12, padding: '4px 6px', flexShrink: 0 }} onClick={() => deleteQuestion(q.id)}>删除</button>
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

      {/* Detail Modal (read-only) */}
      {detail && (
        <QuestionDetailModal question={detail} onClose={() => setDetail(null)} onError={(m) => showToast(m, 'error')} />
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
              style={{ width: '100%', minHeight: 120, padding: '10px 12px', fontSize: 14, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontFamily: 'var(--font)', marginBottom: 16, boxSizing: 'border-box', resize: 'vertical', lineHeight: 1.6 }}
            />
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>关联知识点（可选多个）</div>
            {editPoints.length > 0 && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                {editPoints.map((p) => (
                  <span key={p.id} style={{ ...tagChipStyle, display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px' }}>
                    {p.title}
                    <span
                      onClick={() => setEditPoints((prev) => prev.filter((x) => x.id !== p.id))}
                      style={{ cursor: 'pointer', fontWeight: 700, lineHeight: 1, fontSize: 12 }}
                      title="移除"
                    >
                      ×
                    </span>
                  </span>
                ))}
              </div>
            )}
            <div style={{ marginBottom: 20 }}>
              <PointPicker onPick={(p) => {
                setEditPoints((prev) => prev.some((x) => x.id === p.id) ? prev : [...prev, p])
              }} />
            </div>
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
