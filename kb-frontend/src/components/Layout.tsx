import { useState, useRef, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore, getRoleLabel } from '../stores/authStore'

const navItems = [
  {
    section: '核心功能',
    items: [
      { to: '/qa', label: '智能问答', icon: 'qa', perm: 'ai:access' },
      { to: '/quiz', label: '智能出题', icon: 'quiz', perm: null },
      { to: '/knowledge', label: '知识管理', icon: 'knowledge', perm: 'knowledge:read' },
    ],
  },
  {
    section: '知识沉淀',
    items: [
      { to: '/faq', label: 'FAQ 管理', icon: 'faq', perm: 'faq:manage' },
      { to: '/quiz-bank', label: '题库审核', icon: 'quizbank', perm: 'quiz:manage' },
      { to: '/quiz-browse', label: '题库浏览', icon: 'browse', perm: 'quiz:manage' },
      { to: '/gaps', label: '缺口分析', icon: 'gaps', perm: 'gap:manage' },
    ],
  },
  {
    section: '数据与系统',
    items: [
      { to: '/dashboard', label: '数据看板', icon: 'dashboard', perm: 'dashboard:view' },
      { to: '/admin', label: '系统管理', icon: 'admin', perm: 'permission:manage' },
    ],
  },
]

function NavIcon({ name }: { name: string }) {
  switch (name) {
    case 'qa':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" /><path d="M8 12l3 3 5-5" />
        </svg>
      )
    case 'quiz':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
        </svg>
      )
    case 'quizbank':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      )
    case 'browse':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      )
    case 'knowledge':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
        </svg>
      )
    case 'faq':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      )
    case 'gaps':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" /><path d="M8 12h8" />
        </svg>
      )
    case 'dashboard':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="3" y1="15" x2="21" y2="15" /><line x1="9" y1="3" x2="9" y2="21" />
        </svg>
      )
    case 'admin':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
        </svg>
      )
    default:
      return null
  }
}

export default function Layout({ children, title }: { children: React.ReactNode; title: string }) {
  const { user, logout, hasPermission } = useAuthStore()
  const navigate = useNavigate()
  const [popupVisible, setPopupVisible] = useState(false)
  const userCardRef = useRef<HTMLDivElement>(null)
  const popupRef = useRef<HTMLDivElement>(null)

  const displayName = user?.display_name || user?.username || ''
  const roleLabel = getRoleLabel(user)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (popupRef.current && !popupRef.current.contains(e.target as Node) &&
          userCardRef.current && !userCardRef.current.contains(e.target as Node)) {
        setPopupVisible(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function handleLogout() {
    setPopupVisible(false)
    logout()
    navigate('/login', { replace: true })
  }

  const visibleSections = navItems.map((s) => ({
    ...s,
    items: s.items.filter((item) => !item.perm || hasPermission(item.perm)),
  })).filter((s) => s.items.length > 0)

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      {/* Sidebar */}
      <aside style={{
        width: 'var(--sidebar-width)', background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border)', display: 'flex',
        flexDirection: 'column', flexShrink: 0,
      }}>
        <div style={{
          height: 'var(--header-height)', display: 'flex', alignItems: 'center',
          padding: '0 20px', fontSize: 16, fontWeight: 600, color: 'var(--primary)',
          borderBottom: '1px solid var(--border)', gap: 10,
        }}>
          知识库平台
        </div>
        <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {visibleSections.map((section, si) => (
            <div key={si}>
              <div style={{
                fontSize: 11, fontWeight: 600, color: 'var(--text-muted)',
                padding: '8px 12px 4px', textTransform: 'uppercase', letterSpacing: 0.5,
              }}>
                {section.section}
              </div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  style={({ isActive }) => ({
                    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                    borderRadius: 'var(--radius)', color: isActive ? 'var(--primary)' : 'var(--text-secondary)',
                    background: isActive ? 'var(--primary-light)' : 'transparent',
                    fontWeight: isActive ? 500 : 400, textDecoration: 'none',
                    fontSize: 14, transition: 'all 0.15s',
                  })}
                >
                  <span style={{ width: 20, height: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <NavIcon name={item.icon} />
                  </span>
                  {item.label}
                </NavLink>
              ))}
              {si < visibleSections.length - 1 && (
                <div style={{ height: 1, background: 'var(--border)', margin: '8px 12px' }} />
              )}
            </div>
          ))}
        </nav>
        <div style={{ padding: 12, borderTop: '1px solid var(--border)' }}>
          <div
            ref={userCardRef}
            onClick={() => setPopupVisible(!popupVisible)}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: 8,
              borderRadius: 'var(--radius)', cursor: 'pointer',
            }}
          >
            <div style={{
              width: 32, height: 32, borderRadius: '50%', background: 'var(--primary)',
              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 600, flexShrink: 0,
            }}>
              {displayName.charAt(0) || 'U'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{displayName}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{roleLabel}</div>
            </div>
          </div>
        </div>
      </aside>

      {/* User Popup */}
      {popupVisible && (
        <>
          <div onClick={() => setPopupVisible(false)} style={{ position: 'fixed', inset: 0, zIndex: 999 }} />
          <div
            ref={popupRef}
            style={{
              position: 'fixed', zIndex: 1000, background: 'var(--bg)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-lg)', width: 280, left: 12, bottom: 68,
              animation: 'fadeIn 0.15s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 16, borderBottom: '1px solid var(--border)' }}>
              <div style={{
                width: 44, height: 44, borderRadius: '50%', background: 'var(--primary)',
                color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 17, fontWeight: 600, flexShrink: 0,
              }}>
                {displayName.charAt(0) || 'U'}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>{displayName}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{roleLabel}</div>
              </div>
            </div>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-light)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)', minWidth: 48 }}>用户名</span>
                <span style={{ color: 'var(--text)' }}>{user?.username || '--'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)', minWidth: 48 }}>邮箱</span>
                <span style={{ color: 'var(--text)' }}>{user?.email || '未设置'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13 }}>
                <span style={{ color: 'var(--text-muted)', minWidth: 48 }}>部门</span>
                <span style={{ color: 'var(--text)' }}>{user?.department_name || '未设置'}</span>
              </div>
            </div>
            <div style={{ padding: 8 }}>
              <button
                className="btn btn-outline"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => { setPopupVisible(false); navigate('/settings') }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
                </svg>
                账号设置
              </button>
              <button
                className="btn btn-outline"
                style={{ width: '100%', justifyContent: 'center', color: 'var(--danger)', borderColor: 'transparent' }}
                onClick={handleLogout}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                退出登录
              </button>
            </div>
          </div>
        </>
      )}

      {/* Main */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={{
          height: 'var(--header-height)', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 24px', flexShrink: 0,
        }}>
          <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text)' }}>{title}</span>
        </header>
        <div style={{ flex: 1, overflow: 'hidden' }}>{children}</div>
      </main>
    </div>
  )
}

