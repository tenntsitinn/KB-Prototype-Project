import { useState, useEffect } from 'react'
import api from '../services/api'

interface CourseItem { id: string; title: string }
interface ChapterNode { id: string; title: string; children: ChapterNode[] }
export interface PointItem { id: string; title: string }

export interface CategoryValue {
  courseId: string
  chapterId: string
  pointId: string
}

export const emptyCategory: CategoryValue = { courseId: '', chapterId: '', pointId: '' }

const selectStyle: React.CSSProperties = {
  padding: '8px 12px', fontSize: 13, borderRadius: 8,
  border: '1px solid var(--border)', background: 'var(--bg-card)',
  color: 'var(--text)', cursor: 'pointer', outline: 'none', fontFamily: 'var(--font)',
}

const smallSelectStyle: React.CSSProperties = {
  padding: '6px 10px', fontSize: 12, borderRadius: 6,
  border: '1px solid var(--border)', background: 'var(--bg)',
  color: 'var(--text)', cursor: 'pointer', outline: 'none', fontFamily: 'var(--font)',
}

function flattenChapters(nodes: ChapterNode[], depth: number, out: { id: string; title: string; depth: number }[]) {
  for (const n of nodes) {
    out.push({ id: n.id, title: n.title, depth })
    flattenChapters(n.children, depth + 1, out)
  }
}

export function useCategoryData(courseId: string, chapterId: string) {
  const [courses, setCourses] = useState<CourseItem[]>([])
  const [chapterTree, setChapterTree] = useState<ChapterNode[]>([])
  const [points, setPoints] = useState<PointItem[]>([])

  useEffect(() => {
    api.get('/api/education/courses')
      .then((res) => setCourses(res.data?.items || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!courseId) { setChapterTree([]); return }
    api.get(`/api/education/courses/${courseId}/chapters/tree`)
      .then((res) => setChapterTree(res.data?.tree || []))
      .catch(() => setChapterTree([]))
  }, [courseId])

  useEffect(() => {
    if (!chapterId) { setPoints([]); return }
    api.get(`/api/education/chapters/${chapterId}/knowledge-points`)
      .then((res) => setPoints(res.data?.items || []))
      .catch(() => setPoints([]))
  }, [chapterId])

  return { courses, chapterTree, points }
}

export function ChapterOptions({ chapterTree }: { chapterTree: ChapterNode[] }) {
  const flat: { id: string; title: string; depth: number }[] = []
  flattenChapters(chapterTree, 0, flat)
  return (
    <>
      {flat.map((n) => (
        <option key={n.id} value={n.id}>{'\u00A0\u00A0'.repeat(n.depth)}{n.title}</option>
      ))}
    </>
  )
}

export default function CategoryCascade({ value, onChange }: {
  value: CategoryValue
  onChange: (v: CategoryValue) => void
}) {
  const { courses, chapterTree, points } = useCategoryData(value.courseId, value.chapterId)

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <select value={value.courseId} onChange={(e) => onChange({ courseId: e.target.value, chapterId: '', pointId: '' })} style={selectStyle}>
        <option value="">全部课程</option>
        {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
      </select>
      <select
        value={value.chapterId}
        onChange={(e) => onChange({ ...value, chapterId: e.target.value, pointId: '' })}
        disabled={!value.courseId}
        style={{ ...selectStyle, cursor: value.courseId ? 'pointer' : 'default', color: value.courseId ? 'var(--text)' : 'var(--text-muted)' }}
      >
        <option value="">全部章节</option>
        <ChapterOptions chapterTree={chapterTree} />
      </select>
      <select
        value={value.pointId}
        onChange={(e) => onChange({ ...value, pointId: e.target.value })}
        disabled={!value.chapterId}
        style={{ ...selectStyle, cursor: value.chapterId ? 'pointer' : 'default', color: value.chapterId ? 'var(--text)' : 'var(--text-muted)' }}
      >
        <option value="">全部知识点</option>
        {points.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
      </select>
    </div>
  )
}

export function PointPicker({ onPick }: { onPick: (point: PointItem) => void }) {
  const [courseId, setCourseId] = useState('')
  const [chapterId, setChapterId] = useState('')
  const { courses, chapterTree, points } = useCategoryData(courseId, chapterId)

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <select value={courseId} onChange={(e) => { setCourseId(e.target.value); setChapterId('') }} style={smallSelectStyle}>
        <option value="">选择课程</option>
        {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
      </select>
      <select
        value={chapterId}
        onChange={(e) => setChapterId(e.target.value)}
        disabled={!courseId}
        style={{ ...smallSelectStyle, cursor: courseId ? 'pointer' : 'default', color: courseId ? 'var(--text)' : 'var(--text-muted)' }}
      >
        <option value="">选择章节</option>
        <ChapterOptions chapterTree={chapterTree} />
      </select>
      <select
        value=""
        onChange={(e) => {
          const p = points.find((x) => x.id === e.target.value)
          if (p) onPick(p)
        }}
        disabled={!chapterId}
        style={{ ...smallSelectStyle, cursor: chapterId ? 'pointer' : 'default', color: chapterId ? 'var(--text)' : 'var(--text-muted)' }}
      >
        <option value="">选择知识点</option>
        {points.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
      </select>
    </div>
  )
}
