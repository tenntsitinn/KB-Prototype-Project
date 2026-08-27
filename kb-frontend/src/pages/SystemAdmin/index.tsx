import { useState } from 'react'
import { DeptManagement, RoleManagement, TagManagement, UserManagement } from './components/AdminSections'

export default function SystemAdmin() {
  const [activeTab, setActiveTab] = useState('users')
  const [toast, setToast] = useState({ msg: '', type: '' })

  function showToast(msg: string, type: string) {
    setToast({ msg, type })
    setTimeout(() => setToast({ msg: '', type: '' }), 3000)
  }

  const tabs = [
    { key: 'users', label: '用户管理' },
    { key: 'roles', label: '角色管理' },
    { key: 'departments', label: '部门管理' },
    { key: 'tags', label: '标签管理' },
  ]

  const tabBarStyle: React.CSSProperties = {
    display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 20,
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 24, minHeight: 0 }}>
      <div style={tabBarStyle}>
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            style={{
              padding: '10px 20px', fontSize: 14, fontWeight: activeTab === t.key ? 600 : 400,
              color: activeTab === t.key ? 'var(--primary)' : 'var(--text-secondary)',
              borderBottom: activeTab === t.key ? '2px solid var(--primary)' : '2px solid transparent',
              background: 'transparent', borderTop: 'none', borderLeft: 'none', borderRight: 'none',
              cursor: 'pointer', fontFamily: 'var(--font)',
            }}
          >{t.label}</button>
        ))}
      </div>

      {activeTab === 'users' && <UserManagement showToast={showToast} />}
      {activeTab === 'roles' && <RoleManagement showToast={showToast} />}
      {activeTab === 'departments' && <DeptManagement showToast={showToast} />}
      {activeTab === 'tags' && <TagManagement showToast={showToast} />}

      {toast.msg && <div className={`toast ${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
