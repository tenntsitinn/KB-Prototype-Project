import { useState, useCallback, useEffect, useMemo } from 'react'
import api from '../../services/api'
import type { Phase, Tag, QuizQuestion, QuizAnswerResult, DocumentItem } from './model'
import DocumentTreeSelect from '../../components/DocumentTreeSelect'

const containerStyle: React.CSSProperties = {
  flex: 1, overflow: 'auto', padding: 24, minHeight: 0,
  display: 'flex', flexDirection: 'column', alignItems: 'center',
}

const cardStyle: React.CSSProperties = {
  width: '100%', maxWidth: 720, background: 'var(--bg-card)',
  border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
  boxShadow: 'var(--shadow)', padding: 32,
}

const labelStyle: React.CSSProperties = {
  fontSize: 12, color: 'var(--text-muted)', marginBottom: 6,
}

const scoreColor = (score: number) =>
  score >= 90 ? 'var(--success, #16a34a)' : score >= 70 ? 'var(--primary)' : score >= 40 ? 'var(--warning, #d97706)' : 'var(--danger, #dc2626)'

export default function Quiz() {
  const [phase, setPhase] = useState<Phase>('select')
  const [tags, setTags] = useState<Tag[]>([])
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const [loading, setLoading] = useState(false)
  const [current, setCurrent] = useState<QuizQuestion | null>(null)
  const [answerText, setAnswerText] = useState('')
  const [result, setResult] = useState<QuizAnswerResult | null>(null)
  const [askedIds, setAskedIds] = useState<string[]>([])
  const [history, setHistory] = useState<{question: string; score: number}[]>([])
  const [error, setError] = useState('')
  const [selectedCourse, setSelectedCourse] = useState<string>('')
  const [courseOpen, setCourseOpen] = useState(false)

  const courses = useMemo(() => {
    const set = new Set(documents.map(d => d.category).filter(Boolean))
    return Array.from(set).sort()
  }, [documents])

  const filteredDocuments = useMemo(() => {
    if (!selectedCourse) return documents
    return documents.filter(d => d.category === selectedCourse)
  }, [documents, selectedCourse])

  useEffect(() => {
    api.get('/api/tags').then((res) => {
      setTags(Array.isArray(res.data) ? res.data : res.data?.data || [])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (documents.length > 0) return
    api.get('/api/knowledge/units', { params: { status: 'published', limit: 500 } }).then((res) => {
      const items = res.data?.items || []
      setDocuments(items.map((u: any) => ({ id: u.id, title: u.title, category: u.category })))
    }).catch(() => {})
  }, [documents.length])

  const startQuiz = useCallback(() => {
    if (selectedIds.size === 0) return
    setAskedIds([])
    setHistory([])
    setPhase('question')
    fetchNext([])
  }, [selectedIds])

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
      setError('原文档加载失败')
    }
  }, [])

  const fetchNext = useCallback(async (asked: string[]) => {
    setLoading(true)
    setError('')
    setResult(null)
    setAnswerText('')
    try {
      const payload: Record<string, any> = {
        asked_question_ids: asked,
        source_unit_ids: Array.from(selectedIds),
      }
      const res = await api.post('/api/quiz/next', payload)
      setCurrent(res.data)
    } catch (e: any) {
      setCurrent(null)
      setError(e?.response?.data?.detail || '出题失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [selectedIds])

  const submitAnswer = useCallback(async () => {
    if (!current) return
    setPhase('grading')
    try {
      const res = await api.post('/api/quiz/answer', {
        question_id: current.question_id,
        answer_text: answerText,
      })
      setResult(res.data)
      setHistory((prev) => [...prev, { question: current.question, score: res.data.score }])
      setPhase('result')
    } catch (e: any) {
      setError(e?.response?.data?.detail || '判分失败，请稍后重试')
      setPhase('question')
    }
  }, [current, answerText])

  const nextCard = useCallback(() => {
    const asked = current ? [...askedIds, current.question_id] : askedIds
    setAskedIds(asked)
    setPhase('question')
    fetchNext(asked)
  }, [current, askedIds, fetchNext])

  const skipCard = useCallback(() => {
    const asked = current ? [...askedIds, current.question_id] : askedIds
    setAskedIds(asked)
    setPhase('question')
    fetchNext(asked)
  }, [current, askedIds, fetchNext])

  const exitQuiz = useCallback(() => {
    setPhase('select')
    setCurrent(null)
    setResult(null)
  }, [])

  // ===== 范围选择 =====
  if (phase === 'select') {
    return (
      <div style={containerStyle}>
        <div style={cardStyle}>
          {/* 顶部：标题 + 课程选择 */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
            <h2 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: 'var(--text)' }}>智能出题</h2>
            {/* 课程下拉选择 */}
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setCourseOpen(!courseOpen)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 12px', borderRadius: 6,
                  border: '1px solid var(--border)', background: 'var(--bg)',
                  fontSize: 13, color: 'var(--text)', cursor: 'pointer',
                  fontFamily: 'var(--font)',
                }}
              >
                <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>课程</span>
                <span style={{ fontWeight: 500 }}>{selectedCourse || '全部'}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"
                  style={{ transform: courseOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {courseOpen && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 10,
                  minWidth: 160, background: 'var(--bg-card)', border: '1px solid var(--border)',
                  borderRadius: 8, boxShadow: 'var(--shadow)', overflow: 'hidden',
                }}>
                  <div
                    onClick={() => { setSelectedCourse(''); setSelectedIds(new Set()); setCourseOpen(false) }}
                    style={{
                      padding: '8px 14px', fontSize: 13, cursor: 'pointer',
                      background: !selectedCourse ? 'var(--primary-light, rgba(59,130,246,0.08))' : 'transparent',
                      color: !selectedCourse ? 'var(--primary)' : 'var(--text)',
                      fontWeight: !selectedCourse ? 600 : 400,
                    }}
                  >
                    全部 <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>{documents.length}</span>
                  </div>
                  {courses.map(c => {
                    const count = documents.filter(d => d.category === c).length
                    const active = selectedCourse === c
                    return (
                      <div
                        key={c}
                        onClick={() => { setSelectedCourse(c); setSelectedIds(new Set()); setCourseOpen(false) }}
                        style={{
                          padding: '8px 14px', fontSize: 13, cursor: 'pointer',
                          background: active ? 'var(--primary-light, rgba(59,130,246,0.08))' : 'transparent',
                          color: active ? 'var(--primary)' : 'var(--text)',
                          fontWeight: active ? 600 : 400,
                          borderTop: '1px solid var(--border-light)',
                        }}
                      >
                        {c} <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>{count}</span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 20px', lineHeight: 1.6 }}>
            选择出题范围，AI 基于章节中的知识点生成开放式问题。勾选章节即覆盖其下全部知识点。一题一卡，作答后即时评分并给出参考答案。
          </p>

          <div style={{ marginBottom: 24 }}>
            <div style={{ ...labelStyle, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>出题范围{selectedCourse ? ` — ${selectedCourse}` : ''}</span>
              <span style={{ fontSize: 11 }}>{filteredDocuments.length} 个章节</span>
            </div>
            <DocumentTreeSelect
              documents={filteredDocuments}
              selectedIds={selectedIds}
              onChange={setSelectedIds}
            />
          </div>

          <button
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center', padding: '12px 0', fontSize: 15 }}
            disabled={selectedIds.size === 0}
            onClick={startQuiz}
          >
            {selectedIds.size > 0 ? `开始答题（已选 ${selectedIds.size} 个章节）` : '请先选择出题范围'}
          </button>
          {history.length > 0 && (
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border-light)' }}>
              <div style={labelStyle}>上一轮成绩</div>
              <div style={{ fontSize: 14, color: 'var(--text)' }}>
                {history.length} 题，平均分{' '}
                <span style={{ fontWeight: 600, color: scoreColor(Math.round(history.reduce((s, h) => s + h.score, 0) / history.length)) }}>
                  {Math.round(history.reduce((s, h) => s + h.score, 0) / history.length)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ===== 答题卡 =====
  return (
    <div style={containerStyle}>
      {/* 进度提示 */}
      <div style={{
        width: '100%', maxWidth: 720, display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 12, fontSize: 13, color: 'var(--text-muted)',
      }}>
        <span>
          已答 {history.length} 题 · 已选 {selectedIds.size} 个章节
        </span>
        <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 10px' }} onClick={exitQuiz}>
          退出本轮
        </button>
      </div>

      <div style={cardStyle}>
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
            正在出题…
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{ padding: 32, color: 'var(--danger)', fontSize: 14 }}>{error}</div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button className="btn btn-ghost" onClick={() => fetchNext(askedIds)}>重试</button>
              <button className="btn btn-outline" onClick={exitQuiz}>返回选择范围</button>
            </div>
          </div>
        ) : current ? (
          <>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
            }}>
              <span style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 999,
                background: current.from_bank ? 'var(--primary-light)' : 'var(--bg-hover, #f1f3f5)',
                color: current.from_bank ? 'var(--primary)' : 'var(--text-muted)',
                fontWeight: 500,
              }}>
                {current.from_bank ? '题库' : '实时生成'}
              </span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>第 {askedIds.length + 1} 题</span>
            </div>

            <div style={{ fontSize: 17, fontWeight: 600, lineHeight: 1.6, color: 'var(--text)', marginBottom: 20, whiteSpace: 'pre-wrap' }}>
              {current.question}
            </div>

            <div style={labelStyle}>你的回答</div>
            <textarea
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              disabled={phase === 'grading'}
              placeholder="在此作答，留空提交则视为未作答"
              style={{
                width: '100%', minHeight: 140, padding: '12px 14px', fontSize: 14,
                borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)',
                color: 'var(--text)', fontFamily: 'var(--font)', resize: 'vertical',
                lineHeight: 1.6, boxSizing: 'border-box', marginBottom: 20,
              }}
            />

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-primary"
                style={{ flex: 1, justifyContent: 'center', padding: '10px 0' }}
                disabled={phase === 'grading'}
                onClick={submitAnswer}
              >
                {phase === 'grading' ? '评分中…' : '提交作答'}
              </button>
              <button
                className="btn btn-outline"
                disabled={phase === 'grading'}
                onClick={skipCard}
              >
                跳过
              </button>
            </div>
          </>
        ) : null}
      </div>

      {/* 判分结果 */}
      {phase === 'result' && result && (
        <div style={{ ...cardStyle, marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 16 }}>
            <span style={{ fontSize: 32, fontWeight: 700, color: scoreColor(result.score) }}>
              {result.score}
            </span>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>分</span>
            <span style={{
              fontSize: 13, color: 'var(--text)',
              background: 'var(--bg-hover, #f1f3f5)', borderRadius: 6, padding: '4px 10px',
            }}>
              {result.score >= 90 ? '优秀' : result.score >= 70 ? '良好' : result.score >= 40 ? '待加强' : '未通过'}
            </span>
          </div>

          <div style={labelStyle}>评语</div>
          <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.6, marginBottom: 16, whiteSpace: 'pre-wrap' }}>
            {result.feedback || '暂无评语'}
          </div>

          <div style={labelStyle}>参考答案</div>
          <div style={{
            fontSize: 14, color: 'var(--text)', lineHeight: 1.7, marginBottom: 16,
            padding: 14, background: 'var(--bg)', borderRadius: 8,
            border: '1px solid var(--border-light)', whiteSpace: 'pre-wrap',
          }}>
            {result.reference_answer || '（本题暂无参考答案）'}
          </div>

          {result.source_unit_id && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>
              题目来源文档：
              <a
                href="#"
                onClick={(e) => { e.preventDefault(); openSource(result.source_unit_id) }}
                style={{ color: 'var(--primary)' }}
              >
                查看原文
              </a>
            </div>
          )}

          <button
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center', padding: '10px 0' }}
            onClick={nextCard}
          >
            下一题
          </button>
        </div>
      )}
    </div>
  )
}
