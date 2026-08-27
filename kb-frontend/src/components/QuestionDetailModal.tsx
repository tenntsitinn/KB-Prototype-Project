import api from '../services/api'
import { SOURCE_MAP, STATUS_MAP, type BankQuestion } from '../pages/QuizBank/model'

export function statusBadgeStyle(status: string): React.CSSProperties {
  return {
    fontSize: 11, padding: '2px 8px', borderRadius: 999, fontWeight: 500,
    background: status === 'published' ? 'rgba(52, 168, 83, 0.12)'
      : status === 'pending_review' ? 'var(--primary-light)'
      : status === 'rejected' ? 'rgba(234, 67, 53, 0.12)'
      : 'var(--bg-hover)',
    color: status === 'published' ? 'var(--success)'
      : status === 'pending_review' ? 'var(--primary)'
      : status === 'rejected' ? 'var(--danger)'
      : 'var(--text-muted)',
  }
}

export function fmtDate(v: string | null): string {
  if (!v) return '-'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '-' : d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const tagChipStyle: React.CSSProperties = {
  fontSize: 11, padding: '2px 8px', borderRadius: 999,
  background: 'var(--primary-light)', color: 'var(--primary)', fontWeight: 500,
}

export default function QuestionDetailModal({ question, onClose, onError }: {
  question: BankQuestion
  onClose: () => void
  onError?: (msg: string) => void
}) {
  const openSource = async (unitId: string) => {
    const win = window.open('about:blank', '_blank')
    try {
      const res = await api.get(`/api/knowledge/units/${unitId}/file-url`)
      const url: string = res.data?.url
      if (!url) throw new Error('no url')
      if (win) win.location.href = url
      else window.open(url, '_blank')
    } catch {
      win?.close()
      onError?.('原文档加载失败')
    }
  }

  const metaItem = (k: string, v: React.ReactNode) => (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>{k}</div>
      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{v}</div>
    </div>
  )

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{
        width: '90%', maxWidth: 640, background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-lg)', padding: 24, maxHeight: '80vh', overflow: 'auto',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)' }}>题目详情</div>
          <span style={{ ...statusBadgeStyle(question.status), fontSize: 12 }}>{STATUS_MAP[question.status] || question.status}</span>
        </div>
        <div style={{ fontSize: 14, color: 'var(--text)', lineHeight: 1.7, marginBottom: 12 }}>{question.question}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>参考答案</div>
        <div style={{
          fontSize: 13, color: 'var(--text)', lineHeight: 1.8, marginBottom: 16,
          padding: 14, background: 'var(--bg)', borderRadius: 8, border: '1px solid var(--border-light)',
          whiteSpace: 'pre-wrap',
        }}>
          {question.reference_answer || '（暂无参考答案）'}
        </div>
        {question.points.length > 0 && (
          <>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>关联知识点</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
              {question.points.map((p) => (
                <span key={p.id} style={tagChipStyle}>{p.title}</span>
              ))}
            </div>
          </>
        )}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
          paddingTop: 16, borderTop: '1px solid var(--border-light)',
        }}>
          {metaItem('分类', question.category || '-')}
          {metaItem('来源', SOURCE_MAP[question.source_type] || question.source_type)}
          {metaItem('使用次数', question.usage_count)}
          {metaItem('审核人', question.reviewer_name || '未审核')}
          {metaItem('审核时间', fmtDate(question.reviewed_at))}
          {metaItem('创建时间', fmtDate(question.created_at))}
          {metaItem('编号', <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 12 }}>{question.id}</span>)}
          {metaItem('来源文档', question.source_unit_id
            ? <a href="#" onClick={(e) => { e.preventDefault(); openSource(question.source_unit_id) }} style={{ color: 'var(--primary)', cursor: 'pointer' }}>查看原文 →</a>
            : '-')}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
          <button className="btn btn-primary" onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  )
}
