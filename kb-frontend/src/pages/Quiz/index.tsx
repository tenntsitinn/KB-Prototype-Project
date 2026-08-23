import { useState, useCallback, useEffect } from 'react'
import api from '../../services/api'
import type { Phase, Tag, QuizQuestion, QuizAnswerResult, DocumentItem } from './model'
import DocumentTreeSelect from '../../components/DocumentTreeSelect'

const containerStyle: React.CSSProperties = {
  flex: 1, overflow: 'auto', padding: 24,
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
          <h2 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 8px', color: 'var(--text)' }}>智能出题</h2>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 24px', lineHeight: 1.6 }}>
            选择知识范围，AI 基于其中的内容生成开放式问题。勾选标签可全选其下所有文档，也可展开单独勾选文档。一题一卡，作答后即时评分并给出参考答案。
          </p>

          <div style={{ marginBottom: 24 }}>
            <div style={{ ...labelStyle, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>出题范围（按标签分组，勾选标签 = 全选其下文档）</span>
              <span style={{ fontSize: 11 }}>{tags.length} 个标签 · {documents.length} 篇文档</span>
            </div>
            <DocumentTreeSelect
              documents={documents}
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
            {selectedIds.size > 0 ? `开始答题（已选 ${selectedIds.size} 篇）` : '请先选择出题范围'}
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
          已答 {history.length} 题 · 已选 {selectedIds.size} 篇文档
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
