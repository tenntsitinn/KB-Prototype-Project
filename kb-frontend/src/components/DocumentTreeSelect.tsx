import { useState, useMemo, useCallback } from 'react'

export interface TreeDocument {
  id: string
  title: string
  category: string
}

interface DocumentTreeSelectProps {
  documents: TreeDocument[]
  selectedIds: Set<string>
  onChange: (ids: Set<string>) => void
}

interface TagGroup {
  tag: string
  docs: TreeDocument[]
}

const TAG_LABELS: Record<string, string> = {
  '': '未分类',
}

function tagLabel(tag: string): string {
  return TAG_LABELS[tag] || tag
}

export default function DocumentTreeSelect({
  documents, selectedIds, onChange,
}: DocumentTreeSelectProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [query, setQuery] = useState('')

  const groups = useMemo<TagGroup[]>(() => {
    const map = new Map<string, TreeDocument[]>()
    for (const doc of documents) {
      const tag = doc.category || ''
      if (!map.has(tag)) map.set(tag, [])
      map.get(tag)!.push(doc)
    }
    return Array.from(map.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([tag, docs]) => ({ tag, docs: docs.sort((a, b) => a.title.localeCompare(b.title)) }))
  }, [documents])

  const filteredGroups = useMemo<TagGroup[]>(() => {
    const q = query.trim().toLowerCase()
    if (!q) return groups
    return groups
      .map(g => ({
        ...g,
        docs: g.docs.filter(d => d.title.toLowerCase().includes(q)),
      }))
      .filter(g => g.docs.length > 0)
  }, [groups, query])

  const toggleCollapse = useCallback((tag: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(tag)) next.delete(tag)
      else next.add(tag)
      return next
    })
  }, [])

  const toggleTag = useCallback((tag: string, docs: TreeDocument[]) => {
    const allSelected = docs.every(d => selectedIds.has(d.id))
    const next = new Set(selectedIds)
    if (allSelected) {
      for (const d of docs) next.delete(d.id)
    } else {
      for (const d of docs) next.add(d.id)
    }
    onChange(next)
  }, [selectedIds, onChange])

  const toggleDoc = useCallback((id: string) => {
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(next)
  }, [selectedIds, onChange])

  const selectAll = useCallback(() => {
    onChange(new Set(documents.map(d => d.id)))
  }, [documents, onChange])

  const clearAll = useCallback(() => {
    onChange(new Set())
  }, [onChange])

  const allSelected = selectedIds.size === documents.length && documents.length > 0

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
          placeholder="搜索文档…"
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
          {selectedIds.size > 0 ? `已选 ${selectedIds.size} 篇` : '全选'}
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

      {/* 树形列表 */}
      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {filteredGroups.map(g => {
          const selectedCount = g.docs.filter(d => selectedIds.has(d.id)).length
          const allChecked = selectedCount === g.docs.length
          const indeterminate = selectedCount > 0 && !allChecked
          const isCollapsed = collapsed.has(g.tag) && !query

          return (
            <div key={g.tag}>
              {/* Tag 行 */}
              <div
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px',
                  cursor: 'pointer', background: 'var(--bg-hover, #f7f8fa)',
                  borderBottom: isCollapsed ? '1px solid var(--border-light)' : 'none',
                }}
                onClick={() => { if (!query) toggleCollapse(g.tag) }}
              >
                {!query && (
                  <svg
                    width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"
                    style={{ flexShrink: 0, transition: 'transform 0.15s', transform: isCollapsed ? 'rotate(-90deg)' : 'none' }}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                )}
                <div style={checkboxStyle(allChecked, indeterminate)} onClick={(e) => { e.stopPropagation(); toggleTag(g.tag, g.docs) }}>
                  {allChecked ? checkMark() : indeterminate ? indeterminateMark() : null}
                </div>
                <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>
                  {tagLabel(g.tag)}
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  ({selectedCount}/{g.docs.length})
                </span>
              </div>

              {/* 文档列表 */}
              {!isCollapsed && g.docs.map(d => {
                const checked = selectedIds.has(d.id)
                return (
                  <div
                    key={d.id}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '6px 10px 6px 32px', cursor: 'pointer',
                      borderBottom: '1px solid var(--border-light)',
                    }}
                    onClick={() => toggleDoc(d.id)}
                  >
                    <div style={checkboxStyle(checked, false)}>
                      {checked ? checkMark() : null}
                    </div>
                    <span style={{
                      fontSize: 13, color: 'var(--text)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {d.title}
                    </span>
                  </div>
                )
              })}
            </div>
          )
        })}

        {filteredGroups.length === 0 && (
          <div style={{ padding: '20px 12px', textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
            无匹配文档
          </div>
        )}
      </div>
    </div>
  )
}
