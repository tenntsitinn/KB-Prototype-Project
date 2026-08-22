import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../../services/api';
import { useAuthStore } from '../../stores/authStore';
import { type FaqPublished, type FaqRecommendation, type PaginationMeta } from './model';
import { EmptyCheckIcon, EmptyDashIcon, Pagination, SyncIcon, type ToastState } from './components';
import { styles } from './styles';

const FAQManage: React.FC = () => {
  const { user } = useAuthStore();

  // Tab state
  const [activeTab, setActiveTab] = useState<'recommendations' | 'published'>('recommendations');

  // Recommendations state
  const [recs, setRecs] = useState<FaqRecommendation[]>([]);
  const [recPagination, setRecPagination] = useState<PaginationMeta>({ page: 1, page_size: 10, total: 0, total_pages: 0 });
  const [recLoading, setRecLoading] = useState(false);
  const [recError, setRecError] = useState<string | null>(null);

  // Published state
  const [pubs, setPubs] = useState<FaqPublished[]>([]);
  const [pubPagination, setPubPagination] = useState<PaginationMeta>({ page: 1, page_size: 10, total: 0, total_pages: 0 });
  const [pubLoading, setPubLoading] = useState(false);
  const [pubError, setPubError] = useState<string | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState('');

  // Toast
  const [toast, setToast] = useState<ToastState>({ message: '', type: 'success', visible: false });
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((message: string, type: 'success' | 'error') => {
    setToast({ message, type, visible: true });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => {
      setToast((prev) => ({ ...prev, visible: false }));
    }, 2500);
  }, []);

  // Review modal
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewItem, setReviewItem] = useState<FaqRecommendation | null>(null);
  const [reviewAnswer, setReviewAnswer] = useState('');

  // Edit modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<FaqPublished | null>(null);
  const [editQuestion, setEditQuestion] = useState('');
  const [editAnswer, setEditAnswer] = useState('');

  // Fetch recommendations
  const fetchRecommendations = useCallback(async (page: number = 1) => {
    setRecLoading(true);
    setRecError(null);
    try {
      const params: Record<string, string | number> = { offset: (page - 1) * 10, limit: 10 };
      const res = await api.get('/api/settlement/faqs/recommendations', { params });
      const data = res.data;
      setRecs(data.items ?? []);
      setRecPagination({
        page,
        page_size: 10,
        total: data.total ?? 0,
        total_pages: Math.ceil((data.total ?? 0) / 10),
      });
    } catch {
      setRecError('加载推荐列表失败');
      showToast('加载推荐列表失败', 'error');
    } finally {
      setRecLoading(false);
    }
  }, [showToast]);

  // Fetch published
  const fetchPublished = useCallback(async (page: number = 1) => {
    setPubLoading(true);
    setPubError(null);
    try {
      const params: Record<string, string | number> = { offset: (page - 1) * 10, limit: 10 };
      const res = await api.get('/api/settlement/faqs', { params });
      const data = res.data;
      setPubs(data.items ?? []);
      setPubPagination({
        page,
        page_size: 10,
        total: data.total ?? 0,
        total_pages: Math.ceil((data.total ?? 0) / 10),
      });
    } catch {
      setPubError('加载已发布列表失败');
      showToast('加载已发布列表失败', 'error');
    } finally {
      setPubLoading(false);
    }
  }, [showToast]);

  // Initial load and tab/refresh
  useEffect(() => {
    if (activeTab === 'recommendations') {
      fetchRecommendations(recPagination.page);
    } else {
      fetchPublished(pubPagination.page);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // Search debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      if (activeTab === 'recommendations') {
        fetchRecommendations(1);
      } else {
        fetchPublished(1);
      }
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery]);

  // Tab switch
  const handleTabChange = (tab: 'recommendations' | 'published') => {
    setActiveTab(tab);
    setSearchQuery('');
  };

  // Open review modal
  const openReviewModal = (item: FaqRecommendation) => {
    setReviewItem(item);
    setReviewAnswer(item.answer);
    setReviewModalOpen(true);
  };

  // Approve
  const handleApprove = async () => {
    if (!reviewItem) return;
    const answer = reviewAnswer.trim();
    if (!answer) {
      showToast('请填写答案', 'error');
      return;
    }
    try {
      await api.post(`/api/settlement/faqs/${reviewItem.id}/review`, { action: 'approve', edited_answer: answer });
      setReviewModalOpen(false);
      setReviewItem(null);
      fetchRecommendations(recPagination.page);
      fetchPublished(pubPagination.page);
      showToast('已通过并发布到缓存', 'success');
    } catch {
      showToast('审核通过失败', 'error');
    }
  };

  // Reject (from modal)
  const handleRejectFromModal = async () => {
    if (!reviewItem) return;
    try {
      await api.post(`/api/settlement/faqs/${reviewItem.id}/review`, { action: 'reject' });
      setReviewModalOpen(false);
      setReviewItem(null);
      fetchRecommendations(recPagination.page);
      showToast('已驳回', 'success');
    } catch {
      showToast('驳回失败', 'error');
    }
  };

  // Quick reject
  const handleQuickReject = async (item: FaqRecommendation) => {
    if (!window.confirm('确定驳回该 FAQ 推荐吗？')) return;
    try {
      await api.post(`/api/settlement/faqs/${item.id}/review`, { action: 'reject' });
      fetchRecommendations(recPagination.page);
      showToast('已驳回', 'success');
    } catch {
      showToast('驳回失败', 'error');
    }
  };

  // Delete published
  const handleDelete = async (item: FaqPublished) => {
    if (!window.confirm('确定删除该 FAQ 并清理缓存吗？')) return;
    try {
      await api.delete(`/api/settlement/faqs/${item.id}`);
      fetchPublished(pubPagination.page);
      showToast('已删除并清理缓存', 'success');
    } catch {
      showToast('删除失败', 'error');
    }
  };

  // Sync cache
  const handleSyncCache = async () => {
    const inactiveCount = pubs.filter((f) => !f.cache_active).length;
    if (inactiveCount === 0) {
      showToast('所有 FAQ 缓存已生效', 'success');
      return;
    }
    try {
      await api.post('/api/settlement/faqs/sync-cache');
      fetchPublished(pubPagination.page);
      showToast(`已同步 ${inactiveCount} 条到缓存`, 'success');
    } catch {
      showToast('同步缓存失败', 'error');
    }
  };

  // Open edit modal
  const openEditModal = (item: FaqPublished) => {
    setEditItem(item);
    setEditQuestion(item.question);
    setEditAnswer(item.answer);
    setEditModalOpen(true);
  };

  // Save edit
  const handleSaveEdit = async () => {
    if (!editItem) return;
    const q = editQuestion.trim();
    const a = editAnswer.trim();
    if (!q) {
      showToast('请填写问题', 'error');
      return;
    }
    if (!a) {
      showToast('请填写答案', 'error');
      return;
    }
    try {
      await api.put(`/api/settlement/faqs/${editItem.id}`, { question: q, answer: a });
      setEditModalOpen(false);
      setEditItem(null);
      fetchPublished(pubPagination.page);
      showToast('FAQ 已更新', 'success');
    } catch {
      showToast('更新失败', 'error');
    }
  };

  // Page change
  const handleRecPageChange = (page: number) => {
    fetchRecommendations(page);
  };

  const handlePubPageChange = (page: number) => {
    fetchPublished(page);
  };

  // Render table header cell
  const renderTh = (text: string, isFirst: boolean, isLast: boolean) => (
    <th key={text} style={isFirst ? styles.theadThFirst : isLast ? styles.theadThLast : styles.theadTh}>
      {text}
    </th>
  );

  // Render table body cell
  const renderTd = (content: React.ReactNode, isFirst: boolean, isLast: boolean, key?: string) => (
    <td key={key} style={isFirst ? styles.tbodyTdFirst : isLast ? styles.tbodyTdLast : styles.tbodyTd}>
      {content}
    </td>
  );

  return (
    <>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerActions}>
          <input
            type="text"
            placeholder="搜索问题或答案..."
            style={styles.searchInput}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = 'var(--primary)'; }}
            onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = 'var(--border)'; }}
          />
          <button style={styles.btnGhost} onClick={handleSyncCache}>
            <SyncIcon />
            同步缓存
          </button>
        </div>
      </div>

      {/* Content */}
      <div style={styles.content}>
        {/* Tabs */}
        <div style={styles.tabs}>
          <button
            style={styles.tabBtn(activeTab === 'recommendations')}
            onClick={() => handleTabChange('recommendations')}
          >
            待审核推荐
            <span style={styles.tabCount(activeTab === 'recommendations')}>{recPagination.total}</span>
          </button>
          <button
            style={styles.tabBtn(activeTab === 'published')}
            onClick={() => handleTabChange('published')}
          >
            已发布 FAQ
            <span style={styles.tabCount(activeTab === 'published')}>{pubPagination.total}</span>
          </button>
        </div>

        {/* Recommendations Panel */}
        {activeTab === 'recommendations' && (
          <div style={styles.tableCard}>
            <div style={styles.tableWrapper}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {['问题', '建议答案', '关联知识单元', '推荐频次', '来源', '操作'].map((h, i) =>
                      renderTh(h, i === 0, i === 5),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {recLoading ? (
                    <tr>
                      <td colSpan={6}>
                        <div style={styles.loadingState}>
                          <p>加载中...</p>
                        </div>
                      </td>
                    </tr>
                  ) : recError ? (
                    <tr>
                      <td colSpan={6}>
                        <div style={styles.errorState}>
                          <p>{recError}</p>
                          <button style={styles.errorRetryBtn} onClick={() => fetchRecommendations(recPagination.page)}>
                            重试
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : recs.length === 0 ? (
                    <tr>
                      <td colSpan={6}>
                        <div style={styles.emptyState}>
                          <EmptyCheckIcon />
                          <p style={styles.emptyStateText}>所有推荐已处理完毕</p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    recs.map((item) => (
                      <tr key={item.id}>
                        {renderTd(
                          <span style={styles.cellText} title={item.question}>{item.question}</span>,
                          true,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.cellText} title={item.answer}>
                            {item.answer.length > 50 ? item.answer.substring(0, 50) + '…' : item.answer}
                          </span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.relatedUnitLink}>{item.related_unit_title}</span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.cellMeta}>{item.hit_count} 次</span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.sourceTag(item.source_type)}>
                            {item.source_type === 'auto_mined' ? '自动挖掘' : '手动'}
                          </span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <div style={styles.actionsCell}>
                            <button style={styles.btnOutlineXs} onClick={() => openReviewModal(item)}>
                              审核
                            </button>
                            <button style={styles.btnDangerXs} onClick={() => handleQuickReject(item)}>
                              快速驳回
                            </button>
                          </div>,
                          false,
                          true,
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <Pagination
              page={recPagination.page}
              totalPages={recPagination.total_pages}
              total={recPagination.total}
              onPageChange={handleRecPageChange}
            />
          </div>
        )}

        {/* Published Panel */}
        {activeTab === 'published' && (
          <div style={styles.tableCard}>
            <div style={styles.tableWrapper}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    {['问题', '答案', '来源', '命中次数', '缓存', '操作'].map((h, i) =>
                      renderTh(h, i === 0, i === 5),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {pubLoading ? (
                    <tr>
                      <td colSpan={6}>
                        <div style={styles.loadingState}>
                          <p>加载中...</p>
                        </div>
                      </td>
                    </tr>
                  ) : pubError ? (
                    <tr>
                      <td colSpan={6}>
                        <div style={styles.errorState}>
                          <p>{pubError}</p>
                          <button style={styles.errorRetryBtn} onClick={() => fetchPublished(pubPagination.page)}>
                            重试
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : pubs.length === 0 ? (
                    <tr>
                      <td colSpan={6}>
                        <div style={styles.emptyState}>
                          <EmptyDashIcon />
                          <p style={styles.emptyStateText}>暂无已发布 FAQ</p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    pubs.map((item) => (
                      <tr key={item.id}>
                        {renderTd(
                          <span style={styles.cellText} title={item.question}>{item.question}</span>,
                          true,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.cellText} title={item.answer}>
                            {item.answer.length > 50 ? item.answer.substring(0, 50) + '…' : item.answer}
                          </span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.sourceTag(item.source_type)}>
                            {item.source_type === 'auto_mined' ? '自动挖掘' : '手动'}
                          </span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.cellMeta}>{item.hit_count}</span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <span style={styles.cacheTag(item.cache_active)}>
                            {item.cache_active ? '● 已生效' : '○ 未生效'}
                          </span>,
                          false,
                          false,
                        )}
                        {renderTd(
                          <div style={styles.actionsCell}>
                            <button style={styles.btnEditXs} onClick={() => openEditModal(item)}>
                              编辑
                            </button>
                            <button style={styles.btnDangerXs} onClick={() => handleDelete(item)}>
                              删除
                            </button>
                          </div>,
                          false,
                          true,
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <Pagination
              page={pubPagination.page}
              totalPages={pubPagination.total_pages}
              total={pubPagination.total}
              onPageChange={handlePubPageChange}
            />
          </div>
        )}
      </div>

      {/* Review Modal */}
      {reviewModalOpen && (
        <div style={styles.modalOverlay} onClick={() => setReviewModalOpen(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h3 style={styles.modalHeaderH3}>审核 FAQ</h3>
              <button style={styles.modalClose} onClick={() => setReviewModalOpen(false)}>
                &times;
              </button>
            </div>
            <div style={styles.modalBody}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>问题</label>
                <div style={styles.formReadonly}>{reviewItem?.question}</div>
              </div>
              <div style={{ ...styles.formGroup, marginBottom: 0 }}>
                <label style={styles.formLabel}>答案</label>
                <textarea
                  style={styles.formTextarea}
                  value={reviewAnswer}
                  onChange={(e) => setReviewAnswer(e.target.value)}
                  rows={6}
                  onFocus={(e) => {
                    e.target.style.borderColor = 'var(--primary)';
                    e.target.style.boxShadow = '0 0 0 3px var(--primary-light)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'var(--border)';
                    e.target.style.boxShadow = 'none';
                  }}
                />
              </div>
            </div>
            <div style={styles.modalFooter}>
              <button style={styles.btnDanger} onClick={handleRejectFromModal}>
                驳回
              </button>
              <button style={styles.btnSuccess} onClick={handleApprove}>
                通过并发布
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editModalOpen && (
        <div style={styles.modalOverlay} onClick={() => setEditModalOpen(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h3 style={styles.modalHeaderH3}>编辑 FAQ</h3>
              <button style={styles.modalClose} onClick={() => setEditModalOpen(false)}>
                &times;
              </button>
            </div>
            <div style={styles.modalBody}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>问题</label>
                <input
                  style={styles.formInput}
                  value={editQuestion}
                  onChange={(e) => setEditQuestion(e.target.value)}
                  onFocus={(e) => {
                    e.target.style.borderColor = 'var(--primary)';
                    e.target.style.boxShadow = '0 0 0 3px var(--primary-light)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'var(--border)';
                    e.target.style.boxShadow = 'none';
                  }}
                />
              </div>
              <div style={{ ...styles.formGroup, marginBottom: 0 }}>
                <label style={styles.formLabel}>答案</label>
                <textarea
                  style={styles.formTextarea}
                  value={editAnswer}
                  onChange={(e) => setEditAnswer(e.target.value)}
                  rows={6}
                  onFocus={(e) => {
                    e.target.style.borderColor = 'var(--primary)';
                    e.target.style.boxShadow = '0 0 0 3px var(--primary-light)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'var(--border)';
                    e.target.style.boxShadow = 'none';
                  }}
                />
              </div>
            </div>
            <div style={styles.modalFooter}>
              <button style={styles.btnDanger} onClick={() => setEditModalOpen(false)}>
                取消
              </button>
              <button style={styles.btnSuccess} onClick={handleSaveEdit}>
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast.visible && (
        <div style={styles.toast(toast.type)}>{toast.message}</div>
      )}
    </>
  );
};

export default FAQManage;
