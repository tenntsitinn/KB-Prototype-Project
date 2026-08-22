import { useEffect, useRef, useState } from 'react'

export interface TagSelectTag {
  id: string
  name: string
}

interface TagSelectProps {
  tags: TagSelectTag[]
  value: string
  onChange: (value: string) => void
  /** 空值选项文案，如「全部分类」；不传则不允许空值 */
  emptyLabel?: string
  /** 允许输入新标签值（如上传/编辑场景） */
  allowCustom?: boolean
  /** 自定义输入的最大长度 */
  maxLength?: number
  placeholder?: string
  width?: number | string
}

/**
 * 可搜索的标签选择器：标签多时可输入关键字过滤，
 * 支持新建自定义标签值（allowCustom）。
 */
export default function TagSelect({
  tags, value, onChange, emptyLabel, allowCustom, maxLength, placeholder, width,
}: TagSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocDown)
    return () => document.removeEventListener('mousedown', onDocDown)
  }, [open])

  const close = () => {
    setOpen(false)
    setQuery('')
  }

  const openList = () => {
    setOpen(true)
    setQuery(value)
    requestAnimationFrame(() => inputRef.current?.select())
  }

  const pick = (v: string) => {
    onChange(v)
    close()
  }

  const q = query.trim().toLowerCase()
  const filtered = q ? tags.filter((t) => t.name.toLowerCase().includes(q)) : tags
  const exactMatch = tags.some((t) => t.name === query.trim())
  const canCreate = !!allowCustom && q.length > 0 && !exactMatch

  const itemStyle = (active: boolean): React.CSSProperties => ({
    padding: '8px 12px', fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap',
    overflow: 'hidden', textOverflow: 'ellipsis',
    background: active ? 'var(--primary-light)' : 'transparent',
    color: active ? 'var(--primary)' : 'var(--text)',
  })

  return (
    <div ref={rootRef} style={{ position: 'relative', width: width ?? '100%' }}>
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          border: `1px solid ${open ? 'var(--primary)' : 'var(--border)'}`,
          borderRadius: 8, background: 'var(--bg)', cursor: 'text',
          boxShadow: open ? '0 0 0 3px var(--primary-light)' : 'none',
        }}
        onClick={() => { if (!open) openList() }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" style={{ marginLeft: 10, flexShrink: 0 }}>
          <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          ref={inputRef}
          value={open ? query : value}
          maxLength={maxLength}
          placeholder={open ? (allowCustom ? '搜索或输入新分类…' : '搜索分类…') : (placeholder || value || (emptyLabel ?? ''))}
          onChange={(e) => { setQuery(e.target.value); if (!open) setOpen(true) }}
          onFocus={openList}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              if (canCreate) pick(query.trim())
              else if (filtered.length > 0) pick(filtered[0].name)
              else if (emptyLabel !== undefined && !q) pick('')
            } else if (e.key === 'Escape') {
              close()
            }
          }}
          style={{
            flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent',
            fontFamily: 'var(--font)', fontSize: 13, color: 'var(--text)',
            padding: '8px 10px 8px 0',
          }}
        />
        {value && !open && (
          <span
            onClick={(e) => { e.stopPropagation(); onChange('') }}
            title="清除"
            style={{ marginRight: 8, cursor: 'pointer', color: 'var(--text-muted)', fontSize: 14, lineHeight: 1, flexShrink: 0 }}
          >×</span>
        )}
        {!value && !open && emptyLabel && (
          <span style={{ marginRight: 10, fontSize: 12, color: 'var(--text-muted)', flexShrink: 0 }}>{emptyLabel}</span>
        )}
      </div>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 1000,
          background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
          boxShadow: '0 8px 24px rgba(0,0,0,0.12)', maxHeight: 260, overflowY: 'auto',
        }}>
          {emptyLabel !== undefined && (
            <div style={itemStyle(false)} onClick={() => pick('')}>{emptyLabel}</div>
          )}
          {filtered.map((t) => (
            <div key={t.id} style={itemStyle(t.name === value)} onClick={() => pick(t.name)}>
              {t.name === value ? '✓ ' : ''}{t.name}
            </div>
          ))}
          {canCreate && (
            <div
              style={{ ...itemStyle(false), color: 'var(--primary)', fontWeight: 500 }}
              onClick={() => pick(query.trim())}
            >
              ＋ 使用「{query.trim()}」
            </div>
          )}
          {filtered.length === 0 && !canCreate && (
            <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-muted)' }}>
              无匹配标签
            </div>
          )}
        </div>
      )}
    </div>
  )
}
