import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import { SOURCE_MAP, type BankQuestion } from '../QuizBank/model'
import CategoryCascade, { emptyCategory, type CategoryValue } from '../../components/CategoryCascade'
import QuestionDetailModal, { fmtDate } from '../../components/QuestionDetailModal'

const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }
const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)', verticalAlign: 'top' }
const selectStyle: React.CSSProperties = { padding: '8px 12px', fontSize: 13, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', cursor: 'pointer' }
const inputStyle: React.CSSProperties = {
  padding: '8px 12px', fontSize: 13, borderRadius: 8, border: '1px solid var(--border)',
  background: 'var(--bg-card)', color: 'var(--text)', fontFamily: 'var(--font)', outline: 'none', width: 240,
}

const tagChipStyle: React.CSSProperties = {
  fontSize: 11, padding: '1px 8px', borderRadius: 999,
  background: 'var(--primary-light)', color: 'var(--primary)', fontWeight: 500,
}

const statusChipStyle = (color: string): React.CSSProperties => ({
  fontSize: 11, padding: '2px 8px', borderRadius: 999,
  background: `${color}1a`, color, fontWeight: 500, whiteSpace: 'nowrap',
})

const POINT_STATUS: Record<string, { label: string; color: string }> = {
  confirmed: { label: '已确认', color: 'var(--success, #16a34a)' },
  pending_review: { label: '待审核', color: 'var(--primary)' },
  delete_pending: { label: '删除待处理', color: 'var(--warning, #d97706)' },
}

interface OverviewPoint {
  id: string
  unit_id: string
  unit_title: string
  title: string
  summary: string
  content: string
  status: string
  source_units: { unit_id: string; title: string }[]
  created_at: string
  question_count: number
}

interface SourceOption { unit_id: string; title: string; count: number }

const PAGE_SIZE = 10

export default function KnowledgeOverview() {
  const [view, setView] = useState<'points' | 'questions'>('points')

  // 知识点视图状态
  const [points, setPoints] = useState<OverviewPoint[]>([])
  const [pointTotal, setPointTotal] = useState(0)
  const [sourceOptions, setSourceOptions] = useState<SourceOption[]>([])
  const [ptKeyword, setPtKeyword] = useState('')
  const [ptSearchInput, setPtSearchInput] = useState('')
  const [ptSource, setPtSource] = useState('')
  const [ptStatus, setPtStatus] = useState('')
  const [ptPage, setPtPage] = useState(0)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [pointQuestions, setPointQuestions] = useState<Record<string, BankQuestion[]>>({})
  const [ptQLoading, setPtQLoading] = useState(false)

  // 题目视图状态
  const [questions, setQuestions] = useState<BankQuestion[]>([])
  const [qTotal, setQTotal] = useState(0)
  const [qKeyword, setQKeyword] = useState('')
  const [qSearchInput, setQSearchInput] = useState('')
  const [category, setCategory] = useState<CategoryValue>(emptyCategory)
  const [qSource, setQSource] = useState('')
  const [pointFilter, setPointFilter] = useState<{ id: string; title: string } | null>(null)
  const [qPage, setQPage] = useState(0)

  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<BankQuestion | null>(null)
  const [toast, setToast] = useState({ msg: '', type: '' })

  function showToast(msg: string, type: string) {
    setToast({ msg, type })
    setTimeout(() => setToast({ msg: '', type: '' }), 3000)
  }

  const fetchPoints = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/education/points', {
        params: {
          status: ptStatus, unit_id: ptSource, keyword: ptKeyword,
          offset: ptPage * PAGE_SIZE, limit: PAGE_SIZE,
        },
      })
      setPoints(res.data?.items || [])
      setPointTotal(res.data?.total || 0)
      setSourceOptions(res.data?.source_options || [])
    } catch { showToast('加载知识点失败', 'error') }
    finally { setLoading(false) }
  }, [ptStatus, ptSource, ptKeyword, ptPage])

  const fetchQuestions = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/quiz/bank', {
        params: {
          status: 'published',
          source_type: qSource,
          course_id: category.courseId,
          chapter_id: category.chapterId,
          point_id: pointFilter?.id || category.pointId,
          keyword: qKeyword,
          offset: qPage * PAGE_SIZE, limit: PAGE_SIZE,
        },
      })
      setQuestions(res.data?.items || [])
      setQTotal(res.data?.total || 0)
    } catch { showToast('加载题目失败', 'error') }
    finally { setLoading(false) }
  }, [qSource, category, pointFilter, qKeyword, qPage])

  useEffect(() => { fetchPoints() }, [fetchPoints])
  useEffect(() => { fetchQuestions() }, [fetchQuestions])
  useEffect(() => { setPtPage(0) }, [ptStatus, ptSource, ptKeyword])
  useEffect(() => { setQPage(0) }, [qSource, category, pointFilter, qKeyword])

  // 展开知识点时懒加载其关联题目
  useEffect(() => {
    if (!expanded || pointQuestions[expanded]) return
    let cancelled = false
    setPtQLoading(true)
    api.get('/api/quiz/bank', { params: { status: 'published', point_id: expanded, offset: 0, limit: 20 } })
      .then((res) => { if (!cancelled) setPointQuestions((prev) => ({ ...prev, [expanded]: res.data?.items || [] })) })
      .catch(() => { if (!cancelled) setPointQuestions((prev) => ({ ...prev, [expanded]: [] })) })
      .finally(() => { if (!cancelled) setPtQLoading(false) })
    return () => { cancelled = true }
  }, [expanded, pointQuestions])

  const jumpToQuestions = (point: { id: string; title: string }) => {
    setView('questions')
    setPointFilter(point)
    setQPage(0)
  }

  const ptTotalPages = Math.max(1, Math.ceil(pointTotal / PAGE_SIZE))
  const qTotalPages = Math.max(1, Math.ceil(qTotal / PAGE_SIZE))

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 24, minHeight: 0 }}>
      {/* 视图切换 + 说明 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 4, padding: 4, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10 }}>
          {(['points', 'questions'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              style={{
                padding: '6px 18px', fontSize: 13, borderRadius: 7, border: 'none', cursor: 'pointer',
                background: view === v ? 'var(--bg-card)' : 'transparent',
                color: view === v ? 'var(--primary)' : 'var(--text-muted)',
                fontWeight: view === v ? 600 : 400, fontFamily: 'var(--font)',
                boxShadow: view === v ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
              }}
            >
              {v === 'points' ? `知识点${view === 'points' && !loading ? ` (${pointTotal})` : ''}` : `题目${view === 'questions' && !loading ? ` (${qTotal})` : ''}`}
            </button>
          ))}
        </div>
        <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          统一浏览知识库沉淀的知识点与题目，点击知识点可展开内容与关联题目
        </span>
      </div>

      {/* ============ 知识点视图 ============ */}
      {view === 'points' && (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              value={ptSearchInput}
              onChange={(e) => setPtSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') setPtKeyword(ptSearchInput.trim()) }}
              placeholder="搜索知识点标题/内容，回车确认"
              style={inputStyle}
            />
            <select value={ptSource} onChange={(e) => setPtSource(e.target.value)} style={selectStyle}>
              <option value="">全部来源章节</option>
              {sourceOptions.map((s) => (
                <option key={s.unit_id} value={s.unit_id}>{s.title}（{s.count}）</option>
              ))}
            </select>
            <select value={ptStatus} onChange={(e) => setPtStatus(e.target.value)} style={selectStyle}>
              <option value="">全部状态</option>
              <option value="pending_review">待审核</option>
              <option value="confirmed">已确认</option>
              <option value="delete_pending">删除待处理</option>
            </select>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>共 {pointTotal} 个知识点</span>
          </div>

          <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr style={{ background: 'var(--bg-card)' }}>
                <th style={{ ...thStyle, width: 72, textAlign: 'center' }}>序号</th>
                <th style={thStyle}>知识点</th>
                <th style={{ ...thStyle, width: 140 }}>所属章节</th>
                <th style={{ ...thStyle, width: 96 }}>状态</th>
                <th style={{ ...thStyle, width: 80, textAlign: 'center' }}>关联题目</th>
                <th style={{ ...thStyle, width: 220 }}>内容摘要</th>
                <th style={{ ...thStyle, width: 100 }}>创建时间</th>
              </tr></thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr>
                ) : points.length === 0 ? (
                  <tr><td colSpan={7} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>暂无符合条件的知识点</td></tr>
                ) : points.map((p, idx) => (
                  <>
                    <tr key={p.id}>
                      <td style={{ ...tdStyle, textAlign: 'center' }}>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{ptPage * PAGE_SIZE + idx + 1}</span>
                      </td>
                      <td style={tdStyle}>
                        <div
                          onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                          style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.5, cursor: 'pointer', fontWeight: 500 }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary)')}
                          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text)')}
                        >
                          {expanded === p.id ? '▾ ' : '▸ '}{p.title}
                        </div>
                      </td>
                      <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{p.unit_title}</span></td>
                      <td style={tdStyle}>
                        <span style={statusChipStyle(POINT_STATUS[p.status]?.color || 'var(--text-muted)')}>
                          {POINT_STATUS[p.status]?.label || p.status}
                        </span>
                      </td>
                      <td style={{ ...tdStyle, textAlign: 'center' }}>
                        {p.question_count > 0 ? (
                          <span
                            onClick={() => jumpToQuestions({ id: p.id, title: p.title })}
                            style={{ fontSize: 13, color: 'var(--primary)', cursor: 'pointer', fontWeight: 600 }}
                            title="在题目视图查看该知识点的题目"
                          >
                            {p.question_count}
                          </span>
                        ) : (
                          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>0</span>
                        )}
                      </td>
                      <td style={tdStyle}>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                          {p.summary ? (p.summary.length > 40 ? `${p.summary.slice(0, 40)}…` : p.summary) : '—'}
                        </span>
                      </td>
                      <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{fmtDate(p.created_at)}</span></td>
                    </tr>
                    {expanded === p.id && (
                      <tr key={`${p.id}-detail`}>
                        <td colSpan={7} style={{ padding: '16px 20px', background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}>
                          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                            <div style={{ flex: '1 1 320px', minWidth: 280 }}>
                              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>知识点内容</div>
                              <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                                {p.content || '（无内容）'}
                              </div>
                              {p.source_units.length > 0 && (
                                <div style={{ marginTop: 12, display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>来源文档：</span>
                                  {p.source_units.map((s) => (
                                    <span key={s.unit_id} style={tagChipStyle}>{s.title}</span>
                                  ))}
                                </div>
                              )}
                            </div>
                            <div style={{ flex: '1 1 320px', minWidth: 280 }}>
                              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                                关联题目（已发布）
                              </div>
                              {ptQLoading && !pointQuestions[p.id] ? (
                                <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>加载中...</div>
                              ) : (pointQuestions[p.id] || []).length === 0 ? (
                                <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '8px 0' }}>暂无关联题目</div>
                              ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                  {(pointQuestions[p.id] || []).slice(0, 5).map((q) => (
                                    <div
                                      key={q.id}
                                      onClick={() => setDetail(q)}
                                      style={{
                                        fontSize: 13, color: 'var(--text)', cursor: 'pointer', lineHeight: 1.5,
                                        padding: '6px 10px', background: 'var(--bg)', borderRadius: 8, border: '1px solid var(--border-light)',
                                      }}
                                      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--primary)')}
                                      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-light)')}
                                    >
                                      {q.question.length > 50 ? `${q.question.slice(0, 50)}…` : q.question}
                                    </div>
                                  ))}
                                  {(pointQuestions[p.id] || []).length > 5 && (
                                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                      +{(pointQuestions[p.id] || []).length - 5} 题
                                    </span>
                                  )}
                                  <button className="btn btn-outline" style={{ fontSize: 12, padding: '4px 12px', width: 'fit-content' }} onClick={() => jumpToQuestions({ id: p.id, title: p.title })}>
                                    在题目视图查看全部
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          {pointTotal > PAGE_SIZE && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16, alignItems: 'center' }}>
              <button className="btn btn-ghost" disabled={ptPage === 0} onClick={() => setPtPage(ptPage - 1)}>上一页</button>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{ptPage + 1} / {ptTotalPages}</span>
              <button className="btn btn-ghost" disabled={ptPage >= ptTotalPages - 1} onClick={() => setPtPage(ptPage + 1)}>下一页</button>
            </div>
          )}
        </>
      )}

      {/* ============ 题目视图 ============ */}
      {view === 'questions' && (
        <>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              value={qSearchInput}
              onChange={(e) => setQSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') setQKeyword(qSearchInput.trim()) }}
              placeholder="搜索题目/答案关键词，回车确认"
              style={inputStyle}
            />
            <CategoryCascade value={category} onChange={setCategory} />
            <select value={qSource} onChange={(e) => setQSource(e.target.value)} style={selectStyle}>
              <option value="">全部来源</option>
              <option value="ai_generated">AI 出题</option>
              <option value="user_question">用户提问</option>
              <option value="auto_mined">问答挖掘</option>
              <option value="manual">手工录入</option>
            </select>
            {pointFilter && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '4px 10px', borderRadius: 999, background: 'var(--primary-light)', color: 'var(--primary)', fontWeight: 500, whiteSpace: 'nowrap' }}>
                知识点：{pointFilter.title.length > 12 ? `${pointFilter.title.slice(0, 12)}…` : pointFilter.title}
                <span style={{ cursor: 'pointer', fontWeight: 700 }} onClick={() => setPointFilter(null)} title="清除筛选">✕</span>
              </span>
            )}
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>共 {qTotal} 题</span>
          </div>

          <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr style={{ background: 'var(--bg-card)' }}>
                <th style={{ ...thStyle, width: 72, textAlign: 'center' }}>序号</th>
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
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{qPage * PAGE_SIZE + idx + 1}</span>
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

          {qTotal > PAGE_SIZE && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16, alignItems: 'center' }}>
              <button className="btn btn-ghost" disabled={qPage === 0} onClick={() => setQPage(qPage - 1)}>上一页</button>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{qPage + 1} / {qTotalPages}</span>
              <button className="btn btn-ghost" disabled={qPage >= qTotalPages - 1} onClick={() => setQPage(qPage + 1)}>下一页</button>
            </div>
          )}
        </>
      )}

      {detail && (
        <QuestionDetailModal question={detail} onClose={() => setDetail(null)} onError={(m) => showToast(m, 'error')} />
      )}

      {toast.msg && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
