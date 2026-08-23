// ===== Types =====
export interface Tag {
  id: string
  name: string
  sort_order: number
}
export interface Permission {
  id: string
  target_type: 'global' | 'department' | 'role' | 'user'
  target_id: string
  target_name: string
}

export interface KnowledgeUnit {
  id: string
  unit_code: string
  title: string
  content: string
  summary: string
  category: string
  source_file_name: string
  file_type: string
  file_size: number
  status: 'published' | 'draft' | 'deleted'
  creator_id: string
  created_at: string
  updated_at: string
  deleted_at?: string
  permissions: Permission[]
}

export interface Department {
  id: string
  name: string
}

export interface Role {
  role_code: string
  role_name: string
}

export interface ImportTask {
  id: string
  fileName: string
  fileSize: number
  progress: number
  status: 'processing' | 'completed' | 'failed'
}

// ===== Constants =====
export const PAGE_SIZE = 5

export const STATUS_MAP: Record<string, string> = { published: '已发布', draft: '草稿', deleted: '已删除' }
export const PERM_TYPE_MAP: Record<string, string> = { global: '全局可见', department: '指定部门', role: '指定角色', user: '指定用户' }

// ===== Helpers =====
export function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

export function formatDate(iso?: string): string {
  if (!iso) return '--'
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

export function getPermissionTargetName(p: Permission, departments: Department[], roles: Role[]): string {
  if (p.target_type === 'global') return '所有人'
  if (p.target_type === 'department') {
    const dept = departments.find((d) => d.id === p.target_id)
    return dept ? dept.name : p.target_name || p.target_id || '--'
  }
  if (p.target_type === 'role') {
    const role = roles.find((r) => r.role_code === p.target_id)
    return role ? role.role_name : p.target_name || p.target_id || '--'
  }
  return p.target_name || p.target_id || '--'
}
