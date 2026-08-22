import React from 'react';
import { styles } from './styles';

export const SyncIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
  </svg>
);

export const EmptyCheckIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="10" />
    <path d="M8 12l3 3 5-5" />
  </svg>
);

export const EmptyDashIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="10" />
    <line x1="8" y1="12" x2="16" y2="12" />
  </svg>
);

// ──────────────── Toast Hook ────────────────
export interface ToastState {
  message: string;
  type: 'success' | 'error';
  visible: boolean;
}

// ──────────────── Pagination Component ────────────────
interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  onPageChange: (page: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({ page, totalPages, total, onPageChange }) => {
  if (totalPages <= 1) return null;

  const getPageNumbers = (): (number | 'ellipsis')[] => {
    const pages: (number | 'ellipsis')[] = [];
    const sp = Math.max(1, Math.min(page - 2, totalPages - 4));
    const ep = Math.min(totalPages, Math.max(page + 2, 5));

    if (sp > 1) {
      pages.push(1);
      if (sp > 2) pages.push('ellipsis');
    }
    for (let i = sp; i <= ep; i++) pages.push(i);
    if (ep < totalPages) {
      if (ep < totalPages - 1) pages.push('ellipsis');
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div style={styles.pagination}>
      <div style={styles.paginationInfo}>第 {page}/{totalPages} 页，共 {total} 条</div>
      <div style={styles.paginationBtns}>
        <button
          style={styles.paginationBtn()}
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
        >
          «
        </button>
        {getPageNumbers().map((p, i) =>
          p === 'ellipsis' ? (
            <span key={`e-${i}`} style={styles.paginationEllipsis}>…</span>
          ) : (
            <button
              key={p}
              style={styles.paginationBtn(p === page)}
              disabled={p === page}
              onClick={() => onPageChange(p)}
            >
              {p}
            </button>
          ),
        )}
        <button
          style={styles.paginationBtn()}
          disabled={page === totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          »
        </button>
      </div>
    </div>
  );
};

// ──────────────── FAQManage Component ────────────────
