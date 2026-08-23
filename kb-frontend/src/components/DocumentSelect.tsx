import { useEffect, useRef, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'

export interface DocumentSelectItem {
  id: string
  title: string
  category: string
}

interface DocumentSelectProps {
  documents: DocumentSelectItem[]
  value: string
  onChange: (value: string) => void
  emptyLabel?: string
  placeholder?: string
  width?: number | string
}

export default function DocumentSelect({
  documents, value, onChange, emptyLabel, placeholder, width,
}: DocumentSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({})
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const calcPosition = useCallback(() => {
    if (!rootRef.current) return
    const rect = rootRef.current.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    const openUpward = spaceBelow < 300 && rect.top > spaceBelow
    setDropdownStyle({
      position: 'fixed',
      top: openUpward ? undefined : rect.bottom + 4,
      bottom: openUpward ? window.innerHeight - rect.top + 4 : undefined,
      left: rect.left,
      width: rect.width,
      zIndex: 9999,
    })
  }, [])

  useEffect(() => {
    if (!open) return
    calcPosition()
    const onDocDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        const dropdown = document.getElementById('doc-select-dropdown')
        if (!dropdown || !dropdown.contains(e.target as Node)) setOpen(false)
      }
    }
    const onScroll = () => setOpen(false)
    const onResize = () => calcPosition()
    document.addEventListener('mousedown', onDocDown)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onResize)
    return () => {
      document.removeEventListener('mousedown', onDocDown)
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onResize)
    }
  }, [open, calcPosition])

  const close = () => {
    setOpen(false)
    setQuery('')
  }

  const openList = () => {
    setOpen(true)
    setQuery('')
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  const pick = (v: string) => {
    onChange(v)
    close()
  }

  const selectedDoc = documents.find((d) => d.id === value)
  const q = query.trim().toLowerCase()
  const filtered = q ? documents.filter((d) => d.title.toLowerCase().includes(q)) : documents

  const itemStyle = (active: boolean): React.CSSProperties => ({
    padding: '8px 12px', fontSize: 13, cursor: 'pointer',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
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
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
        <input
          ref={inputRef}
          value={open ? query : (selectedDoc?.title || '')}
          readOnly={!open}
          placeholder={open ? '搜索文档…' : (placeholder || selectedDoc?.title || (emptyLabel ?? ''))}
          onChange={(e) => { setQuery(e.target.value) }}
          onFocus={openList}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              if (filtered.length > 0) pick(filtered[0].id)
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

      {open && createPortal(
        <div
          id="doc-select-dropdown"
          style={{
            ...dropdownStyle,
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
            boxShadow: '0 8px 24px rgba(0,0,0,0.12)', maxHeight: 300, overflowY: 'auto',
          }}
        >
          {emptyLabel !== undefined && (
            <div style={itemStyle(false)} onClick={() => pick('')}>{emptyLabel}</div>
          )}
          {filtered.map((d) => (
            <div key={d.id} style={itemStyle(d.id === value)} onClick={() => pick(d.id)} title={d.title}>
              {d.id === value ? '✓ ' : ''}{d.title}
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: '10px 12px', fontSize: 12, color: 'var(--text-muted)' }}>
              无匹配文档
            </div>
          )}
        </div>,
        document.body,
      )}
    </div>
  )
}
