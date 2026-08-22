import { useEffect, useState } from 'react'
import api from '../../../services/api'

interface UserItem {
  id: string
  username: string
  display_name: string
  email: string
  department_id: string
  roles: string[]
  status: string
  is_superuser: boolean
}

interface RoleItem {
  id: string
  role_name: string
  role_code: string
  description: string
  permissions: string[]
}

interface DeptItem {
  id: string
  name: string
  parent_id: string | null
  description: string
}

const PERMISSIONS = [
  { key: 'knowledge:read', label: '知识查看' },
  { key: 'knowledge:manage', label: '知识管理（编辑/删除/标签）' },
  { key: 'knowledge:upload', label: '文件上传' },
  { key: 'knowledge:manage_permissions', label: '数据权限管理' },
  { key: 'faq:manage', label: 'FAQ 管理' },
  { key: 'gap:manage', label: '缺口分析' },
  { key: 'dashboard:view', label: '看板查看' },
  { key: 'ai:access', label: 'AI 问答' },
  { key: 'quiz:manage', label: '题库管理' },
]

export function UserManagement({ showToast }: { showToast: (m: string, t: string) => void }) {
  const [users, setUsers] = useState<UserItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditingUser] = useState<{user: UserItem; display_name: string; email: string; department_id: string} | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [allRoles, setAllRoles] = useState<RoleItem[]>([])
  const [editingRoles, setEditingRoles] = useState<string[]>([])
  const [depts, setDepts] = useState<DeptItem[]>([])
  const [form, setForm] = useState({ username: '', password: '', display_name: '', email: '', department_id: '' })

  async function fetchUsers() {
    setLoading(true)
    try {
      const res = await api.get('/api/org/users')
      setUsers(res.data?.items || [])
    } catch { showToast('加载用户失败', 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    fetchUsers()
    api.get('/api/org/departments').then((res) => setDepts(res.data || [])).catch(() => {})
  }, [])

  const deptName = (id: string | undefined) =>
    id ? (depts.find((d) => d.id === id)?.name || '-') : '-'

  const deptSelectStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', fontSize: 14, borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-card)',
    color: 'var(--text)', cursor: 'pointer',
  }

  async function handleDelete(id: string) {
    if (!confirm('确定删除此用户？')) return
    try {
      await api.delete(`/api/org/users/${id}`)
      showToast('删除成功', 'success')
      fetchUsers()
    } catch { showToast('删除失败', 'error') }
  }

  async function handleEdit() {
    if (!editing) return
    try {
      await api.put(`/api/org/users/${editing.user.id}`, {
        display_name: editing.display_name,
        email: editing.email,
        department_id: editing.department_id,
      })

      // 同步角色变更
      const currentRoles = editing.user.roles || []
      const toAdd = editingRoles.filter(r => !currentRoles.includes(r))
      const toRemove = currentRoles.filter(r => !editingRoles.includes(r))
      await Promise.all([
        ...toAdd.map(r => api.put(`/api/org/users/${editing.user.id}/roles`, { role_code: r })),
        ...toRemove.map(r => api.delete(`/api/org/users/${editing.user.id}/roles/${r}`)),
      ])

      showToast('更新成功', 'success')
      setEditingUser(null)
      fetchUsers()
    } catch (err: any) { showToast(err.response?.data?.detail || '更新失败', 'error') }
  }

  async function openEdit(u: UserItem) {
    try {
      const res = await api.get('/api/org/roles')
      setAllRoles(res.data || [])
    } catch { /* ignore */ }
    setEditingRoles(u.roles || [])
    setEditingUser({ user: u, display_name: u.display_name, email: u.email || '', department_id: u.department_id || '' })
  }

  async function handleCreate() {
    if (!form.username.trim() || !form.password) { showToast('用户名和密码必填', 'error'); return }
    try {
      await api.post('/api/org/users', form)
      showToast('创建成功', 'success')
      setShowCreate(false)
      setForm({ username: '', password: '', display_name: '', email: '', department_id: '' })
      fetchUsers()
    } catch (err: any) { showToast(err.response?.data?.detail || '创建失败', 'error') }
  }

  const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }
  const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)' }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>创建用户</button>
      </div>

      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ background: 'var(--bg-card)' }}>
            <th style={thStyle}>用户名</th><th style={thStyle}>显示名</th><th style={thStyle}>邮箱</th><th style={thStyle}>部门</th><th style={thStyle}>角色</th><th style={{ ...thStyle, textAlign: 'center', width: 120 }}>操作</th>
          </tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr> :
              users.length === 0 ? <tr><td colSpan={6} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>暂无用户</td></tr> :
              users.map(u => (
                <tr key={u.id}>
                  <td style={tdStyle}>{u.username}</td>
                  <td style={tdStyle}>{u.display_name}</td>
                  <td style={tdStyle}>{u.email || '-'}</td>
                  <td style={tdStyle}>{deptName(u.department_id)}</td>
                  <td style={tdStyle}>{u.roles?.join(', ') || '-'}</td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 8px' }} onClick={() => openEdit(u)}>编辑</button>
                    <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 8px', color: 'var(--danger)' }} onClick={() => handleDelete(u.id)}>删除</button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <Modal title="创建用户" onClose={() => setShowCreate(false)}>
          <FormField label="用户名 *"><input className="form-input" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></FormField>
          <FormField label="密码 *"><input className="form-input" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></FormField>
          <FormField label="显示名"><input className="form-input" value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} /></FormField>
          <FormField label="邮箱"><input className="form-input" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></FormField>
          <FormField label="部门">
            <select
              value={form.department_id}
              onChange={e => setForm({ ...form, department_id: e.target.value })}
              style={deptSelectStyle}
            >
              <option value="">未分配</option>
              {depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </FormField>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>取消</button>
            <button className="btn btn-primary" onClick={handleCreate}>创建</button>
          </div>
        </Modal>
      )}

      {editing && (
        <Modal title={`编辑用户 - ${editing.user.username}`} onClose={() => setEditingUser(null)}>
          <FormField label="显示名"><input className="form-input" value={editing.display_name} onChange={e => setEditingUser({ ...editing, display_name: e.target.value })} /></FormField>
          <FormField label="邮箱"><input className="form-input" type="email" value={editing.email} onChange={e => setEditingUser({ ...editing, email: e.target.value })} /></FormField>
          <FormField label="部门">
            <select
              value={editing.department_id}
              onChange={e => setEditingUser({ ...editing, department_id: e.target.value })}
              style={deptSelectStyle}
            >
              <option value="">未分配</option>
              {depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </FormField>
          <FormField label="角色">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {allRoles.map(r => (
                <label key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={editingRoles.includes(r.role_code)}
                    onChange={e => {
                      if (e.target.checked) setEditingRoles([...editingRoles, r.role_code])
                      else setEditingRoles(editingRoles.filter(rc => rc !== r.role_code))
                    }}
                  />
                  {r.role_name}
                </label>
              ))}
              {allRoles.length === 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>加载角色中...</span>}
            </div>
          </FormField>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => setEditingUser(null)}>取消</button>
            <button className="btn btn-primary" onClick={handleEdit}>保存</button>
          </div>
        </Modal>
      )}
    </div>
  )
}

export function RoleManagement({ showToast }: { showToast: (m: string, t: string) => void }) {
  const [roles, setRoles] = useState<RoleItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editingPerms, setEditingPerms] = useState<RoleItem | null>(null)
  const [selectedPerms, setSelectedPerms] = useState<string[]>([])

  async function fetchRoles() {
    setLoading(true)
    try {
      const res = await api.get('/api/org/roles')
      setRoles(res.data || [])
    } catch { showToast('加载角色失败', 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchRoles() }, [])

  function openPermEdit(role: RoleItem) {
    setEditingPerms(role)
    setSelectedPerms([...role.permissions])
  }

  async function savePerms() {
    if (!editingPerms) return
    try {
      await api.post(`/api/org/roles/${editingPerms.id}/permissions`, { permissions: selectedPerms })
      showToast('权限更新成功', 'success')
      setEditingPerms(null)
      fetchRoles()
    } catch { showToast('更新失败', 'error') }
  }

  function togglePerm(key: string) {
    setSelectedPerms(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])
  }

  const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }
  const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)' }

  const SUPER_ADMIN_COUNT = PERMISSIONS.length + 1 // +1 for permission:manage

  return (
    <div>
      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ background: 'var(--bg-card)' }}>
            <th style={thStyle}>角色名</th><th style={thStyle}>描述</th><th style={thStyle}>权限</th><th style={{ ...thStyle, textAlign: 'center', width: 100 }}>操作</th>
          </tr></thead>
          <tbody>
            {/* 超级管理员 — 不可编辑 */}
            <tr style={{ background: 'var(--bg-card)' }}>
              <td style={{ ...tdStyle, fontWeight: 600 }}>超级管理员</td>
              <td style={tdStyle}>系统最高权限，拥有权限配置能力</td>
              <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{SUPER_ADMIN_COUNT} 项权限</span></td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>内置</span>
              </td>
            </tr>
            {loading ? <tr><td colSpan={4} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr> :
              roles.filter(r => r.role_code !== 'super_admin').map(r => (
                <tr key={r.id}>
                  <td style={tdStyle}>{r.role_name}</td>
                  <td style={tdStyle}>{r.description || '-'}</td>
                  <td style={tdStyle}><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.permissions?.length || 0} 项权限</span></td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 8px' }} onClick={() => openPermEdit(r)}>权限配置</button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {editingPerms && (
        <Modal title={`配置权限 - ${editingPerms.role_name}`} onClose={() => setEditingPerms(null)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {PERMISSIONS.map(p => (
              <label key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, cursor: 'pointer' }}>
                <input type="checkbox" checked={selectedPerms.includes(p.key)} onChange={() => togglePerm(p.key)} style={{ width: 16, height: 16, accentColor: 'var(--primary)' }} />
                {p.label}
              </label>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => setEditingPerms(null)}>取消</button>
            <button className="btn btn-primary" onClick={savePerms}>保存</button>
          </div>
        </Modal>
      )}
    </div>
  )
}

export function TagManagement({ showToast }: { showToast: (m: string, t: string) => void }) {
  const [tags, setTags] = useState<{id: string; name: string; sort_order: number}[]>([])
  const [loading, setLoading] = useState(true)
  const [newName, setNewName] = useState('')
  const [editing, setEditing] = useState<{id: string; name: string} | null>(null)

  async function fetchTags() {
    setLoading(true)
    try {
      const res = await api.get('/api/tags')
      setTags(res.data || [])
    } catch { showToast('加载标签失败', 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchTags() }, [])

  async function handleCreate() {
    const name = newName.trim()
    if (!name) { showToast('请输入标签名', 'error'); return }
    try {
      await api.post('/api/tags', { name })
      showToast('创建成功', 'success')
      setNewName('')
      fetchTags()
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '创建失败', 'error')
    }
  }

  async function handleRename() {
    if (!editing) return
    const name = editing.name.trim()
    if (!name) { showToast('请输入标签名', 'error'); return }
    try {
      await api.put(`/api/tags/${editing.id}`, { name })
      showToast('重命名成功（引用处已同步更新）', 'success')
      setEditing(null)
      fetchTags()
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '重命名失败', 'error')
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`确定删除标签「${name}」？引用该标签的文档将变为未分类。`)) return
    try {
      await api.delete(`/api/tags/${id}`)
      showToast('删除成功', 'success')
      fetchTags()
    } catch (e: any) {
      showToast(e?.response?.data?.detail || '删除失败', 'error')
    }
  }

  const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }
  const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)' }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="新标签名称"
          style={{ flex: 1, maxWidth: 280, padding: '8px 12px', fontSize: 14, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', fontFamily: 'var(--font)' }}
          onKeyDown={(e) => { if (e.key === 'Enter') handleCreate() }}
        />
        <button className="btn btn-primary" onClick={handleCreate}>新建标签</button>
      </div>

      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ background: 'var(--bg-card)' }}>
            <th style={{ ...thStyle, width: 80 }}>序号</th><th style={thStyle}>标签名</th><th style={{ ...thStyle, textAlign: 'center', width: 160 }}>操作</th>
          </tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={3} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr> :
              tags.length === 0 ? <tr><td colSpan={3} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>暂无标签，上传文档时可先在此创建</td></tr> :
              tags.map((t, idx) => (
                <tr key={t.id}>
                  <td style={tdStyle}>{idx + 1}</td>
                  <td style={tdStyle}>
                    {editing?.id === t.id ? (
                      <input
                        value={editing.name}
                        onChange={(e) => setEditing({ id: editing.id, name: e.target.value })}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleRename() }}
                        style={{ padding: '6px 10px', fontSize: 14, borderRadius: 6, border: '1px solid var(--primary)', background: 'var(--bg-card)', color: 'var(--text)', fontFamily: 'var(--font)', width: 200 }}
                        autoFocus
                      />
                    ) : t.name}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    {editing?.id === t.id ? (
                      <>
                        <button className="btn btn-primary" style={{ fontSize: 12, padding: '4px 8px', marginRight: 6 }} onClick={handleRename}>保存</button>
                        <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 8px' }} onClick={() => setEditing(null)}>取消</button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 8px', marginRight: 6 }} onClick={() => setEditing({ id: t.id, name: t.name })}>重命名</button>
                        <button className="btn btn-danger" style={{ fontSize: 12, padding: '4px 8px' }} onClick={() => handleDelete(t.id, t.name)}>删除</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function DeptManagement({ showToast }: { showToast: (m: string, t: string) => void }) {
  const [depts, setDepts] = useState<DeptItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', parent_id: '', description: '' })

  async function fetchDepts() {
    setLoading(true)
    try {
      const res = await api.get('/api/org/departments')
      setDepts(res.data || [])
    } catch { showToast('加载部门失败', 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchDepts() }, [])

  async function handleCreate() {
    if (!form.name.trim()) { showToast('请输入部门名称', 'error'); return }
    try {
      await api.post('/api/org/departments', { name: form.name.trim(), parent_id: form.parent_id || null, description: form.description.trim() })
      showToast('创建成功', 'success')
      setShowCreate(false)
      setForm({ name: '', parent_id: '', description: '' })
      fetchDepts()
    } catch (err: any) { showToast(err.response?.data?.detail || '创建失败', 'error') }
  }

  async function handleDelete(id: string) {
    if (!confirm('确定删除此部门？')) return
    try {
      await api.delete(`/api/org/departments/${id}`)
      showToast('删除成功', 'success')
      fetchDepts()
    } catch { showToast('删除失败', 'error') }
  }

  const thStyle: React.CSSProperties = { padding: '10px 14px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }
  const tdStyle: React.CSSProperties = { padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border-light)' }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>创建部门</button>
      </div>

      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr style={{ background: 'var(--bg-card)' }}>
            <th style={thStyle}>部门名称</th><th style={thStyle}>描述</th><th style={{ ...thStyle, textAlign: 'center', width: 100 }}>操作</th>
          </tr></thead>
          <tbody>
            {loading ? <tr><td colSpan={3} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</td></tr> :
              depts.length === 0 ? <tr><td colSpan={3} style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>暂无部门</td></tr> :
              depts.map(d => (
                <tr key={d.id}>
                  <td style={tdStyle}>{d.name}</td>
                  <td style={tdStyle}>{d.description || '-'}</td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <button className="btn btn-ghost" style={{ fontSize: 12, padding: '4px 8px', color: 'var(--danger)' }} onClick={() => handleDelete(d.id)}>删除</button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <Modal title="创建部门" onClose={() => setShowCreate(false)}>
          <FormField label="部门名称 *"><input className="form-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></FormField>
          <FormField label="描述"><input className="form-input" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></FormField>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>取消</button>
            <button className="btn btn-primary" onClick={handleCreate}>创建</button>
          </div>
        </Modal>
      )}
    </div>
  )
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={e => e.stopPropagation()} style={{ background: 'var(--bg)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-lg)', width: '90%', maxWidth: 480, animation: 'fadeIn 0.15s' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>{title}</h3>
          <button onClick={onClose} style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 6, cursor: 'pointer', border: 'none', background: 'transparent', fontSize: 18, color: 'var(--text-muted)' }}>&times;</button>
        </div>
        <div style={{ padding: 20 }}>{children}</div>
      </div>
    </div>
  )
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>{label}</label>
      {children}
    </div>
  )
}

// Add form-input styles
if (typeof document !== 'undefined') {
  const styleId = 'form-input-system-admin'
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style')
    style.id = styleId
    style.textContent = `
.form-input {
  width: 100%; padding: 8px 12px; border: 1px solid var(--border);
  border-radius: var(--radius); font-size: 14px; font-family: var(--font);
  color: var(--text); outline: none; background: var(--bg);
}
.form-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-light); }
`
    document.head.appendChild(style)
  }
}

