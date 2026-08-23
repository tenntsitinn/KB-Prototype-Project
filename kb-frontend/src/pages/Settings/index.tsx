import { useState, useEffect } from 'react'
import { useAuthStore } from '../../stores/authStore'
import api from '../../services/api'

export default function Settings() {
  const { user, updateUser } = useAuthStore()
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [newPwd2, setNewPwd2] = useState('')
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState({ msg: '', type: '' })

  const [apiKeyInput, setApiKeyInput] = useState('')
  const [apiKeyInfo, setApiKeyInfo] = useState<{ has_key: boolean; masked_key: string; is_superuser: boolean } | null>(null)
  const [savingKey, setSavingKey] = useState(false)
  const [showKeyInput, setShowKeyInput] = useState(false)

  function showToast(msg: string, type: string) {
    setToast({ msg, type })
    setTimeout(() => setToast({ msg: '', type: '' }), 3000)
  }

  useEffect(() => {
    api.get('/api/auth/api-key').then(res => {
      setApiKeyInfo(res.data)
    }).catch(() => {})
  }, [])

  async function handleSaveApiKey() {
    if (!apiKeyInput.trim()) { showToast('请输入 API Key', 'error'); return }
    setSavingKey(true)
    try {
      const res = await api.put('/api/auth/api-key', { api_key: apiKeyInput.trim() })
      setApiKeyInfo(res.data)
      setApiKeyInput('')
      setShowKeyInput(false)
      showToast('API Key 保存成功', 'success')
    } catch (err: any) {
      showToast(err.response?.data?.detail || '保存失败', 'error')
    } finally {
      setSavingKey(false)
    }
  }

  async function handleClearApiKey() {
    setSavingKey(true)
    try {
      const res = await api.put('/api/auth/api-key', { api_key: '' })
      setApiKeyInfo(res.data)
      setApiKeyInput('')
      setShowKeyInput(false)
      showToast('API Key 已清除', 'success')
    } catch (err: any) {
      showToast(err.response?.data?.detail || '操作失败', 'error')
    } finally {
      setSavingKey(false)
    }
  }

  async function handleSave() {
    if (!displayName.trim()) { showToast('请输入显示名称', 'error'); return }

    if (oldPwd || newPwd || newPwd2) {
      if (!oldPwd) { showToast('请输入当前密码', 'error'); return }
      if (!newPwd) { showToast('请输入新密码', 'error'); return }
      if (newPwd.length < 6) { showToast('新密码至少 6 位', 'error'); return }
      if (newPwd !== newPwd2) { showToast('两次新密码不一致', 'error'); return }
    }

    setSaving(true)
    try {
      await api.put('/api/auth/profile', { display_name: displayName.trim(), email: email.trim() })

      if (oldPwd) {
        await api.post('/api/auth/change-password', {
          old_password: oldPwd, new_password: newPwd, confirm_password: newPwd2,
        })
      }

      updateUser({ display_name: displayName.trim(), email: email.trim() })
      setOldPwd(''); setNewPwd(''); setNewPwd2('')
      showToast('保存成功', 'success')
    } catch (err: any) {
      showToast(err.response?.data?.detail || '保存失败', 'error')
    } finally {
      setSaving(false)
    }
  }

  const sectionStyle: React.CSSProperties = {
    background: 'var(--bg)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)', marginBottom: 16,
  }
  const sectionHeader: React.CSSProperties = {
    padding: '16px 20px', borderBottom: '1px solid var(--border)',
    fontSize: 14, fontWeight: 600, color: 'var(--text)',
  }
  const sectionBody: React.CSSProperties = { padding: 20 }
  const labelStyle: React.CSSProperties = {
    display: 'block', fontSize: 13, fontWeight: 500,
    color: 'var(--text-secondary)', marginBottom: 6,
  }
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', fontSize: 14, fontFamily: 'var(--font)',
    color: 'var(--text)', outline: 'none',
  }
  const hintStyle: React.CSSProperties = { fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
      <div style={{ maxWidth: 560 }}>
        <div style={sectionStyle}>
          <div style={sectionHeader}>基本信息</div>
          <div style={sectionBody}>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>用户名</label>
              <input style={{ ...inputStyle, background: 'var(--bg-card)', color: 'var(--text-muted)' }} type="text" value={user?.username || ''} disabled />
              <div style={hintStyle}>用户名不可修改</div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>显示名称</label>
              <input style={inputStyle} type="text" value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="请输入显示名称" />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>邮箱</label>
              <input style={inputStyle} type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="请输入邮箱地址" />
            </div>
            <div style={{ marginBottom: 0 }}>
              <label style={labelStyle}>部门</label>
              <input style={{ ...inputStyle, background: 'var(--bg-card)', color: 'var(--text-muted)' }} type="text" value={user?.department_name || '未设置'} disabled />
              <div style={hintStyle}>部门由管理员分配，如需变更请联系管理员</div>
            </div>
          </div>
        </div>

        <div style={sectionStyle}>
          <div style={sectionHeader}>API Key 配置</div>
          <div style={sectionBody}>
            {apiKeyInfo?.is_superuser ? (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                超级管理员使用系统默认密钥，无需单独配置。
              </div>
            ) : (
              <>
                <div style={{ marginBottom: 12 }}>
                  <label style={labelStyle}>当前状态</label>
                  <div style={{ fontSize: 13, color: apiKeyInfo?.has_key ? 'var(--success, #52c41a)' : 'var(--text-muted)' }}>
                    {apiKeyInfo?.has_key ? `已配置（${apiKeyInfo.masked_key}）` : '未配置，将使用系统默认密钥'}
                  </div>
                </div>
                {showKeyInput ? (
                  <>
                    <div style={{ marginBottom: 12 }}>
                      <label style={labelStyle}>输入 API Key</label>
                      <input
                        style={inputStyle}
                        type="password"
                        value={apiKeyInput}
                        onChange={e => setApiKeyInput(e.target.value)}
                        placeholder="请输入您的 API Key"
                        autoFocus
                      />
                      <div style={hintStyle}>配置后，智能问答和智能出题将使用您自己的 Key 调用 LLM</div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-primary" onClick={handleSaveApiKey} disabled={savingKey}>
                        {savingKey ? '保存中...' : '保存'}
                      </button>
                      <button className="btn btn-outline" onClick={() => { setShowKeyInput(false); setApiKeyInput('') }}>取消</button>
                    </div>
                  </>
                ) : (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-outline" onClick={() => setShowKeyInput(true)}>
                      {apiKeyInfo?.has_key ? '更换 Key' : '设置 Key'}
                    </button>
                    {apiKeyInfo?.has_key && (
                      <button className="btn btn-outline" onClick={handleClearApiKey} disabled={savingKey} style={{ color: 'var(--danger, #ff4d4f)' }}>
                        清除
                      </button>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        <div style={sectionStyle}>
          <div style={sectionHeader}>修改密码</div>
          <div style={sectionBody}>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>当前密码</label>
              <input style={inputStyle} type="password" value={oldPwd} onChange={e => setOldPwd(e.target.value)} placeholder="请输入当前密码" />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>新密码</label>
              <input style={inputStyle} type="password" value={newPwd} onChange={e => setNewPwd(e.target.value)} placeholder="至少 6 位" />
            </div>
            <div style={{ marginBottom: 0 }}>
              <label style={labelStyle}>确认新密码</label>
              <input style={inputStyle} type="password" value={newPwd2} onChange={e => setNewPwd2(e.target.value)} placeholder="再次输入新密码" />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 8 }}>
          <button className="btn btn-outline" onClick={() => window.history.back()}>取消</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? '保存中...' : '保存修改'}
          </button>
        </div>
      </div>

      {toast.msg && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
