import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import { SOURCE_MAP, type BankQuestion } from '../QuizBank/model'
import CategoryCascade, { emptyCategory, type CategoryValue } from '../../components/CategoryCascade'
import QuestionDetailModal, { fmtDate } from '../../components/QuestionDetailModal'

const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }
const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)', verticalAlign: 'top' }
const selectStyle: React.CSSProperties = { padding: '8px 12px', fontSize: 13, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', cursor: 'pointer' }

const tagChipStyle: React.CSSProperties = {
  fontSize: 11, padding: '1px 8px', borderRadius: 999,
  background: 'var(--primary-light)', color: 'var(--primary)', fontWeight: 500,
}

export default function QuizBrowse() {
  const [questions, setQuestions] = useState<BankQuestion[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [category, setCategory] = useState<CategoryValue>(emptyCategory)
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
          status: 'published',
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
  }, [sourceFilter, category, keyword, page])

  useEffect(() => { fetchQuestions() }, [fetchQuestions])
  useEffect(() => { setPage(0) }, [sourceFilter, category, keyword])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

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
            <th style={{ ...thStyle, width: 64, textAlign: 'center' }}>使用</th>
            <th style={{ ...thStyle, width: 100 }}>创建时间</th>
          </tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr>
            ) : questions.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>暂无符合条件的题目</td></tr>
            ) : questions.map((q, idx) => (
              <tr key={q.id}>
                <td style={{ ...tdStyle, textAlign: 'center' }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{page * PAGE_SIZE + idx + 1}</span>
                </td>
                <td style={tdStyle}>
                  <div
                    onClick={() => setDetail(q)}
                    style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.5, cursor: 'pointer' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text)')}
                  >
                    {q.question.length > 60 ? `${q.question.slice(0, 60)}…` : q.question}
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
                <td style={{ ...tdStyle, textAlign: 'center' }}><span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{q.usage_count}</span></td>
                <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{fmtDate(q.created_at)}</span></td>
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

      {toast.msg && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
