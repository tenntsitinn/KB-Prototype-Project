import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { useAuthStore } from '../../stores/authStore'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
  sources?: { title: string; score: number; text: string }[]
  faqHit?: boolean
  streaming?: boolean
}

const fallbackSuggestions = [
  '支持导入哪些文件格式？',
  '如何给部门配置知识库权限？',
  'FAQ 自动挖掘是怎么工作的？',
  '上传的文档解析失败怎么办？',
]

export default function SearchQA() {
  const { user } = useAuthStore()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const chatRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight)
  }, [messages])

  // 热门问题：近 100 条问答中频次最高的 3 个；无记录时用默认示例
  useEffect(() => {
    const token = sessionStorage.getItem('kb_token')
    const auth = token ? JSON.parse(token).access_token : ''
    fetch('/api/ai/hot-questions', { headers: { Authorization: `Bearer ${auth}` } })
      .then((res) => (res.ok ? res.json() : { questions: [] }))
      .then((data) => {
        const qs: string[] = Array.isArray(data?.questions) ? data.questions : []
        setSuggestions(qs.length > 0 ? qs.slice(0, 3) : fallbackSuggestions)
      })
      .catch(() => setSuggestions(fallbackSuggestions))
  }, [])

  function addMessage(msg: Message) {
    setMessages(prev => [...prev, msg])
  }

  function updateLastMessage(updater: (msg: Message) => Message) {
    setMessages(prev => {
      const copy = [...prev]
      copy[copy.length - 1] = updater(copy[copy.length - 1])
      return copy
    })
  }

  function formatTime() {
    const now = new Date()
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return

    const time = formatTime()
    addMessage({ id: Date.now().toString(), role: 'user', content: text, time })
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    const aiId = (Date.now() + 1).toString()
    addMessage({ id: aiId, role: 'assistant', content: '', time: '', streaming: true })
    setLoading(true)

    try {
      const res = await fetch('/api/ai/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionStorage.getItem('kb_token') ? JSON.parse(sessionStorage.getItem('kb_token')!).access_token : ''}`,
        },
        body: JSON.stringify({ question: text, stream: true }),
      })

      if (!res.ok) throw new Error('请求失败')

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\n')
          let currentEvent = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              const data = line.slice(6)
              if (data === '[DONE]') continue
              try {
                const json = JSON.parse(data)
                if (currentEvent === 'delta' && json.content) {
                  fullContent += json.content
                  updateLastMessage(msg => ({ ...msg, content: fullContent, streaming: true }))
                }
                if (currentEvent === 'sources') {
                  updateLastMessage(msg => ({ ...msg, sources: Array.isArray(json) ? json : [] }))
                }
              } catch { /* ignore parse errors */ }
            }
          }
        }
      }

      updateLastMessage(msg => ({ ...msg, content: fullContent || '未获取到回答', streaming: false, time: formatTime() }))
    } catch {
      updateLastMessage(msg => ({ ...msg, content: '请求失败，请稍后重试', streaming: false, time: formatTime() }))
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  const displayName = user?.display_name || user?.username || 'U'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div ref={chatRef} style={{
        flex: 1, overflow: 'auto', padding: 24,
        display: 'flex', flexDirection: 'column', gap: 24,
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 24px', maxWidth: 560, margin: '0 auto' }}>
            <img
              src="/logo-sidebar.png" alt="KB"
              style={{ height: 80, width: 'auto', marginBottom: 16 }}
            />
            <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>你好，有什么可以帮助你的？</h2>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 20 }}>
              基于企业知识库的智能问答助手，支持流式对话、多轮上下文理解、自动来源追溯。
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              {suggestions.map(s => (
                <span
                  key={s}
                  onClick={() => { setInput(s); setTimeout(() => sendMessage(), 100) }}
                  style={{
                    padding: '8px 16px', background: 'var(--bg-card)', border: '1px solid var(--border)',
                    borderRadius: 20, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer',
                  }}
                >{s}</span>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} style={{
            display: 'flex', gap: 12, maxWidth: 780, margin: '0 auto', width: '100%',
            flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%', display: 'flex',
              alignItems: 'center', justifyContent: 'center', fontSize: 13,
              fontWeight: 600, color: '#fff', flexShrink: 0,
              background: msg.role === 'user' ? 'var(--primary)' : '#5F6368',
            }}>
              {msg.role === 'user' ? displayName.charAt(0) : 'AI'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              {msg.faqHit && (
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px',
                  background: 'rgba(52,168,83,0.1)', color: 'var(--success)',
                  borderRadius: 10, fontSize: 11, fontWeight: 500, marginBottom: 8,
                }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12" /></svg>
                  FAQ 缓存命中
                </div>
              )}
              <div style={{
                padding: '12px 16px', borderRadius: 'var(--radius-lg)', fontSize: 14, lineHeight: 1.7,
                background: msg.role === 'user' ? 'var(--primary)' : 'var(--bg-card)',
                color: msg.role === 'user' ? '#fff' : 'var(--text)',
                borderBottomRightRadius: msg.role === 'user' ? 4 : undefined,
                borderBottomLeftRadius: msg.role === 'assistant' ? 4 : undefined,
                whiteSpace: msg.role === 'user' ? 'pre-wrap' : 'normal',
              }}>
                {msg.role === 'assistant' ? (
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {msg.content}
                  </ReactMarkdown>
                ) : (
                  msg.content
                )}
                {msg.streaming && (
                  <span style={{
                    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                    background: 'var(--primary)', animation: 'pulse 1.2s infinite', marginLeft: 2,
                  }} />
                )}
              </div>
              {msg.sources && msg.sources.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    参考来源
                  </div>
                  {msg.sources.map((s, i) => (
                    <div key={i} style={{
                      background: 'var(--bg)', border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)', padding: 12, marginBottom: 8, cursor: 'pointer',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{s.title}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-card)', padding: '2px 8px', borderRadius: 10 }}>匹配度 {(s.score * 100).toFixed(1)}%</span>
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{s.text}</div>
                    </div>
                  ))}
                </div>
              )}
              {msg.time && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, padding: '0 4px', textAlign: msg.role === 'user' ? 'right' : 'left' }}>{msg.time}</div>}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div style={{ padding: '16px 24px 20px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{
          maxWidth: 780, margin: '0 auto', display: 'flex', alignItems: 'flex-end', gap: 10,
          background: 'var(--bg-input)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '10px 14px',
        }}>
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder="输入你的问题，按 Enter 发送…"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            style={{
              flex: 1, border: 'none', outline: 'none', background: 'transparent',
              fontFamily: 'var(--font)', fontSize: 14, color: 'var(--text)',
              resize: 'none', minHeight: 24, maxHeight: 120, lineHeight: 1.5,
            }}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            style={{
              width: 36, height: 36, borderRadius: '50%', background: 'var(--primary)',
              border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
              justifyContent: 'center', flexShrink: 0, opacity: loading || !input.trim() ? 0.5 : 1,
            }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" width="18" height="18">
              <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', marginTop: 8 }}>
          支持流式响应 · FAQ 缓存优先匹配 · 多路召回 + Rerank 排序
        </div>
      </div>
    </div>
  )
}