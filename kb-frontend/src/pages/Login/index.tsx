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

  // Register modal
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

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: '#F5F6F8', padding: 24,
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