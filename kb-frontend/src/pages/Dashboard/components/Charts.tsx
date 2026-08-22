import { type RankingItem, type TrendPoint } from '../model'

export function TokenTrendChart({ data }: { data: TrendPoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 400, color: 'var(--text-muted)', fontSize: 14 }}>
        暂无趋势数据
      </div>
    )
  }

  const W = 800, H = 420
  const pad = { left: 55, right: 60, top: 20, bottom: 55 }
  const chartW = W - pad.left - pad.right
  const chartH = H - pad.top - pad.bottom

  const tokenMax = Math.max(...data.map(d => d.tokens)) * 1.15
  const reqMax = Math.max(...data.map(d => d.requests)) * 1.15

  const xScale = (i: number) => pad.left + (i / (data.length - 1)) * chartW
  const yScaleToken = (v: number) => pad.top + chartH - (v / tokenMax) * chartH
  const yScaleReq = (v: number) => pad.top + chartH - (v / reqMax) * chartH

  // Build line paths
  const tokenPath = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(1)},${yScaleToken(d.tokens).toFixed(1)}`).join(' ')
  const reqPath = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(1)},${yScaleReq(d.requests).toFixed(1)}`).join(' ')

  // Area fill polygon
  const areaPath = [
    `M${xScale(0).toFixed(1)},${pad.top + chartH}`,
    ...data.map((d, i) => `L${xScale(i).toFixed(1)},${yScaleToken(d.tokens).toFixed(1)}`),
    `L${xScale(data.length - 1).toFixed(1)},${pad.top + chartH}Z`,
  ].join(' ')

  // Grid lines and Y axis ticks
  const yTicks = 5
  const tokenGrid = Array.from({ length: yTicks + 1 }, (_, i) => {
    const val = (tokenMax / yTicks) * i
    const y = yScaleToken(val)
    return { val, y }
  })
  const reqGrid = Array.from({ length: yTicks + 1 }, (_, i) => {
    const val = Math.round((reqMax / yTicks) * i)
    const y = yScaleReq(val)
    return { val, y }
  })

  // X axis labels (show every 5th)
  const xLabels = data.filter((_, i) => i % 5 === 0 || i === data.length - 1)

  function formatToken(v: number): string {
    if (v >= 1000) return (v / 1000).toFixed(0) + 'K'
    return v.toString()
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', minHeight: 400 }} preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="tokenArea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#263238" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#263238" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Grid lines (left Y axis) */}
      {tokenGrid.map((t, i) => (
        <line key={`gl-${i}`} x1={pad.left} y1={t.y} x2={pad.left + chartW} y2={t.y}
          stroke="#F1F3F4" strokeWidth="1" />
      ))}

      {/* Left Y axis labels */}
      {tokenGrid.map((t, i) => (
        <text key={`yl-${i}`} x={pad.left - 6} y={t.y + 4} textAnchor="end"
          fill="#9AA0A6" fontSize="11" fontFamily="var(--font)">
          {formatToken(t.val)}
        </text>
      ))}

      {/* Left Y axis name */}
      <text x={12} y={pad.top + chartH / 2} textAnchor="middle"
        fill="#9AA0A6" fontSize="11" fontFamily="var(--font)"
        transform={`rotate(-90, 12, ${pad.top + chartH / 2})`}>
        Token
      </text>

      {/* Right Y axis labels */}
      {reqGrid.map((t, i) => (
        <text key={`yr-${i}`} x={pad.left + chartW + 6} y={t.y + 4} textAnchor="start"
          fill="#9AA0A6" fontSize="11" fontFamily="var(--font)">
          {t.val}
        </text>
      ))}

      {/* Right Y axis name */}
      <text x={W - 12} y={pad.top + chartH / 2} textAnchor="middle"
        fill="#9AA0A6" fontSize="11" fontFamily="var(--font)"
        transform={`rotate(-90, ${W - 12}, ${pad.top + chartH / 2})`}>
        请求数
      </text>

      {/* X axis line */}
      <line x1={pad.left} y1={pad.top + chartH} x2={pad.left + chartW} y2={pad.top + chartH}
        stroke="#E8EAED" strokeWidth="1" />

      {/* X axis labels */}
      {xLabels.map((d, i) => {
        const idx = data.indexOf(d)
        return (
          <text key={`xl-${i}`} x={xScale(idx)} y={pad.top + chartH + 18} textAnchor="middle"
            fill="#9AA0A6" fontSize="11" fontFamily="var(--font)">
            {d.date}
          </text>
        )
      })}

      {/* Area fill */}
      <path d={areaPath} fill="url(#tokenArea)" />

      {/* Token line */}
      <path d={tokenPath} fill="none" stroke="#263238" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

      {/* Token dots */}
      {data.filter((_, i) => i % 5 === 0 || i === data.length - 1).map((d) => {
        const i = data.indexOf(d)
        return (
          <circle key={`td-${i}`} cx={xScale(i)} cy={yScaleToken(d.tokens)} r="4"
            fill="#263238" />
        )
      })}

      {/* Request line */}
      <path d={reqPath} fill="none" stroke="#4285F4" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

      {/* Request dots */}
      {data.filter((_, i) => i % 5 === 0 || i === data.length - 1).map((d) => {
        const i = data.indexOf(d)
        return (
          <circle key={`rd-${i}`} cx={xScale(i)} cy={yScaleReq(d.requests)} r="4"
            fill="#4285F4" />
        )
      })}

      {/* Legend */}
      <g transform={`translate(${(W - 160) / 2}, ${H - 8})`}>
        <line x1={0} y1={0} x2={16} y2={0} stroke="#263238" strokeWidth="2" />
        <circle cx={8} cy={0} r="3" fill="#263238" />
        <text x={22} y={4} fill="#5F6368" fontSize="12" fontFamily="var(--font)">Token 消耗</text>
        <line x1={90} y1={0} x2={106} y2={0} stroke="#4285F4" strokeWidth="2" />
        <circle cx={98} cy={0} r="3" fill="#4285F4" />
        <text x={112} y={4} fill="#5F6368" fontSize="12" fontFamily="var(--font)">请求数</text>
      </g>
    </svg>
  )
}

/** Horizontal bar chart for rankings */
export function RankingBarChart({ data, barColor }: { data: RankingItem[]; barColor: string }) {
  if (!data || data.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 320, color: 'var(--text-muted)', fontSize: 14 }}>
        暂无排行数据
      </div>
    )
  }

  const W = 550, H = 380
  const pad = { left: 150, right: 45, top: 10, bottom: 10 }
  const chartW = W - pad.left - pad.right
  const barH = 28
  const gap = 8
  const maxVal = Math.max(...data.map(d => d.count))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', minHeight: 320 }} preserveAspectRatio="xMidYMid meet">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
        const x = pad.left + chartW * pct
        return (
          <line key={`gl-${i}`} x1={x} y1={pad.top} x2={x} y2={H - pad.bottom}
            stroke="#F1F3F4" strokeWidth="1" />
        )
      })}

      {/* Bars */}
      {data.map((item, i) => {
        const y = pad.top + i * (barH + gap)
        const barW = Math.max((item.count / maxVal) * chartW, 4)
        return (
          <g key={`bar-${i}`}>
            {/* Category label */}
            <text x={pad.left - 8} y={y + barH / 2 + 4} textAnchor="end"
              fill="#1A1A1A" fontSize="12" fontFamily="var(--font)">
              {item.name.length > 14 ? item.name.slice(0, 14) + '...' : item.name}
            </text>
            {/* Bar with rounded right corners */}
            <rect x={pad.left} y={y} width={barW} height={barH} rx="4" ry="4"
              fill={barColor} />
            {/* Value label */}
            <text x={pad.left + barW + 6} y={y + barH / 2 + 4} textAnchor="start"
              fill="#5F6368" fontSize="11" fontFamily="var(--font)">
              {item.count}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

// ==================== Main Component ====================

