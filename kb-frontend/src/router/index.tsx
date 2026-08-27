import { lazy, Suspense, useEffect, useState, Component, ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import Layout from '../components/Layout'
const Login = lazy(() => import('../pages/Login'))
const SearchQA = lazy(() => import('../pages/SearchQA'))
const Quiz = lazy(() => import('../pages/Quiz'))
const KnowledgeManage = lazy(() => import('../pages/KnowledgeManage'))
const GapAnalysis = lazy(() => import('../pages/GapAnalysis'))
const Dashboard = lazy(() => import('../pages/Dashboard'))
const QuizBank = lazy(() => import('../pages/QuizBank'))
const PointReview = lazy(() => import('../pages/PointReview'))
const QuizBrowse = lazy(() => import('../pages/QuizBrowse'))
const SystemAdmin = lazy(() => import('../pages/SystemAdmin'))
const Settings = lazy(() => import('../pages/Settings'))

function PageFallback() {
  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 13 }}>
      页面加载中…
    </div>
  )
}

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  componentDidCatch(error: Error, info: any) {
    console.error('Page Error:', error.message, error.stack, info)
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 48, textAlign: 'center', fontFamily: 'sans-serif' }}>
          <h1 style={{ color: '#EA4335', fontSize: 20, marginBottom: 12 }}>页面渲染错误</h1>
          <pre style={{ background: '#FFF3F0', padding: 16, borderRadius: 8, fontSize: 13, color: '#333', textAlign: 'left', maxWidth: 600, margin: '0 auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{this.state.error.message}</pre>
          <button onClick={() => this.setState({ error: null })} style={{ marginTop: 16, padding: '8px 20px', background: '#263238', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 14 }}>重试</button>
        </div>
      )
    }
    return this.props.children
  }
}

function ProtectedRoute({ children, title }: { children: React.ReactNode; title: string }) {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Layout title={title}>{children}</Layout>
}

export default function AppRouter() {
  const { restoreSession, isAuthenticated } = useAuthStore()
  const [ready, setReady] = useState(false)

  useEffect(() => {
    restoreSession()
    setReady(true)
  }, [])

  if (!ready) {
    return null
  }

  return (
    <ErrorBoundary>
    <Suspense fallback={<PageFallback />}>
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/qa" replace /> : <Login />} />
      <Route path="/" element={<Navigate to={isAuthenticated ? "/qa" : "/login"} replace />} />
      <Route path="/qa" element={<ProtectedRoute title="智能问答"><SearchQA /></ProtectedRoute>} />
      <Route path="/quiz" element={<ProtectedRoute title="智能出题"><Quiz /></ProtectedRoute>} />
      <Route path="/knowledge" element={<ProtectedRoute title="知识管理"><KnowledgeManage /></ProtectedRoute>} />
      <Route path="/gaps" element={<ProtectedRoute title="缺口分析"><GapAnalysis /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute title="数据看板"><Dashboard /></ProtectedRoute>} />
      <Route path="/quiz-bank" element={<ProtectedRoute title="题库管理"><QuizBank /></ProtectedRoute>} />
      <Route path="/points-review" element={<ProtectedRoute title="知识点管理"><PointReview /></ProtectedRoute>} />
      <Route path="/quiz-browse" element={<ProtectedRoute title="题库浏览"><QuizBrowse /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute title="系统管理"><SystemAdmin /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute title="账号设置"><Settings /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/qa" replace />} />
    </Routes>
    </Suspense>
    </ErrorBoundary>
  )
}
