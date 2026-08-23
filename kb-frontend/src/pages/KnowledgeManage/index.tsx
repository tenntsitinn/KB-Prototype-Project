import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../../services/api'
import { useAuthStore } from '../../stores/authStore'
import { PAGE_SIZE, PERM_TYPE_MAP, STATUS_MAP, formatDate, formatSize, getPermissionTargetName, type Department, type ImportTask, type KnowledgeUnit, type Permission, type Role, type Tag } from './model'
import { S } from './styles'
import { CloseIcon, DeleteIcon, EmptySearchIcon, SearchIcon, UploadIcon } from './icons'
import TagSelect from '../../components/TagSelect'

export default function KnowledgeManage() {

  const { hasPermission } = useAuthStore()
  const canManage = hasPermission('knowledge:manage')
  const canUpload = hasPermission('knowledge:upload')
  const canWrite = canManage
  const canDelete = canManage

  // Tab state
  const [activeTab, setActiveTab] = useState<'units' | 'trash'>('units')

  // Data state
  const [data, setData] = useState<KnowledgeUnit[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [total, setTotal] = useState(0)

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Modal state
  const [detailVisible, setDetailVisible] = useState(false)
  const [detailUnit, setDetailUnit] = useState<KnowledgeUnit | null>(null)
  const [fileLoading, setFileLoading] = useState(false)
  const [editVisible, setEditVisible] = useState(false)
  const [editUnit, setEditUnit] = useState<KnowledgeUnit | null>(null)

  // Edit form state
  const [editTitle, setEditTitle] = useState('')
  const [editCategory, setEditCategory] = useState('')
  const [editSummary, setEditSummary] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editPerms, setEditPerms] = useState<Permission[]>([])

  // Permission form state (detail modal)
  const [newPermType, setNewPermType] = useState('global')
  const [newPermTarget, setNewPermTarget] = useState('')
  const [newPermUser, setNewPermUser] = useState('')

  // Edit permission form state
  const [editNewPermType, setEditNewPermType] = useState('global')
  const [editNewPermTarget, setEditNewPermTarget] = useState('')
  const [editNewPermUser, setEditNewPermUser] = useState('')

  // Import state
  const [importTask, setImportTask] = useState<ImportTask | null>(null)
  const [useUnlimitedOcr, setUseUnlimitedOcr] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)

  // Toast state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Upload refs
  const uploadZoneRef = useRef<HTMLLabelElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Dummy departments and roles (for permission UI)
  const [departments, setDepartments] = useState<Department[]>([])
  const [roles, setRoles] = useState<Role[]>([])

  // Tags
  const [tags, setTags] = useState<Tag[]>([])
  const [uploadCategory, setUploadCategory] = useState('')

  // Trash state
  const [trashData, setTrashData] = useState<KnowledgeUnit[]>([])
  const [trashLoading, setTrashLoading] = useState(false)
  const [trashTotal, setTrashTotal] = useState(0)
  const [trashPage, setTrashPage] = useState(1)
  const [trashSelectedIds, setTrashSelectedIds] = useState<Set<string>>(new Set())
  const [trashBatchLoading, setTrashBatchLoading] = useState(false)
  const [confirmBatchDelete, setConfirmBatchDelete] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const safePage = Math.max(1, Math.min(currentPage, totalPages))

  // ===== Toast =====
  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type })
    if (toastTimer.current) clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 2500)
  }, [])

  // ===== API Calls =====
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, any> = {
        offset: (currentPage - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }
      if (debouncedSearch) params.title = debouncedSearch
      if (categoryFilter) params.category = categoryFilter
      if (statusFilter) params.status = statusFilter
      const res = await api.get('/api/knowledge/units', { params })
      const items = res.data?.items || []
      const totalCount = res.data?.total || 0
      setData(items)
      setTotal(totalCount)
      if (items.length === 0 && currentPage > 1) {
        setCurrentPage(Math.max(1, Math.ceil(totalCount / PAGE_SIZE)))
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.response?.data?.message || err?.message || '加载失败'
      setError(msg)
      showToast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast, currentPage, debouncedSearch, categoryFilter, statusFilter])

  const fetchDepartments = useCallback(async () => {
    try {
      const res = await api.get('/api/org/departments')
      const list = Array.isArray(res.data) ? res.data : res.data?.data || []
      setDepartments(list)
    } catch {
      // Non-critical; use empty list
    }
  }, [])

  const fetchRoles = useCallback(async () => {
    try {
      const res = await api.get('/api/org/roles')
      const list = Array.isArray(res.data) ? res.data : res.data?.data || []
      setRoles(list)
    } catch {
      // Non-critical
    }
  }, [])

  const fetchTags = useCallback(async () => {
    try {
      const res = await api.get('/api/tags')
      const list = Array.isArray(res.data) ? res.data : res.data?.data || []
      setTags(list)
    } catch {
      // Non-critical
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    fetchDepartments()
    fetchRoles()
    fetchTags()
  }, [fetchDepartments, fetchRoles, fetchTags])

  // ===== Upload =====
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPendingFile(file)
    // Reset input so the same file can be re-uploaded
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const startImport = useCallback(async (file: File) => {
    const taskId = 'import_' + Date.now()
    const task: ImportTask = {
      id: taskId,
      fileName: file.name,
      fileSize: file.size,
      progress: 0,
      status: 'processing',
    }
    setImportTask(task)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('use_unlimited_ocr', String(useUnlimitedOcr))
    if (uploadCategory) formData.append('category', uploadCategory)

    try {
      const res = await api.post('/api/knowledge/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      })
      const data = res.data

      setImportTask((prev) => prev ? { ...prev, progress: 100, status: 'completed' } : null)
      showToast('导入成功', 'success')

      // Refresh list + tags（新分类可能已自动入库）
      fetchData()
      fetchTags()
      setUploadCategory('')

      setTimeout(() => setImportTask(null), 2000)
    } catch (err: any) {
      setImportTask((prev) => prev ? { ...prev, status: 'failed' } : null)
      const msg = err?.response?.data?.detail || err?.message || '导入失败'
      showToast(msg, 'error')
    }
  }, [showToast, fetchData, uploadCategory, useUnlimitedOcr])

  const cancelImport = useCallback(() => {
    setImportTask(null)
  }, [])

  const confirmUpload = useCallback(() => {
    if (!pendingFile) return
    const file = pendingFile
    setPendingFile(null)
    startImport(file)
  }, [pendingFile, startImport])

  const cancelUpload = useCallback(() => {
    setPendingFile(null)
  }, [])

  // Drag and drop
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (uploadZoneRef.current) {
      uploadZoneRef.current.style.borderColor = 'var(--primary)'
      uploadZoneRef.current.style.background = 'var(--primary-light)'
    }
  }, [])

  const handleDragLeave = useCallback(() => {
    if (uploadZoneRef.current) {
      uploadZoneRef.current.style.borderColor = 'var(--border)'
      uploadZoneRef.current.style.background = 'var(--bg)'
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    handleDragLeave()
    if (e.dataTransfer.files.length > 0) {
      setPendingFile(e.dataTransfer.files[0])
    }
  }, [handleDragLeave])

  // ===== Retry vectorize (resume) =====
  const retryVectorize = useCallback(async (unit: KnowledgeUnit) => {
    try {
      const res = await api.post(`/api/knowledge/units/${unit.id}/retry-vectorize`)
      const taskId = res.data?.task_id as string | undefined
      showToast('已开始重新向量化，完成后自动刷新列表', 'success')
      if (!taskId) return

      const startedAt = Date.now()
      const poll = setInterval(async () => {
        try {
          const st = await api.get(`/api/knowledge/import/${taskId}/status`)
          const status = st.data?.status
          if (status === 'completed' || status === 'SUCCESS') {
            clearInterval(poll)
            showToast('向量化完成，单元已发布', 'success')
            fetchData()
          } else if (status === 'failed' || status === 'FAILURE') {
            clearInterval(poll)
            showToast(st.data?.error || '向量化失败', 'error')
            fetchData()
          } else if (Date.now() - startedAt > 30 * 60 * 1000) {
            clearInterval(poll)
          }
        } catch {
          clearInterval(poll)
        }
      }, 3000)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '重试失败'
      showToast(msg, 'error')
    }
  }, [showToast, fetchData])

  // ===== Detail Modal =====
  const showDetail = useCallback(async (unit: KnowledgeUnit) => {
    setDetailVisible(true)
    setNewPermType('global')
    setNewPermTarget('')
    setNewPermUser('')
    try {
      const res = await api.get(`/api/knowledge/units/${unit.id}`)
      setDetailUnit(res.data)
    } catch {
      setDetailUnit(unit)
    }
  }, [])

  const hideDetail = useCallback(() => {
    setDetailVisible(false)
    setDetailUnit(null)
  }, [])

  const handleDetailOverlayClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) hideDetail()
  }, [hideDetail])

  const handleDetailEdit = useCallback(() => {
    if (detailUnit) {
      hideDetail()
      showEdit(detailUnit)
    }
  }, [detailUnit, hideDetail])

  const addDetailPermission = useCallback(() => {
    if (!detailUnit) return
    const type = newPermType
    let targetId = ''
    let targetName = ''

    if (type === 'global') {
      targetName = '所有人'
    } else if (type === 'department') {
      targetId = newPermTarget
      const dept = departments.find((d) => d.id === targetId)
      targetName = dept ? dept.name : targetId
    } else if (type === 'role') {
      targetId = newPermTarget
      const role = roles.find((r) => r.role_code === targetId)
      targetName = role ? role.role_name : targetId
    } else {
      targetId = newPermUser.trim()
      targetName = targetId
      if (!targetId) { showToast('请输入用户 ID', 'error'); return }
    }

    const exists = detailUnit.permissions.some((p) => p.target_type === type && p.target_id === targetId)
    if (exists) { showToast('该权限已存在', 'error'); return }

    const newP: Permission = { id: 'p' + Date.now(), target_type: type as Permission['target_type'], target_id: targetId, target_name: targetName }
    const updatedUnit = { ...detailUnit, permissions: [...detailUnit.permissions, newP] }
    setDetailUnit(updatedUnit)
    setData((prev) => prev.map((u) => (u.id === updatedUnit.id ? updatedUnit : u)))
    if (type === 'user') setNewPermUser('')
  }, [detailUnit, newPermType, newPermTarget, newPermUser, departments, roles, showToast])

  const removeDetailPermission = useCallback((pid: string) => {
    if (!detailUnit) return
    const updatedUnit = { ...detailUnit, permissions: detailUnit.permissions.filter((p) => p.id !== pid) }
    setDetailUnit(updatedUnit)
    setData((prev) => prev.map((u) => (u.id === updatedUnit.id ? updatedUnit : u)))
  }, [detailUnit])

  const openSourceFile = useCallback(async () => {
    if (!detailUnit || fileLoading) return
    setFileLoading(true)
    // 同步先开窗口保住用户手势授权，拿到签名 URL 后再跳转
    const win = window.open('about:blank', '_blank')
    try {
      const res = await api.get(`/api/knowledge/units/${detailUnit.id}/file-url`)
      const url: string = res.data?.url
      if (!url) throw new Error('no url')
      if (win) {
        win.location.href = url
      } else {
        window.open(url, '_blank')
      }
    } catch {
      win?.close()
      showToast('原文档加载失败', 'error')
    } finally {
      setFileLoading(false)
    }
  }, [detailUnit, fileLoading, showToast])

  // ===== Edit Modal =====
  const showEdit = useCallback(async (unit: KnowledgeUnit) => {
    setEditVisible(true)
    setEditNewPermType('global')
    setEditNewPermTarget('')
    setEditNewPermUser('')
    try {
      const res = await api.get(`/api/knowledge/units/${unit.id}`)
      const u = res.data
      setEditUnit(u)
      setEditTitle(u.title)
      const cat = u.category || ''
      setEditCategory(cat)
      setEditSummary(u.summary || '')
      setEditContent(u.content || '')
      setEditPerms(u.permissions ? [...u.permissions] : [])
    } catch {
      setEditUnit(unit)
      setEditTitle(unit.title)
      setEditCategory(unit.category || '')
      setEditSummary(unit.summary || '')
      setEditContent(unit.content || '')
      setEditPerms([])
    }
  }, [])

  const hideEdit = useCallback(() => {
    setEditVisible(false)
    setEditUnit(null)
  }, [])

  const handleEditOverlayClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) hideEdit()
  }, [hideEdit])

  const addEditPermission = useCallback(() => {
    const type = editNewPermType
    let targetId = ''
    let targetName = ''

    if (type === 'global') {
      targetName = '所有人'
    } else if (type === 'department') {
      targetId = editNewPermTarget
      const dept = departments.find((d) => d.id === targetId)
      targetName = dept ? dept.name : targetId
    } else if (type === 'role') {
      targetId = editNewPermTarget
      const role = roles.find((r) => r.role_code === targetId)
      targetName = role ? role.role_name : targetId
    } else {
      targetId = editNewPermUser.trim()
      targetName = targetId
      if (!targetId) { showToast('请输入用户 ID', 'error'); return }
    }

    const exists = editPerms.some((p) => p.target_type === type && p.target_id === targetId)
    if (exists) { showToast('该权限已存在', 'error'); return }

    const newP: Permission = { id: 'p' + Date.now(), target_type: type as Permission['target_type'], target_id: targetId, target_name: targetName }
    setEditPerms((prev) => [...prev, newP])
    if (type === 'user') setEditNewPermUser('')
  }, [editNewPermType, editNewPermTarget, editNewPermUser, editPerms, departments, roles, showToast])

  const removeEditPermission = useCallback((pid: string) => {
    setEditPerms((prev) => prev.filter((p) => p.id !== pid))
  }, [])

  const handleSaveEdit = useCallback(async () => {
    if (!editUnit) return
    if (!editTitle.trim()) { showToast('标题不能为空', 'error'); return }

    try {
      const payload = {
        title: editTitle.trim(),
        category: editCategory.trim(),
        summary: editSummary,
        content: editContent,
        permissions: editPerms,
      }
      const res = await api.put(`/api/knowledge/units/${editUnit.id}`, payload)
      const updated = res.data?.data || res.data

      setData((prev) => prev.map((u) => (u.id === editUnit.id ? { ...u, ...updated } : u)))
      fetchTags()
      hideEdit()
      showToast('保存成功', 'success')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '保存失败'
      showToast(msg, 'error')
    }
  }, [editUnit, editTitle, editCategory, editSummary, editContent, editPerms, hideEdit, showToast, fetchTags])

  // ===== Delete =====
  const deleteUnit = useCallback(async (id: string) => {
    if (!window.confirm('确定要删除该知识单元吗？')) return
    try {
      await api.delete(`/api/knowledge/units/${id}`)
      setData((prev) => prev.filter((u) => u.id !== id))
      setTotal((prev) => Math.max(0, prev - 1))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      showToast('已删除', 'success')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '删除失败'
      showToast(msg, 'error')
    }
  }, [showToast])

  const batchDelete = useCallback(async () => {
    if (selectedIds.size === 0) return
    if (!window.confirm(`确定要批量删除 ${selectedIds.size} 个知识单元吗？`)) return
    try {
      await api.delete('/api/knowledge/units', { data: { unit_ids: Array.from(selectedIds) } })
      const deletedCount = selectedIds.size
      setData((prev) => prev.filter((u) => !selectedIds.has(u.id)))
      setTotal((prev) => Math.max(0, prev - deletedCount))
      setSelectedIds(new Set())
      showToast('已批量删除', 'success')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '批量删除失败'
      showToast(msg, 'error')
    }
  }, [selectedIds, showToast])

  // ===== Trash =====
  const fetchTrashData = useCallback(async () => {
    if (!canManage) return
    setTrashLoading(true)
    try {
      const res = await api.get('/api/knowledge/units', {
        params: { status: 'deleted', offset: (trashPage - 1) * PAGE_SIZE, limit: PAGE_SIZE },
      })
      setTrashData(res.data?.items || [])
      setTrashTotal(res.data?.total || 0)
    } catch {
      // ignore
    } finally {
      setTrashLoading(false)
    }
  }, [canManage, trashPage])

  useEffect(() => {
    if (activeTab === 'trash') fetchTrashData()
  }, [activeTab, fetchTrashData])

  // 翻页/刷新后清掉失效的勾选
  useEffect(() => {
    setTrashSelectedIds(new Set())
  }, [trashPage, activeTab])

  const isTrashAllSelected = trashData.length > 0 && trashData.every((u) => trashSelectedIds.has(u.id))

  const toggleTrashSelectAll = useCallback(() => {
    setTrashSelectedIds((prev) => {
      if (trashData.length > 0 && trashData.every((u) => prev.has(u.id))) return new Set()
      return new Set(trashData.map((u) => u.id))
    })
  }, [trashData])

  const toggleTrashSelectOne = useCallback((id: string) => {
    setTrashSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const batchRestore = useCallback(async () => {
    if (trashSelectedIds.size === 0 || trashBatchLoading) return
    const ids = Array.from(trashSelectedIds)
    if (!window.confirm(`确定要恢复选中的 ${ids.length} 个知识单元吗？`)) return
    setTrashBatchLoading(true)
    try {
      await api.put('/api/knowledge/units/batch/restore', { unit_ids: ids })
      setTrashData((prev) => prev.filter((u) => !trashSelectedIds.has(u.id)))
      setTrashTotal((prev) => Math.max(0, prev - ids.length))
      setTrashSelectedIds(new Set())
      showToast(`已恢复 ${ids.length} 个单元`, 'success')
      fetchData()
    } catch (err: any) {
      showToast(err?.response?.data?.detail || '批量恢复失败', 'error')
    } finally {
      setTrashBatchLoading(false)
    }
  }, [trashSelectedIds, trashBatchLoading, showToast, fetchData])

  const batchPermanentDelete = useCallback(async () => {
    if (trashSelectedIds.size === 0 || trashBatchLoading) return
    const ids = Array.from(trashSelectedIds)
    setTrashBatchLoading(true)
    try {
      const res = await api.delete('/api/knowledge/units/batch/permanent', { data: { unit_ids: ids } })
      const deleted = res.data?.deleted_count ?? ids.length
      setTrashData((prev) => prev.filter((u) => !trashSelectedIds.has(u.id)))
      setTrashTotal((prev) => Math.max(0, prev - deleted))
      setTrashSelectedIds(new Set())
      setConfirmBatchDelete(false)
      showToast(`已永久删除 ${deleted} 个单元`, 'success')
    } catch (err: any) {
      showToast(err?.response?.data?.detail || '批量删除失败', 'error')
    } finally {
      setTrashBatchLoading(false)
    }
  }, [trashSelectedIds, trashBatchLoading, showToast])

  const handleRestore = useCallback(async (id: string) => {
    setActionLoading(id)
    try {
      await api.put(`/api/knowledge/units/${id}/restore`)
      setTrashData((prev) => prev.filter((u) => u.id !== id))
      setTrashTotal((prev) => prev - 1)
      showToast('已恢复', 'success')
    } catch (err: any) {
      showToast(err?.response?.data?.detail || '恢复失败', 'error')
    } finally {
      setActionLoading(null)
    }
  }, [showToast])

  const handlePermanentDelete = useCallback(async (id: string) => {
    setActionLoading(id)
    try {
      await api.delete(`/api/knowledge/units/${id}/permanent`)
      setTrashData((prev) => prev.filter((u) => u.id !== id))
      setTrashTotal((prev) => prev - 1)
      setConfirmDeleteId(null)
      showToast('已永久删除', 'success')
    } catch (err: any) {
      showToast(err?.response?.data?.detail || '删除失败', 'error')
    } finally {
      setActionLoading(null)
    }
  }, [showToast])

  // ===== Selection =====
  const toggleSelectAll = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(new Set(data.map((item) => item.id)))
    } else {
      setSelectedIds(new Set())
    }
  }, [data])

  const toggleSelectOne = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const isAllSelected = data.length > 0 && data.every((item) => selectedIds.has(item.id))

  // ===== Pagination =====
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearch, categoryFilter, statusFilter])

  useEffect(() => {
    setSelectedIds(new Set())
  }, [currentPage])

  // ===== Render =====
  return (
    <div style={S.content}>
      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: 0, background: 'var(--bg)', borderRadius: 'var(--radius)', border: '1px solid var(--border)', padding: 4 }}>
        <button
          onClick={() => setActiveTab('units')}
          style={{
            flex: 1, padding: '8px 16px', fontSize: 13, fontWeight: activeTab === 'units' ? 600 : 400,
            border: 'none', borderRadius: 6, cursor: 'pointer',
            background: activeTab === 'units' ? 'var(--primary)' : 'transparent',
            color: activeTab === 'units' ? '#fff' : 'var(--text-secondary)',
            transition: 'all 0.15s',
          }}
        >知识单元</button>
        {canManage && (
          <button
            onClick={() => setActiveTab('trash')}
            style={{
              flex: 1, padding: '8px 16px', fontSize: 13, fontWeight: activeTab === 'trash' ? 600 : 400,
              border: 'none', borderRadius: 6, cursor: 'pointer',
              background: activeTab === 'trash' ? 'var(--primary)' : 'transparent',
              color: activeTab === 'trash' ? '#fff' : 'var(--text-secondary)',
              transition: 'all 0.15s',
            }}
          >回收站</button>
        )}
      </div>

      {activeTab === 'units' ? (
      <>
      {/* Upload Zone */}
      {canUpload && (
        <>
      <label
        ref={uploadZoneRef}
        htmlFor="fileInput"
        style={S.uploadZone}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div style={S.uploadZoneIcon}>
          <UploadIcon />
        </div>
        <h3 style={S.uploadZoneH3}>点击或拖拽文件到此处上传</h3>
        <p style={S.uploadZoneP}>支持 PDF/DOCX（100MB，超限自动拆分）、MD/TXT（5MB）、ZIP（MD+图片）</p>
        <div style={S.uploadFormats}>
          <span style={S.formatTag}>PDF</span>
          <span style={S.formatTag}>DOCX</span>
          <span style={S.formatTag}>MD</span>
          <span style={S.formatTag}>TXT</span>
          <span style={S.formatTag}>ZIP</span>
        </div>
        <p style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
          上传前可确认文档分类与解析选项
        </p>
      </label>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.doc,.md,.markdown,.txt,.zip"
        style={{ display: 'none' }}
        onChange={handleFileChange}
        id="fileInput"
      />
      </>
      )}

      {/* Import Progress Bar */}
      {importTask && (
        <div style={S.importBar}>
          <div style={S.importBarInfo}>
            <div style={S.importBarName}>{importTask.fileName}</div>
            <div style={S.importBarFile}>{formatSize(importTask.fileSize)}</div>
          </div>
          <div style={S.importBarProgress}>
            <div style={{ ...S.importBarProgressFill, width: `${importTask.progress}%` }} />
          </div>
          <div style={S.importBarPct}>{Math.floor(importTask.progress)}%</div>
          <div style={S.importBarStatus(importTask.status)}>
            {importTask.status === 'processing' ? '解析中' : importTask.status === 'completed' ? '完成' : '失败'}
          </div>
          <div
            style={S.importBarClose}
            onClick={cancelImport}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-hover)'; (e.currentTarget as HTMLElement).style.color = 'var(--text)' }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)' }}
          >
            <CloseIcon />
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div style={S.toolbar}>
        <div style={S.searchBox}>
          <div style={S.searchIcon}>
            <SearchIcon />
          </div>
          <input
            type="text"
            placeholder="搜索知识单元标题..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={S.searchInput}
            onFocus={(e) => { e.target.style.borderColor = 'var(--primary)'; e.target.style.boxShadow = '0 0 0 3px var(--primary-light)' }}
            onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
          />
        </div>
        <TagSelect
          tags={tags}
          value={categoryFilter}
          onChange={setCategoryFilter}
          emptyLabel="全部分类"
          placeholder="搜索分类…"
          width={200}
        />
        <select
          style={S.filterSelect}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">全部状态</option>
          <option value="published">已发布</option>
          <option value="draft">草稿</option>
        </select>
        <div style={S.toolbarSpacer} />
        {selectedIds.size > 0 && (
          <span style={S.selectedCount}>已选 {selectedIds.size} 项</span>
        )}
        {selectedIds.size > 0 && canDelete && (
          <button className="btn btn-danger" onClick={batchDelete}>
            <DeleteIcon />
            批量删除 ({selectedIds.size})
          </button>
        )}
      </div>

      {/* Table Card */}
      <div style={S.tableCard}>
        <div style={S.tableCardHeader}>
          <h3 style={S.tableCardHeaderH3}>知识单元列表</h3>
          <span style={S.tableCardHeaderCount}>共 {total} 条</span>
        </div>
        <div style={S.tableWrapper}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={{ ...S.th, ...S.thFirst, width: 36 }}>
                  <input
                    type="checkbox"
                    style={S.rowCheckbox}
                    checked={isAllSelected}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th style={S.th}>标题</th>
                <th style={S.th}>分类</th>
                <th style={S.th}>文件类型</th>
                <th style={S.th}>状态</th>
                <th style={S.th}>创建时间</th>
                <th style={{ ...S.th, ...S.thLast }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7}>
                    <div style={S.loading}>加载中...</div>
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={7}>
                    <div style={S.emptyState}>
                      <p style={S.emptyStateP}>页面加载失败，请刷新重试</p>
                    </div>
                  </td>
                </tr>
              ) : data.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <div style={S.emptyState}>
                      <EmptySearchIcon />
                      <p style={{ ...S.emptyStateP, marginTop: 12 }}>没有找到匹配的知识单元</p>
                    </div>
                  </td>
                </tr>
              ) : (
                data.map((item) => (
                  <tr
                    key={item.id}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-hover)' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = '' }}
                  >
                    <td style={{ ...S.td, ...S.tdFirst }}>
                      <input
                        type="checkbox"
                        style={S.rowCheckbox}
                        checked={selectedIds.has(item.id)}
                        onChange={() => toggleSelectOne(item.id)}
                      />
                    </td>
                    <td style={S.td}>
                      <div
                        style={S.cellTitle}
                        onClick={() => showDetail(item)}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--primary)'; (e.currentTarget as HTMLElement).style.textDecoration = 'underline' }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--text)'; (e.currentTarget as HTMLElement).style.textDecoration = 'none' }}
                      >
                        {item.title}
                      </div>
                      <div style={S.cellMeta}>{item.unit_code}</div>
                    </td>
                    <td style={S.td}>{item.category || '-'}</td>
                    <td style={S.td}>
                      <span style={S.fileTypeTag}>{item.file_type.toUpperCase()}</span>
                    </td>
                    <td style={S.td}>
                      <span style={S.statusBadge(item.status)}>
                        <span style={S.statusDot(item.status)} />
                        {STATUS_MAP[item.status] || item.status}
                      </span>
                    </td>
                    <td style={S.td}>
                      <span style={S.cellMeta}>{item.created_at}</span>
                    </td>
                    <td style={{ ...S.td, ...S.tdLast }}>
                      <div style={S.actionsCell}>
                        <button className="btn btn-outline btn-xs" onClick={() => showDetail(item)}>查看</button>
                        {canWrite && <button className="btn btn-outline btn-xs" onClick={() => showEdit(item)}>编辑</button>}
                        {item.status === 'draft' && canUpload && (
                          <button className="btn btn-primary btn-xs" onClick={() => retryVectorize(item)}>重试</button>
                        )}
                        {canDelete && <button className="btn btn-danger btn-xs" onClick={() => deleteUnit(item.id)}>删除</button>}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        <div style={S.pagination}>
          <div style={S.paginationInfo}>
            {total === 0
              ? '显示 0-0，共 0 条'
              : `显示 ${(safePage - 1) * PAGE_SIZE + 1}-${Math.min(safePage * PAGE_SIZE, total)}，共 ${total} 条`
            }
          </div>
          {totalPages > 1 && (
            <div style={S.paginationBtns}>
              <button
                style={safePage === 1 ? S.pageBtnDisabled : S.pageBtn(false)}
                disabled={safePage === 1}
                onClick={() => setCurrentPage(safePage - 1)}
              >
                &laquo;
              </button>
              {(() => {
                const btns: React.ReactNode[] = []
                const startPage = Math.max(1, Math.min(safePage - 2, totalPages - 4))
                const endPage = Math.min(totalPages, Math.max(safePage + 2, 5))
                if (startPage > 1) {
                  btns.push(<button key="1" style={S.pageBtn(false)} onClick={() => setCurrentPage(1)}>1</button>)
                  btns.push(<span key="d1" style={S.pageEllipsis}>...</span>)
                }
                for (let p = startPage; p <= endPage; p++) {
                  btns.push(
                    <button
                      key={p}
                      style={S.pageBtn(p === safePage)}
                      onClick={() => setCurrentPage(p)}
                    >
                      {p}
                    </button>
                  )
                }
                if (endPage < totalPages) {
                  btns.push(<span key="d2" style={S.pageEllipsis}>...</span>)
                  btns.push(<button key={totalPages} style={S.pageBtn(false)} onClick={() => setCurrentPage(totalPages)}>{totalPages}</button>)
                }
                btns.push(
                  <button
                    key="next"
                    style={safePage === totalPages ? S.pageBtnDisabled : S.pageBtn(false)}
                    disabled={safePage === totalPages}
                    onClick={() => setCurrentPage(safePage + 1)}
                  >
                    &raquo;
                  </button>
                )
                return btns
              })()}
            </div>
          )}
        </div>
      </div>

      {/* Detail Modal */}
      {detailVisible && detailUnit && (
        <div style={S.modalOverlay} onClick={handleDetailOverlayClick}>
          <div style={S.modal}>
            <div style={S.modalHeader}>
              <h3 style={S.modalHeaderH3}>{detailUnit.title}</h3>
              <button style={S.modalClose} onClick={hideDetail}>&times;</button>
            </div>
            <div style={S.modalBody}>
              <div style={S.detailMetaGrid}>
                <div>
                  <div style={S.detailLabel}>编码</div>
                  <div style={S.detailValue}>{detailUnit.unit_code}</div>
                </div>
                <div>
                  <div style={S.detailLabel}>分类</div>
                  <div style={S.detailValue}>{detailUnit.category || '-'}</div>
                </div>
                <div>
                  <div style={S.detailLabel}>状态</div>
                  <div style={S.detailValue}>
                    <span style={S.statusBadge(detailUnit.status)}>
                      <span style={S.statusDot(detailUnit.status)} />
                      {STATUS_MAP[detailUnit.status] || detailUnit.status}
                    </span>
                  </div>
                </div>
                <div>
                  <div style={S.detailLabel}>源文件</div>
                  <div style={S.detailValue}>{detailUnit.source_file_name}</div>
                </div>
                <div>
                  <div style={S.detailLabel}>文件大小</div>
                  <div style={S.detailValue}>{formatSize(detailUnit.file_size)}</div>
                </div>
                <div>
                  <div style={S.detailLabel}>创建时间</div>
                  <div style={S.detailValue}>{detailUnit.created_at}</div>
                </div>
              </div>
              {detailUnit.summary && (
                <div style={S.detailSection}>
                  <div style={S.detailLabel}>摘要</div>
                  <div style={S.detailValue}>{detailUnit.summary}</div>
                </div>
              )}
              <div style={S.detailSection}>
                <div style={S.detailLabel}>原文档</div>
                <div style={S.detailValue}>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={openSourceFile}
                    disabled={fileLoading}
                  >
                    {fileLoading ? '加载中…' : '查看原文档'}
                  </button>
                </div>
              </div>
              <div style={S.permSection}>
                <div style={S.detailLabel}>数据权限</div>
                <div style={S.permList}>
                  {detailUnit.permissions.map((p) => (
                    <div key={p.id} style={S.permItem}>
                      <span>
                        <span style={S.permType}>{PERM_TYPE_MAP[p.target_type] || p.target_type}</span>
                        <span style={S.permId}>{getPermissionTargetName(p, departments, roles)}</span>
                      </span>
                      <span
                        style={S.permRemove}
                        onClick={() => removeDetailPermission(p.id)}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--danger)'; (e.currentTarget as HTMLElement).style.background = 'rgba(234,67,53,0.08)' }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)'; (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                      >
                        &times;
                      </span>
                    </div>
                  ))}
                </div>
                <div style={S.permAdd}>
                  <select
                    style={S.permAddSelect}
                    value={newPermType}
                    onChange={(e) => {
                      setNewPermType(e.target.value)
                      setNewPermTarget('')
                      setNewPermUser('')
                    }}
                  >
                    <option value="global">全局可见</option>
                    <option value="department">指定部门</option>
                    <option value="role">指定角色</option>
                    <option value="user">指定用户</option>
                  </select>
                  {newPermType === 'department' && (
                    <select
                      style={{ ...S.permAddSelect, flex: 1 }}
                      value={newPermTarget}
                      onChange={(e) => setNewPermTarget(e.target.value)}
                    >
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  )}
                  {newPermType === 'role' && (
                    <select
                      style={{ ...S.permAddSelect, flex: 1 }}
                      value={newPermTarget}
                      onChange={(e) => setNewPermTarget(e.target.value)}
                    >
                      {roles.map((r) => (
                        <option key={r.role_code} value={r.role_code}>{r.role_name}</option>
                      ))}
                    </select>
                  )}
                  {newPermType === 'user' && (
                    <input
                      type="text"
                      placeholder="输入用户 ID"
                      value={newPermUser}
                      onChange={(e) => setNewPermUser(e.target.value)}
                      style={S.permAddInput}
                      onFocus={(e) => { e.target.style.borderColor = 'var(--primary)' }}
                      onBlur={(e) => { e.target.style.borderColor = 'var(--border)' }}
                    />
                  )}
                  <button className="btn btn-primary btn-sm" onClick={addDetailPermission}>添加</button>
                </div>
              </div>
            </div>
            <div style={S.modalFooter}>
              <button className="btn btn-outline" onClick={handleDetailEdit}>编辑</button>
              <button className="btn btn-ghost" onClick={hideDetail}>关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editVisible && editUnit && (
        <div style={S.modalOverlay} onClick={handleEditOverlayClick}>
          <div style={S.modal}>
            <div style={S.modalHeader}>
              <h3 style={S.modalHeaderH3}>编辑知识单元</h3>
              <button style={S.modalClose} onClick={hideEdit}>&times;</button>
            </div>
            <div style={S.modalBody}>
              <div style={S.formGroup}>
                <label style={S.formLabel}>标题</label>
                <input
                  style={S.formInput}
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onFocus={(e) => { e.target.style.borderColor = 'var(--primary)'; e.target.style.boxShadow = '0 0 0 3px var(--primary-light)' }}
                  onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
                />
              </div>
              <div style={S.formGroup}>
                <label style={S.formLabel}>分类</label>
                <TagSelect
                  tags={tags}
                  value={editCategory}
                  onChange={setEditCategory}
                  emptyLabel="未分类"
                  allowCustom
                  maxLength={50}
                />
              </div>
              <div style={S.formGroup}>
                <label style={S.formLabel}>摘要</label>
                <textarea
                  style={S.formTextarea}
                  rows={3}
                  placeholder="可选"
                  value={editSummary}
                  onChange={(e) => setEditSummary(e.target.value)}
                  onFocus={(e) => { e.target.style.borderColor = 'var(--primary)'; e.target.style.boxShadow = '0 0 0 3px var(--primary-light)' }}
                  onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
                />
              </div>
              <div style={S.formGroup}>
                <label style={S.formLabel}>内容</label>
                <textarea
                  style={S.formTextarea}
                  rows={8}
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  onFocus={(e) => { e.target.style.borderColor = 'var(--primary)'; e.target.style.boxShadow = '0 0 0 3px var(--primary-light)' }}
                  onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
                />
              </div>
              <div style={S.formGroup}>
                <label style={S.formLabel}>数据权限</label>
                <div style={S.permList}>
                  {editPerms.map((p) => (
                    <div key={p.id} style={S.permItem}>
                      <span>
                        <span style={S.permType}>{PERM_TYPE_MAP[p.target_type] || p.target_type}</span>
                        <span style={S.permId}>{getPermissionTargetName(p, departments, roles)}</span>
                      </span>
                      <span
                        style={S.permRemove}
                        onClick={() => removeEditPermission(p.id)}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--danger)'; (e.currentTarget as HTMLElement).style.background = 'rgba(234,67,53,0.08)' }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = 'var(--text-muted)'; (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                      >
                        &times;
                      </span>
                    </div>
                  ))}
                </div>
                <div style={S.permAdd}>
                  <select
                    style={S.permAddSelect}
                    value={editNewPermType}
                    onChange={(e) => {
                      setEditNewPermType(e.target.value)
                      setEditNewPermTarget('')
                      setEditNewPermUser('')
                    }}
                  >
                    <option value="global">全局可见</option>
                    <option value="department">指定部门</option>
                    <option value="role">指定角色</option>
                    <option value="user">指定用户</option>
                  </select>
                  {editNewPermType === 'department' && (
                    <select
                      style={{ ...S.permAddSelect, flex: 1 }}
                      value={editNewPermTarget}
                      onChange={(e) => setEditNewPermTarget(e.target.value)}
                    >
                      {departments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  )}
                  {editNewPermType === 'role' && (
                    <select
                      style={{ ...S.permAddSelect, flex: 1 }}
                      value={editNewPermTarget}
                      onChange={(e) => setEditNewPermTarget(e.target.value)}
                    >
                      {roles.map((r) => (
                        <option key={r.role_code} value={r.role_code}>{r.role_name}</option>
                      ))}
                    </select>
                  )}
                  {editNewPermType === 'user' && (
                    <input
                      type="text"
                      placeholder="输入用户 ID"
                      value={editNewPermUser}
                      onChange={(e) => setEditNewPermUser(e.target.value)}
                      style={S.permAddInput}
                      onFocus={(e) => { e.target.style.borderColor = 'var(--primary)' }}
                      onBlur={(e) => { e.target.style.borderColor = 'var(--border)' }}
                    />
                  )}
                  <button className="btn btn-primary btn-sm" onClick={addEditPermission}>添加</button>
                </div>
              </div>
            </div>
            <div style={S.modalFooter}>
              <button className="btn btn-primary" onClick={handleSaveEdit}>保存</button>
              <button className="btn btn-ghost" onClick={hideEdit}>取消</button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div style={{ ...S.toast, ...(toast.type === 'success' ? S.toastSuccess : S.toastError) }}>
          {toast.message}
        </div>
      )}
      </>
      ) : (
      /* ===== Trash Tab ===== */
      <div style={S.tableCard}>
        <div style={S.tableCardHeader}>
          <h3 style={S.tableCardHeaderH3}>回收站</h3>
          <span style={S.tableCardHeaderCount}>共 {trashTotal} 条 · 删除后保留 7 天</span>
        </div>
        {trashSelectedIds.size > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', borderBottom: '1px solid var(--border-light)', background: 'var(--primary-light)' }}>
            <span style={{ fontSize: 13, color: 'var(--text)' }}>已选 {trashSelectedIds.size} 项</span>
            <div style={{ flex: 1 }} />
            <button
              className="btn btn-outline"
              disabled={trashBatchLoading}
              onClick={batchRestore}
            >
              {trashBatchLoading ? '处理中…' : `批量恢复 (${trashSelectedIds.size})`}
            </button>
            <button
              className="btn btn-danger"
              disabled={trashBatchLoading}
              onClick={() => setConfirmBatchDelete(true)}
            >
              批量永久删除 ({trashSelectedIds.size})
            </button>
          </div>
        )}
        <div style={S.tableWrapper}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={{ ...S.th, ...S.thFirst, width: 36 }}>
                  <input
                    type="checkbox"
                    style={S.rowCheckbox}
                    checked={isTrashAllSelected}
                    onChange={toggleTrashSelectAll}
                  />
                </th>
                <th style={S.th}>标题</th>
                <th style={S.th}>分类</th>
                <th style={S.th}>文件类型</th>
                <th style={S.th}>文件大小</th>
                <th style={S.th}>删除时间</th>
                <th style={{ ...S.th, textAlign: 'center' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {trashLoading ? (
                <tr><td colSpan={7}><div style={S.loading}>加载中...</div></td></tr>
              ) : trashData.length === 0 ? (
                <tr><td colSpan={7}><div style={S.emptyState}><p style={S.emptyStateP}>回收站为空</p></div></td></tr>
              ) : (
                trashData.map((unit) => (
                  <tr
                    key={unit.id}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-hover)' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = '' }}
                  >
                    <td style={{ ...S.td, ...S.tdFirst }}>
                      <input
                        type="checkbox"
                        style={S.rowCheckbox}
                        checked={trashSelectedIds.has(unit.id)}
                        onChange={() => toggleTrashSelectOne(unit.id)}
                      />
                    </td>
                    <td style={S.td}>
                      <div style={S.cellTitle}>{unit.title}</div>
                      <div style={S.cellMeta}>{unit.unit_code}</div>
                    </td>
                    <td style={S.td}>{unit.category || '-'}</td>
                    <td style={S.td}>
                      <span style={S.fileTypeTag}>{unit.file_type?.toUpperCase() || '--'}</span>
                    </td>
                    <td style={S.td}>
                      <span style={S.cellMeta}>{formatSize(unit.file_size)}</span>
                    </td>
                    <td style={S.td}>
                      <span style={S.cellMeta}>{formatDate(unit.deleted_at)}</span>
                    </td>
                    <td style={{ ...S.td, textAlign: 'center' }}>
                      <div style={S.actionsCell}>
                        <button
                          style={S.trashRestoreBtn}
                          onClick={() => handleRestore(unit.id)}
                          disabled={actionLoading === unit.id}
                        >{actionLoading === unit.id ? '...' : '恢复'}</button>
                        <button
                          style={S.trashDeleteBtn}
                          onClick={() => setConfirmDeleteId(unit.id)}
                          disabled={actionLoading === unit.id}
                        >永久删除</button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        {Math.ceil(trashTotal / PAGE_SIZE) > 1 && (
          <div style={S.pagination}>
            <div style={S.paginationInfo}>
              {trashData.length === 0
                ? '显示 0-0，共 0 条'
                : `显示 ${(trashPage - 1) * PAGE_SIZE + 1}-${Math.min(trashPage * PAGE_SIZE, trashTotal)}，共 ${trashTotal} 条`
              }
            </div>
            <div style={S.paginationBtns}>
              <button
                style={trashPage <= 1 ? S.pageBtnDisabled : S.pageBtn(false)}
                disabled={trashPage <= 1}
                onClick={() => setTrashPage(trashPage - 1)}
              >&laquo;</button>
              <button
                style={S.pageBtn(true)}
                onClick={() => {}}
              >{trashPage}</button>
              <button
                style={trashPage >= Math.ceil(trashTotal / PAGE_SIZE) ? S.pageBtnDisabled : S.pageBtn(false)}
                disabled={trashPage >= Math.ceil(trashTotal / PAGE_SIZE)}
                onClick={() => setTrashPage(trashPage + 1)}
              >&raquo;</button>
            </div>
          </div>
        )}
      </div>
      )}

      {/* Upload Confirm Modal */}
      {pendingFile && (
        <div style={S.modalOverlay}>
          <div style={{ ...S.modal, maxWidth: 460, maxHeight: 'none' }}>
            <div style={S.modalHeader}>
              <h3 style={S.modalHeaderH3}>确认上传</h3>
              <button style={S.modalClose} onClick={cancelUpload}>&times;</button>
            </div>
            <div style={S.modalBody}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px',
                background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, marginBottom: 16,
              }}>
                <span style={{ ...S.fileTypeTag, flexShrink: 0 }}>
                  {(pendingFile.name.split('.').pop() || '').toUpperCase()}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {pendingFile.name}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                    {formatSize(pendingFile.size)}
                  </div>
                </div>
              </div>

              <div style={S.formGroup}>
                <label style={S.formLabel}>文档分类（可选，支持搜索或输入新分类）</label>
                <TagSelect
                  tags={tags}
                  value={uploadCategory}
                  onChange={setUploadCategory}
                  emptyLabel="不指定"
                  allowCustom
                  maxLength={50}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <input
                  type="checkbox"
                  id="ocrToggle"
                  checked={useUnlimitedOcr}
                  onChange={(e) => setUseUnlimitedOcr(e.target.checked)}
                  style={{ width: 14, height: 14, accentColor: 'var(--primary)', cursor: 'pointer', marginTop: 2 }}
                />
                <label
                  htmlFor="ocrToggle"
                  style={{ fontSize: 12, color: 'var(--text-muted)', cursor: 'pointer', lineHeight: 1.5 }}
                >
                  PDF 使用 Unlimited-OCR 解析（需单独部署 GPU 服务）
                </label>
              </div>
            </div>
            <div style={S.modalFooter}>
              <button className="btn btn-ghost" onClick={cancelUpload}>取消</button>
              <button className="btn btn-primary" onClick={confirmUpload}>
                <UploadIcon />
                开始上传
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Permanent Delete Modal */}
      {confirmDeleteId && (
        <div style={S.modalOverlay} onClick={() => setConfirmDeleteId(null)}>
          <div style={{ ...S.modal, maxWidth: 400, maxHeight: 'none' }}>
            <div style={S.modalHeader}>
              <h3 style={S.modalHeaderH3}>确认永久删除</h3>
            </div>
            <div style={S.modalBody}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                此操作将立即删除该文档的所有数据（包括 MinIO 图片和向量），不可恢复。
              </p>
            </div>
            <div style={S.modalFooter}>
              <button className="btn btn-ghost" onClick={() => setConfirmDeleteId(null)}>取消</button>
              <button className="btn btn-danger" onClick={() => handlePermanentDelete(confirmDeleteId)}>确认删除</button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Batch Permanent Delete Modal */}
      {confirmBatchDelete && (
        <div style={S.modalOverlay} onClick={() => setConfirmBatchDelete(false)}>
          <div style={{ ...S.modal, maxWidth: 400, maxHeight: 'none' }}>
            <div style={S.modalHeader}>
              <h3 style={S.modalHeaderH3}>确认批量永久删除</h3>
            </div>
            <div style={S.modalBody}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                此操作将立即删除选中的 {trashSelectedIds.size} 个文档的所有数据（包括 MinIO 图片和向量），不可恢复。
              </p>
            </div>
            <div style={S.modalFooter}>
              <button className="btn btn-ghost" onClick={() => setConfirmBatchDelete(false)}>取消</button>
              <button className="btn btn-danger" disabled={trashBatchLoading} onClick={batchPermanentDelete}>
                {trashBatchLoading ? '删除中…' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
