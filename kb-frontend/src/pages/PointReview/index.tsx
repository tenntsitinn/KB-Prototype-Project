import { useState, useCallback, useEffect } from 'react'
import api from '../../services/api'

interface PointItem {
  id: string
  unit_id: string
  unit_title: string
  title: string
  summary: string
  content: string
  status: string
  candidate_merges: { point_id: string; title: string; score: number }[]
  source_units: { unit_id: string; title: string }[]
}

type TabKey = 'pending_review' | 'delete_pending'

const PAGE_SIZE = 10

const containerStyle: React.CSSProperties = {
  flex: 1, overflow: 'auto', padding: 24,
}

const cardStyle: React.CSSProperties = {
  background: 'var(--bg-card)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow)', padding: 20,
  marginBottom: 12,
}

const labelStyle: React.CSSProperties = {
  fontSize: 12, color: 'var(--text-muted)', marginBottom: 6,
}

const chipStyle = (color: string): React.CSSProperties => ({
  fontSize: 11, padding: '2px 8px', borderRadius: 999,
  background: `${color}1a`, color, fontWeight: 500,
})

export default function PointReview() {
  const [tab, setTab] = useState<TabKey>('pending_review')
  const [items, setItems] = useState<PointItem[]>([])
  const [total, setTotal] = useState(0)
  const [counts, setCounts] = useState({ pending_review: 0, delete_pending: 0 })
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [selectAllMode, setSelectAllMode] = useState(false)
  const [batchWorking, setBatchWorking] = useState(false)
  const [editing, setEditing] = useState<PointItem | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [working, setWorking] = useState('')
  const [mergeModal, setMergeModal] = useState(false)
  const [mergeTargetId, setMergeTargetId] = useState('')
  const [mergeTitle, setMergeTitle] = useState('')
  const [mergeWorking, setMergeWorking] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const fetchCounts = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([
        api.get('/api/education/points', { params: { status: 'pending_review', limit: 1 } }),
        api.get('/api/education/points', { params: { status: 'delete_pending', limit: 1 } }),
      ])
      setCounts({ pending_review: a.data?.total || 0, delete_pending: b.data?.total || 0 })
    } catch { /* 忽略 */ }
  }, [])

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/education/points', {
        params: { status: tab, offset: page * PAGE_SIZE, limit: PAGE_SIZE },
      })
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } catch {
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [tab, page])

  useEffect(() => { fetchCounts() }, [fetchCounts])
  useEffect(() => { fetchList() }, [fetchList])
  // 翻页/切换页签时清空勾选，避免跨页残留
  useEffect(() => { setSelected(new Set()); setSelectAllMode(false) }, [page, tab])

  const switchTab = (key: TabKey) => {
    setTab(key)
    setPage(0)
    setExpanded(new Set())
    setSelected(new Set())
    setSelectAllMode(false)
  }

  const refreshAll = () => {
    fetchList()
    fetchCounts()
  }

  const afterAction = () => {
    setSelected(new Set())
    setSelectAllMode(false)
    // 当前页最后一条被处理后，回退一页避免空页
    if (items.length === 1 && page > 0) setPage(page - 1)
    else refreshAll()
  }

  const toggleSelect = (id: string) => {
    if (selectAllMode) {
      // 退出全选模式：以当前页已展示项（去掉本条）转为手动选择
      setSelectAllMode(false)
      setSelected(new Set(items.filter(p => p.id !== id).map(p => p.id)))
      return
    }
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allSelected = tab === 'pending_review' && items.length > 0 && items.every(p => selected.has(p.id))

  const toggleSelectAll = () => {
    if (selectAllMode) {
      setSelectAllMode(false)
      setSelected(new Set())
      return
    }
    setSelected(allSelected ? new Set() : new Set(items.map(p => p.id)))
  }

  const toggleSelectAllMode = () => {
    setSelectAllMode(!selectAllMode)
    setSelected(new Set())
  }

  const batchCount = selectAllMode ? total : selected.size

  const batchConfirm = async () => {
    if (batchCount === 0 || batchWorking) return
    if (!window.confirm(selectAllMode
      ? `确认通过全部 ${total} 个待审核知识点？`
      : `确认通过选中的 ${selected.size} 个知识点？`)) return
    setBatchWorking(true)
    try {
      await api.post('/api/education/points/batch-confirm', selectAllMode ? { all: true } : { point_ids: Array.from(selected) })
      if (selectAllMode) {
        setPage(0)
        setSelectAllMode(false)
        refreshAll()
      } else {
        afterAction()
      }
    } catch (e: any) {
      alert(e?.response?.data?.detail || '批量通过失败，请稍后重试')
    } finally {
      setBatchWorking(false)
    }
  }

  const openMergeModal = () => {
    const selectedItems = items.filter(p => selected.has(p.id))
    if (selectedItems.length < 2) {
      alert('请至少选择 2 个知识点进行合并')
      return
    }
    setMergeTargetId(selectedItems[0].id)
    setMergeTitle(selectedItems[0].title)
    setMergeModal(true)
  }

  const batchMerge = async () => {
    if (!mergeTargetId || mergeWorking) return
    setMergeWorking(true)
    try {
      await api.post('/api/education/points/batch-merge', {
        point_ids: Array.from(selected),
        target_point_id: mergeTargetId,
        new_title: mergeTitle,
      })
      setMergeModal(false)
      afterAction()
    } catch (e: any) {
      alert(e?.response?.data?.detail || '合并失败，请稍后重试')
    } finally {
      setMergeWorking(false)
    }
  }

  const review = useCallback(async (id: string, action: string, extra: Record<string, unknown> = {}): Promise<boolean> => {
    setWorking(id + action)
    try {
      await api.post(`/api/education/points/${id}/review`, { action, ...extra })
      afterAction()
      return true
    } catch (e: any) {
      alert(e?.response?.data?.detail || '操作失败，请稍后重试')
      return false
    } finally {
      setWorking('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, page])

  const deleteReview = useCallback(async (id: string, action: string, extra: Record<string, unknown> = {}): Promise<boolean> => {
    setWorking(id + action)
    try {
      await api.post(`/api/education/points/${id}/delete-review`, { action, ...extra })
      afterAction()
      return true
    } catch (e: any) {
      alert(e?.response?.data?.detail || '操作失败，请稍后重试')
      return false
    } finally {
      setWorking('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, page])

  const openEdit = (p: PointItem) => {
    setEditing(p)
    setEditTitle(p.title)
    setEditContent(p.content)
  }

  const saveEdit = async () => {
    if (!editing) return
    const extra = {
      title: editTitle !== editing.title ? editTitle : '',
      content: editContent !== editing.content ? editContent : '',
    }
    const ok = editing.status === 'delete_pending'
      ? await deleteReview(editing.id, 'keep', extra)
      : await review(editing.id, 'confirm', extra)
    if (ok) setEditing(null)
  }

  const toggleExpand = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: '8px 16px', fontSize: 13, cursor: 'pointer', borderRadius: 8,
    background: active ? 'var(--primary-light)' : 'transparent',
    color: active ? 'var(--primary)' : 'var(--text-muted)',
    fontWeight: active ? 600 : 400, border: '1px solid var(--border)',
  })

  return (
    <div style={containerStyle}>
      {/* Tab */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={tabStyle(tab === 'pending_review')} onClick={() => switchTab('pending_review')}>
            待审核 {counts.pending_review > 0 && <span style={{ fontSize: 11 }}>({counts.pending_review})</span>}
          </div>
          <div style={tabStyle(tab === 'delete_pending')} onClick={() => switchTab('delete_pending')}>
            删除待处理 {counts.delete_pending > 0 && <span style={{ fontSize: 11 }}>({counts.delete_pending})</span>}
          </div>
        </div>
      </div>

      <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 16px', lineHeight: 1.6 }}>
        {tab === 'pending_review'
          ? '文档拆分出的知识点在此确认。语义相近的已列出合并建议，可编辑后确认或直接并入已有知识点。'
          : '删除文档时，融合了多个文档内容的知识点会进入此处。请确认保留（可编辑剔除已删文档的内容）或删除。'}
      </p>

      {/* 批量操作栏（仅待审核） */}
      {tab === 'pending_review' && items.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, padding: '8px 14px',
          background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
        }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)', cursor: 'pointer', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={selectAllMode || allSelected}
              onChange={toggleSelectAll}
              style={{ width: 15, height: 15, accentColor: 'var(--primary)', cursor: 'pointer' }}
            />
            全选本页
          </label>
          {total > PAGE_SIZE && (
            <span
              onClick={toggleSelectAllMode}
              style={{ fontSize: 12, color: 'var(--primary)', cursor: 'pointer', userSelect: 'none' }}
            >
              {selectAllMode ? '取消全选' : `全选所有 (${total})`}
            </span>
          )}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {selectAllMode ? `已选全部 ${total} 项` : `已选 ${selected.size} 项`}
          </span>
          <button
            className="btn btn-outline"
            style={{ fontSize: 12, padding: '5px 16px', marginLeft: 'auto' }}
            disabled={selected.size < 2 || batchWorking || !!working}
            onClick={openMergeModal}
          >
            批量合并
          </button>
          <button
            className="btn btn-primary"
            style={{ fontSize: 12, padding: '5px 16px', marginLeft: 8 }}
            disabled={batchCount === 0 || batchWorking || !!working}
            onClick={batchConfirm}
          >
            {batchWorking ? '处理中…' : `批量通过${batchCount > 0 ? ` (${batchCount})` : ''}`}
          </button>
        </div>
      )}

      {/* 列表 */}
      {loading ? (
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>加载中…</div>
      ) : items.length === 0 ? (
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14, ...cardStyle }}>
          {tab === 'pending_review' ? '暂无待审核知识点' : '暂无删除待处理的知识点'}
        </div>
      ) : items.map(p => {
        const isDeletePending = p.status === 'delete_pending'
        const isExpanded = expanded.has(p.id)
        return (
          <div key={p.id} style={cardStyle}>
            {/* 标题行 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              {!isDeletePending && (
                <input
                  type="checkbox"
                  checked={selectAllMode || selected.has(p.id)}
                  onChange={() => toggleSelect(p.id)}
                  style={{ width: 15, height: 15, accentColor: 'var(--primary)', cursor: 'pointer', flexShrink: 0 }}
                />
              )}
              <span style={{
                fontSize: 15, fontWeight: 600, color: 'var(--text)', flex: 1,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {p.title}
              </span>
              {isDeletePending
                ? <span style={chipStyle('var(--warning, #d97706)')}>删除待处理</span>
                : <span style={chipStyle('var(--primary)')}>待审核</span>}
            </div>

            {/* 归属与来源 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>章节：{p.unit_title}</span>
              {p.source_units.length > 0 && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>·</span>
              )}
              {p.source_units.map(s => (
                <span key={s.unit_id} style={{ fontSize: 11, padding: '1px 7px', borderRadius: 4, background: 'var(--bg-hover, #f1f3f5)', color: 'var(--text-secondary, var(--text))' }}>
                  {s.title}
                </span>
              ))}
            </div>

            {/* 内容 */}
            <div
              style={{
                fontSize: 13, color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-wrap',
                maxHeight: isExpanded ? 'none' : 88, overflow: 'hidden',
                padding: 12, background: 'var(--bg)', borderRadius: 8,
                border: '1px solid var(--border-light)', marginBottom: 10,
              }}
              onClick={() => toggleExpand(p.id)}
            >
              {p.content || '（无内容）'}
            </div>
            <div
              style={{ fontSize: 12, color: 'var(--primary)', cursor: 'pointer', marginBottom: 10, width: 'fit-content' }}
              onClick={() => toggleExpand(p.id)}
            >
              {isExpanded ? '收起' : '展开全文'}
            </div>

            {/* 合并候选（仅待审核） */}
            {!isDeletePending && p.candidate_merges.length > 0 && (
              <div style={{ marginBottom: 12, padding: 10, background: 'var(--bg)', borderRadius: 8, border: '1px dashed var(--border)' }}>
                <div style={{ ...labelStyle, marginBottom: 4 }}>疑似与已有知识点重复，可并入：</div>
                {p.candidate_merges.map(c => (
                  <div key={c.point_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0' }}>
                    <span style={{ fontSize: 12, color: 'var(--text)' }}>{c.title}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>相似度 {(c.score * 100).toFixed(0)}%</span>
                    <button
                      className="btn btn-outline"
                      style={{ fontSize: 11, padding: '2px 10px', marginLeft: 'auto' }}
                      disabled={!!working}
                      onClick={() => review(p.id, 'merge', { merge_into_point_id: c.point_id })}
                    >
                      并入
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* 操作 */}
            <div style={{ display: 'flex', gap: 8 }}>
              {isDeletePending ? (
                <>
                  <button
                    className="btn btn-primary" style={{ fontSize: 12, padding: '5px 14px' }}
                    disabled={!!working}
                    onClick={() => deleteReview(p.id, 'keep')}
                  >
                    保留
                  </button>
                  <button
                    className="btn btn-danger" style={{ fontSize: 12, padding: '5px 14px' }}
                    disabled={!!working}
                    onClick={() => { if (window.confirm(`确认删除知识点「${p.title}」？`)) deleteReview(p.id, 'confirm_delete') }}
                  >
                    确认删除
                  </button>
                </>
              ) : (
                <>
                  <button
                    className="btn btn-primary" style={{ fontSize: 12, padding: '5px 14px' }}
                    disabled={!!working}
                    onClick={() => review(p.id, 'confirm')}
                  >
                    确认
                  </button>
                  <button
                    className="btn btn-danger" style={{ fontSize: 12, padding: '5px 14px' }}
                    disabled={!!working}
                    onClick={() => review(p.id, 'reject')}
                  >
                    拒绝
                  </button>
                </>
              )}
              <button
                className="btn btn-ghost" style={{ fontSize: 12, padding: '5px 14px', marginLeft: 'auto' }}
                onClick={() => openEdit(p)}
              >
                编辑
              </button>
            </div>
          </div>
        )
      })}

      {/* 分页 */}
      {total > PAGE_SIZE && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16, alignItems: 'center' }}>
          <button className="btn btn-ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</button>
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{page + 1} / {totalPages}</span>
          <button className="btn btn-ghost" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>下一页</button>
        </div>
      )}

      {/* 编辑弹窗 */}
      {editing && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
          onClick={(e) => { if (e.target === e.currentTarget) setEditing(null) }}
        >
          <div style={{
            width: '90%', maxWidth: 640, background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)', padding: 24, maxHeight: '80vh', overflow: 'auto',
          }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: 'var(--text)' }}>
              编辑知识点{editing.status === 'delete_pending' ? '（保存后保留）' : '（保存后确认）'}
            </div>
            <div style={labelStyle}>标题</div>
            <input
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              style={{
                width: '100%', boxSizing: 'border-box', padding: '8px 12px', fontSize: 14,
                borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)',
                color: 'var(--text)', fontFamily: 'var(--font)', marginBottom: 16,
              }}
            />
            <div style={labelStyle}>内容</div>
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              style={{
                width: '100%', boxSizing: 'border-box', minHeight: 220, padding: '10px 12px', fontSize: 13,
                borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)',
                color: 'var(--text)', fontFamily: 'var(--font)', resize: 'vertical', lineHeight: 1.7,
                marginBottom: 20,
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button>
              <button className="btn btn-primary" disabled={!!working} onClick={saveEdit}>
                {working ? '保存中…' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 批量合并弹窗 */}
      {mergeModal && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
          onClick={(e) => { if (e.target === e.currentTarget) setMergeModal(false) }}
        >
          <div style={{
            width: '90%', maxWidth: 520, background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)', padding: 24, maxHeight: '80vh', overflow: 'auto',
          }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: 'var(--text)' }}>
              批量合并知识点
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16, lineHeight: 1.6 }}>
              选择保留的目标知识点（其余将被删除，内容拼接到目标），可重命名合并后的标题。
            </p>
            <div style={labelStyle}>选择目标</div>
            <div style={{ marginBottom: 16, maxHeight: 200, overflow: 'auto' }}>
              {items.filter(p => selected.has(p.id)).map(p => (
                <label key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', cursor: 'pointer' }}>
                  <input
                    type="radio"
                    name="merge-target"
                    checked={mergeTargetId === p.id}
                    onChange={() => { setMergeTargetId(p.id); setMergeTitle(p.title) }}
                    style={{ accentColor: 'var(--primary)' }}
                  />
                  <span style={{ fontSize: 13, color: 'var(--text)' }}>{p.title}</span>
                </label>
              ))}
            </div>
            <div style={labelStyle}>合并后标题</div>
            <input
              value={mergeTitle}
              onChange={(e) => setMergeTitle(e.target.value)}
              style={{
                width: '100%', boxSizing: 'border-box', padding: '8px 12px', fontSize: 14,
                borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)',
                color: 'var(--text)', fontFamily: 'var(--font)', marginBottom: 20,
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setMergeModal(false)}>取消</button>
              <button className="btn btn-primary" disabled={mergeWorking} onClick={batchMerge}>
                {mergeWorking ? '合并中…' : '确认合并'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
