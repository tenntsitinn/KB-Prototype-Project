import { create } from 'zustand'

export interface UserInfo {
  id: string
  username: string
  display_name: string
  email: string
  department_name: string
  is_superuser: boolean
  roles: string[]
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: UserInfo | null
  permissions: string[]
  isAuthenticated: boolean

  login: (token: string, refreshToken: string, user: UserInfo, permissions?: string[]) => void
  logout: () => void
  updateUser: (user: Partial<UserInfo>) => void
  restoreSession: () => boolean
  hasPermission: (code: string) => boolean
}

function getRoleLabel(user: UserInfo | null): string {
  if (!user) return '学员'
  if (user.is_superuser) return '超级管理员'
  const roles = user.roles || []
  if (roles.includes('super_admin')) return '超级管理员'
  if (roles.includes('system_admin')) return '系统管理员'
  if (roles.includes('teacher')) return '教师'
  if (roles.includes('knowledge_admin')) return '知识管理员'
  if (roles.includes('student')) return '学员'
  return '学员'
}

function getRoleLabelStatic(roles: string[]): string {
  if (!roles) return '学员'
  if (roles.includes('super_admin')) return '超级管理员'
  if (roles.includes('system_admin')) return '系统管理员'
  if (roles.includes('teacher')) return '教师'
  if (roles.includes('knowledge_admin')) return '知识管理员'
  if (roles.includes('student')) return '学员'
  return '学员'
}

export { getRoleLabel, getRoleLabelStatic }

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  refreshToken: null,
  user: null,
  permissions: [],
  isAuthenticated: false,

  login: (token, refreshToken, user, permissions = []) => {
    const data = { access_token: token, refresh_token: refreshToken, token_type: 'bearer', user, permissions }
    const raw = JSON.stringify(data)
    sessionStorage.setItem('kb_token', raw)
    set({ token, refreshToken, user, permissions, isAuthenticated: true })
  },

  logout: () => {
    sessionStorage.removeItem('kb_token')
    localStorage.removeItem('kb_token')
    set({ token: null, refreshToken: null, user: null, permissions: [], isAuthenticated: false })
  },

  updateUser: (partial) => {
    const current = get().user
    if (!current) return
    const updated = { ...current, ...partial }
    set({ user: updated })

    const raw = sessionStorage.getItem('kb_token')
    if (raw) {
      try {
        const data = JSON.parse(raw)
        if (data.user) Object.assign(data.user, partial)
        else Object.assign(data, partial)
        sessionStorage.setItem('kb_token', JSON.stringify(data))
      } catch { /* ignore */ }
    }
  },

  restoreSession: () => {
    const raw = sessionStorage.getItem('kb_token') || localStorage.getItem('kb_token')
    if (!raw) return false
    try {
      const data = JSON.parse(raw)
      const user = data.user || data
      set({
        token: data.access_token || '',
        refreshToken: data.refresh_token || '',
        user,
        permissions: data.permissions || [],
        isAuthenticated: true,
      })
      return true
    } catch {
      return false
    }
  },

  hasPermission: (code: string) => {
    const { permissions, user } = get()
    if (user?.is_superuser) return true
    return permissions.includes('*') || permissions.includes(code)
  },
}))