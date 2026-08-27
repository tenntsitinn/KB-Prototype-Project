import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import api from '../../services/api'

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState({ msg: '', type: '' })
  const [errors, setErrors] = useState({ username: '', password: '' })

  const [showRegister, setShowRegister] = useState(false)
  const [regForm, setRegForm] = useState({ username: '', password: '', password2: '', displayName: '', email: '' })

  function showToast(msg: string, type: string) {
    setToast({ msg, type })
    setTimeout(() => setToast({ msg: '', type: '' }), 3000)
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    const errs = { username: '', password: '' }
    if (!username.trim()) errs.username = '请输入用户名'
    if (!password) errs.password = '请输入密码'
    setErrors(errs)
    if (errs.username || errs.password) return

    setLoading(true)
    try {
      const res = await api.post('/api/auth/login', { username: username.trim(), password })
      const data = res.data
      login(data.access_token, data.refresh_token, data.user_info || data.user, data.permissions || [])
      if (remember) {
        localStorage.setItem('kb_token', JSON.stringify(data))
      }
      showToast('登录成功，正在跳转…', 'success')
      setTimeout(() => navigate('/qa', { replace: true }), 800)
    } catch (err: any) {
      showToast(err.response?.data?.detail || '用户名或密码错误', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister() {
    if (!regForm.username.trim()) { showToast('请输入用户名', 'error'); return }
    if (regForm.username.trim().length < 3) { showToast('用户名至少 3 个字符', 'error'); return }
    if (!regForm.password) { showToast('请输入密码', 'error'); return }
    if (regForm.password.length < 6) { showToast('密码至少 6 位', 'error'); return }
    if (regForm.password !== regForm.password2) { showToast('两次密码不一致', 'error'); return }

    try {
      await api.post('/api/auth/register', {
        username: regForm.username.trim(),
        password: regForm.password,
        display_name: regForm.displayName.trim() || regForm.username.trim(),
        email: regForm.email.trim() || undefined,
      })
      setShowRegister(false)
      showToast('注册成功，请登录', 'success')
      setUsername(regForm.username.trim())
      setPassword('')
      setRegForm({ username: '', password: '', password2: '', displayName: '', email: '' })
    } catch (err: any) {
      showToast(err.response?.data?.detail || '注册失败', 'error')
    }
  }

  const features = [
    { icon: 'M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z', text: '四维数据权限（全局 / 部门 / 角色 / 个人）混合授权' },
    { icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z', text: 'SSE 流式问答 · Markdown 渲染 · 引用溯源' },
    { icon: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z', text: 'FAQ 自动沉淀 · 知识缺口识别补全' },
  ]

  const stats = [
    { value: '—', label: '知识单元' },
    { value: '—', label: 'Total Tokens' },
    { value: '—', label: '独立访客 UV' },
    { value: '—', label: '平均响应' },
  ]

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100%' }}>
      {/* 左侧宣传区 */}
      <div style={{
        flex: '1 1 0',
        minWidth: 0,
        background: '#263238',
        color: '#fff',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '48px 56px 40px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* 装饰背景 */}
        <div style={{
          position: 'absolute', top: '-20%', right: '-10%', width: '60%', height: '60%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.04) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', bottom: '-15%', left: '-10%', width: '50%', height: '50%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* 顶部 Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, position: 'relative', zIndex: 1 }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
          <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: 1 }}>知识库管理平台</span>
        </div>

        {/* 中间宣传内容 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', gap: 28, position: 'relative', zIndex: 1, paddingTop: '15vh', paddingBottom: 24 }}>
          <div>
            <h1 style={{
              fontSize: 36, fontWeight: 700, lineHeight: 1.3, letterSpacing: 1,
              margin: '0 0 16px',
              background: 'linear-gradient(135deg, #fff 0%, rgba(255,255,255,0.75) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>
              让企业知识
              <br />
              安全地被 AI 使用
            </h1>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.55)', lineHeight: 1.6 }}>
              知识入库 · 授权访问 · 智能问答 · 数据沉淀，一站式企业知识闭环
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {features.map((f, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 22, height: 22, borderRadius: 6,
                  background: 'rgba(255,255,255,0.08)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d={f.icon} />
                  </svg>
                </div>
                <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.65)' }}>{f.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 底部统计 */}
        <div style={{
          display: 'flex', gap: 32, position: 'relative', zIndex: 1,
          paddingTop: 24, borderTop: '1px solid rgba(255,255,255,0.08)',
        }}>
          {stats.map((s, i) => (
            <div key={i}>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#fff', marginBottom: 2 }}>{s.value}</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 右侧登录区 */}
      <div style={{
        flex: '1 1 0',
        minWidth: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#F5F6F8',
        padding: 24,
      }}>
        <div style={{ width: '100%', maxWidth: 400 }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <img
              src="/logo.png"
              alt="Knowledge Base"
              style={{ height: 48, margin: '0 auto', display: 'block', transform: 'translateX(-6px)' }}
            />
            <h1 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text)', margin: '0 0 6px' }}>知识库管理平台</h1>
            <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>企业智能知识库，让知识触手可及</p>
          </div>

          <div style={{
            background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', padding: 32, boxShadow: 'var(--shadow-md)',
          }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 24 }}>账号登录</h2>
            <form onSubmit={handleLogin}>
              <div style={{ marginBottom: 20 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>用户名</label>
                <input
                  style={{
                    width: '100%', padding: '10px 12px', border: `1px solid ${errors.username ? 'var(--danger)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius)', fontSize: 14, fontFamily: 'var(--font)', outline: 'none',
                    boxShadow: errors.username ? '0 0 0 3px rgba(234,67,53,0.1)' : undefined,
                  }}
                  type="text" placeholder="请输入用户名" autoComplete="username" autoFocus
                  value={username} onChange={e => { setUsername(e.target.value); setErrors({ ...errors, username: '' }) }}
                  onDoubleClick={() => { setUsername('admin'); setPassword('admin123') }}
                />
                {errors.username && <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 4 }}>{errors.username}</div>}
              </div>

              <div style={{ marginBottom: 20 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>密码</label>
                <input
                  style={{
                    width: '100%', padding: '10px 12px', border: `1px solid ${errors.password ? 'var(--danger)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius)', fontSize: 14, fontFamily: 'var(--font)', outline: 'none',
                    boxShadow: errors.password ? '0 0 0 3px rgba(234,67,53,0.1)' : undefined,
                  }}
                  type="password" placeholder="请输入密码" autoComplete="current-password"
                  value={password} onChange={e => { setPassword(e.target.value); setErrors({ ...errors, password: '' }) }}
                />
                {errors.password && <div style={{ fontSize: 12, color: 'var(--danger)', marginTop: 4 }}>{errors.password}</div>}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} style={{ width: 16, height: 16, accentColor: 'var(--primary)' }} />
                  记住登录
                </label>
                <a href="javascript:void(0)" style={{ fontSize: 13, color: 'var(--primary)', textDecoration: 'none' }}>忘记密码？</a>
              </div>

              <button
                type="submit" disabled={loading}
                className="btn btn-primary"
                style={{ width: '100%', padding: '10px 20px', fontSize: 14, justifyContent: 'center' }}
              >
                {loading ? '登录中...' : '登 录'}
              </button>

              <div style={{ textAlign: 'center', marginTop: 16, fontSize: 13, color: 'var(--text-muted)' }}>
                还没有账号？<a href="javascript:void(0)" onClick={() => { setRegForm({ username: '', password: '', password2: '', displayName: '', email: '' }); setShowRegister(true) }} style={{ color: 'var(--primary)', fontWeight: 500, textDecoration: 'none' }}>立即注册</a>
              </div>
            </form>
          </div>

          <div style={{ textAlign: 'center', marginTop: 24, fontSize: 12, color: 'var(--text-muted)' }}>
            powered by <a href="javascript:void(0)" style={{ color: 'var(--primary)', textDecoration: 'none' }}>KB Team</a>
          </div>
        </div>
      </div>

      {/* Register Modal */}
      {showRegister && (
        <div onClick={() => setShowRegister(false)} style={{
          position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: 'var(--bg)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-lg)',
            width: '90%', maxWidth: 440, animation: 'fadeIn 0.15s',
          }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: 15, fontWeight: 600 }}>注册账号</h3>
              <button onClick={() => setShowRegister(false)} style={{
                width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                borderRadius: 6, cursor: 'pointer', border: 'none', background: 'transparent',
                fontSize: 18, color: 'var(--text-muted)',
              }}>&times;</button>
            </div>
            <div style={{ padding: 20 }}>
              {[
                { label: '用户名 *', key: 'username', type: 'text', placeholder: '登录用户名' },
                { label: '密码 *', key: 'password', type: 'password', placeholder: '至少 6 位' },
                { label: '确认密码 *', key: 'password2', type: 'password', placeholder: '再次输入密码' },
                { label: '显示名', key: 'displayName', type: 'text', placeholder: '用户显示名称' },
                { label: '邮箱', key: 'email', type: 'email', placeholder: 'user@example.com' },
              ].map(f => (
                <div key={f.key} style={{ marginBottom: 14 }}>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>{f.label}</label>
                  <input
                    type={f.type} placeholder={f.placeholder}
                    value={(regForm as any)[f.key]}
                    onChange={e => setRegForm({ ...regForm, [f.key]: e.target.value })}
                    style={{
                      width: '100%', padding: '8px 12px', border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)', fontSize: 14, fontFamily: 'var(--font)', outline: 'none',
                    }}
                  />
                </div>
              ))}
            </div>
            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn btn-ghost" onClick={() => setShowRegister(false)}>取消</button>
              <button className="btn btn-primary" onClick={handleRegister}>注 册</button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast.msg && (
        <div className={`toast ${toast.type}`}>{toast.msg}</div>
      )}
    </div>
  )
}
