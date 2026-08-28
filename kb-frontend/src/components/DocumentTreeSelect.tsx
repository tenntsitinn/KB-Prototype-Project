import { useState, useMemo, useCallback, useEffect } from 'react'
import api from '../services/api'

export interface TreeDocument {
  id: string
  title: string
  category: string
}

interface PointBrief {
  id: string
  title: string
  status: string
}

interface UnitPoints {
  points_status: string
  points_error: string
  points: PointBrief[]
}

interface DocumentTreeSelectProps {
  documents: TreeDocument[]
  selectedIds: Set<string>
  onChange: (ids: Set<string>) => void
  selectedPointIds?: Set<string>
  onPointIdsChange?: (ids: Set<string>) => void
}

const POINTS_STATUS_TEXT: Record<string, string> = {
  extracting: '知识点拆分中…',
  failed: '知识点拆分失败',
}

export default function DocumentTreeSelect({
  documents, selectedIds, onChange, selectedPointIds, onPointIdsChange,
}: DocumentTreeSelectProps) {
  const [query, setQuery] = useState('')
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [pointsMap, setPointsMap] = useState<Record<string, UnitPoints>>({})
  const [pointsLoaded, setPointsLoaded] = useState(false)
  const pointSelectionEnabled = Boolean(selectedPointIds && onPointIdsChange)

  const unitIdsKey = useMemo(
    () => documents.map(d => d.id).join(','),
    [documents],
  )

  useEffect(() => {
    if (!unitIdsKey) return
    let cancelled = false
    setPointsLoaded(false)
    api.post('/api/education/points/batch', { unit_ids: unitIdsKey.split(',') })
      .then((res) => {
        if (cancelled) return
        setPointsMap(res.data?.units || {})
        setPointsLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setPointsLoaded(true)
      })
    return () => { cancelled = true }
  }, [unitIdsKey])

  const filteredDocs = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return documents
    return documents.filter(d => {
      if (d.title.toLowerCase().includes(q)) return true
      return (pointsMap[d.id]?.points || []).some(p => p.title.toLowerCase().includes(q))
    }).sort((a, b) => a.title.localeCompare(b.title))
  }, [documents, query, pointsMap])

  const toggleCollapse = useCallback((id: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleDoc = useCallback((id: string) => {
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(next)
  }, [selectedIds, onChange])

  const togglePoint = useCallback((pointId: string) => {
    if (!selectedPointIds || !onPointIdsChange) return
    const next = new Set(selectedPointIds)
    if (next.has(pointId)) next.delete(pointId)
    else next.add(pointId)
    onPointIdsChange(next)
  }, [selectedPointIds, onPointIdsChange])

  const allPointIds = useMemo(
    () => filteredDocs.flatMap(d => (pointsMap[d.id]?.points || []).map(p => p.id)),
    [filteredDocs, pointsMap],
  )

  const selectAll = useCallback(() => {
    onChange(new Set(filteredDocs.map(d => d.id)))
    if (selectedPointIds && onPointIdsChange && allPointIds.length > 0) {
      onPointIdsChange(new Set(allPointIds))
    }
  }, [filteredDocs, onChange, selectedPointIds, onPointIdsChange, allPointIds])

  const clearAll = useCallback(() => {
    onChange(new Set())
    if (selectedPointIds && onPointIdsChange) onPointIdsChange(new Set())
  }, [onChange, selectedPointIds, onPointIdsChange])

  const allSelected = filteredDocs.length > 0 && filteredDocs.every(d => selectedIds.has(d.id))

  const checkboxStyle = (checked: boolean, indeterminate: boolean): React.CSSProperties => ({
    width: 16, height: 16, borderRadius: 3, border: `1.5px solid ${checked || indeterminate ? 'var(--primary)' : 'var(--border)'}`,
    background: checked ? 'var(--primary)' : 'transparent',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, cursor: 'pointer', transition: 'all 0.15s',
  })

  const checkMark = () => (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )

  const indeterminateMark = () => (
    <div style={{ width: 8, height: 2, background: 'var(--primary)', borderRadius: 1 }} />
  )

  const pointBody = (unitId: string) => {
    if (!pointsLoaded) {
      return <div style={{ padding: '4px 0', fontSize: 12, color: 'var(--text-muted)' }}>知识点加载中…</div>
    }
    const entry = pointsMap[unitId]
    const statusText = POINTS_STATUS_TEXT[entry?.points_status || 'none']
    if (statusText) {
      const isFailed = entry?.points_status === 'failed'
      const errorMsg = entry?.points_error || ''
      const isBalanceError = errorMsg.includes('Insufficient Balance') || errorMsg.includes('余额')
      return (
        <div style={{ padding: '4px 0', fontSize: 12 }}>
          <span style={{ color: isFailed ? 'var(--warning, #d97706)' : 'var(--text-muted)' }}>
            {statusText}
          </span>
          {isFailed && errorMsg && (
            <span style={{ color: 'var(--error, #dc2626)', marginLeft: 6 }}>
              {isBalanceError ? '（API 余额不足，请更换 Key 后重新提取）' : `（${errorMsg}）`}
            </span>
          )}
        </div>
      )
    }
    const points = entry?.points || []
    if (points.length === 0) {
      return <div style={{ padding: '4px 0', fontSize: 12, color: 'var(--text-muted)' }}>暂无知识点</div>
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '2px 0' }}>
        {points.map(p => {
          const pointChecked = Boolean(selectedPointIds?.has(p.id))
          return (
            <div
              key={p.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: pointSelectionEnabled ? '2px 0' : 0,
                cursor: pointSelectionEnabled ? 'pointer' : 'default',
              }}
              onClick={pointSelectionEnabled ? () => togglePoint(p.id) : undefined}
            >
              {pointSelectionEnabled && (
                <div style={checkboxStyle(pointChecked, false)} onClick={(e) => { e.stopPropagation(); togglePoint(p.id) }}>
                  {pointChecked ? checkMark() : null}
                </div>
              )}
              <span style={{
                width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
                background: p.status === 'pending_review' ? 'var(--warning, #d97706)' : 'var(--success, #16a34a)',
              }} />
              <span style={{
                fontSize: 12, color: 'var(--text-secondary, var(--text))',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {p.title}
              </span>
              {p.status === 'pending_review' && (
                <span style={{ fontSize: 10, color: 'var(--warning, #d97706)', flexShrink: 0 }}>待审核</span>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg)', overflow: 'hidden' }}>
      {/* 搜索栏 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 10px', borderBottom: '1px solid var(--border-light)' }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" style={{ flexShrink: 0 }}>
          <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索章节…"
          style={{
            flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent',
            fontFamily: 'var(--font)', fontSize: 13, color: 'var(--text)',
          }}
        />
        {query && (
          <span onClick={() => setQuery('')} style={{ cursor: 'pointer', color: 'var(--text-muted)', fontSize: 14, flexShrink: 0 }}>×</span>
        )}
      </div>

      {/* 全选 / 清空 */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
        borderBottom: '1px solid var(--border-light)',
      }}>
        <div style={checkboxStyle(allSelected, selectedIds.size > 0 && !allSelected)} onClick={allSelected ? clearAll : selectAll}>
          {allSelected ? checkMark() : selectedIds.size > 0 ? indeterminateMark() : null}
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {selectedIds.size > 0 || (selectedPointIds?.size || 0) > 0
            ? `已选 ${selectedIds.size} 个章节${pointSelectionEnabled && selectedPointIds ? ` · ${selectedPointIds.size} 个知识点` : ''}`
            : '全选章节'}
        </span>
        {selectedIds.size > 0 && (
          <button onClick={clearAll} style={{
            marginLeft: 'auto', border: 'none', background: 'transparent',
            color: 'var(--primary)', fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font)',
          }}>
            清空
          </button>
        )}
      </div>

      {/* 章节列表 */}
      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {filteredDocs.map(d => {
          const checked = selectedIds.has(d.id)
          const isCollapsed = collapsed.has(d.id) && !query
          const points = pointsMap[d.id]?.points
          const pointCount = points?.length ?? 0

          return (
            <div key={d.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
              {/* 章节行 */}
              <div
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
                  cursor: 'pointer',
                }}
                onClick={() => toggleCollapse(d.id)}
              >
                {/* 展开箭头 */}
                <svg
                  width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"
                  style={{ flexShrink: 0, transition: 'transform 0.15s', transform: isCollapsed ? 'rotate(-90deg)' : 'none' }}
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                {/* 章节 checkbox */}
                <div style={checkboxStyle(checked, false)} onClick={(e) => { e.stopPropagation(); toggleDoc(d.id) }}>
                  {checked ? checkMark() : null}
                </div>
                {/* 章节名 */}
                <span style={{
                  fontSize: 13, fontWeight: 500, color: 'var(--text)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {d.title}
                </span>
                {/* 知识点数量 */}
                {pointCount > 0 && (
                  <span style={{ marginLeft: 'auto', flexShrink: 0, fontSize: 11, color: 'var(--text-muted)' }}>
                    {pointCount} 个知识点
                  </span>
                )}
              </div>

              {/* 知识点列表 */}
              {!isCollapsed && (
                <div style={{ padding: '2px 10px 8px 38px' }}>
                  {pointBody(d.id)}
                </div>
              )}
            </div>
          )
        })}

        {filteredDocs.length === 0 && (
          <div style={{ padding: '20px 12px', textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
            无匹配章节
          </div>
        )}
      </div>
    </div>
  )
}
