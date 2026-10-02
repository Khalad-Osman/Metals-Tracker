import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TooltipContentProps } from 'recharts'
import type { Currency, PortfolioDay } from '../api'
import {
  formatAxisMoney,
  formatDate,
  formatMoney,
  formatShortDate,
  formatSignedMoney,
  formatSignedPercent,
} from '../format'

type Props = {
  history: PortfolioDay[]
  currency: Currency
  // What the chart shows, e.g. "Portfolio" or "Gold".
  subject: string
}

// One point on the chart. Numbers are only for drawing; the exact strings
// from the API are kept for the tooltip and table.
type ChartRow = {
  date: string
  value: number | null
  cost: number | null
  day: PortfolioDay
}

export default function PortfolioChart({ history, currency, subject }: Props) {
  const [showTable, setShowTable] = useState(false)

  const rows: ChartRow[] = history.map((day) => ({
    date: day.date,
    value: day.value === null ? null : Number(day.value),
    cost: day.cost === null ? null : Number(day.cost),
    day,
  }))
  const ticks = roundTicks(rows.flatMap((row) => [row.value, row.cost]))

  return (
    <figure className="chart">
      <div className="chart-header">
        <figcaption>
          <span className="chart-title">{subject} value over time</span>
          <span className="chart-subtitle">
            Daily value at spot price, compared with what you paid ({currency})
          </span>
        </figcaption>
        <button type="button" className="secondary" onClick={() => setShowTable(!showTable)}>
          {showTable ? 'Show chart' : 'Show table'}
        </button>
      </div>

      {showTable ? (
        <HistoryTable history={history} currency={currency} />
      ) : (
        <>
          <ul className="legend">
            <li>
              <span className="legend-key value" aria-hidden="true" /> Market value
            </li>
            <li>
              <span className="legend-key cost" aria-hidden="true" /> Cost
            </li>
          </ul>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
                <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatShortDate}
                  stroke="var(--chart-axis)"
                  tick={{ fill: 'var(--chart-muted)', fontSize: 12 }}
                  tickLine={false}
                  minTickGap={32}
                />
                <YAxis
                  domain={[ticks[0], ticks[ticks.length - 1]]}
                  ticks={ticks}
                  tickFormatter={(amount: number) => formatAxisMoney(amount, currency)}
                  stroke="var(--chart-axis)"
                  tick={{ fill: 'var(--chart-muted)', fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  width={72}
                />
                <Tooltip
                  cursor={{ stroke: 'var(--chart-axis)', strokeWidth: 1 }}
                  content={(props) => <ChartTooltip {...props} currency={currency} />}
                />
                {/* Cost only changes on purchase days, so it's drawn as steps. */}
                <Line
                  dataKey="cost"
                  name="Cost"
                  type="stepAfter"
                  stroke="var(--chart-cost)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
                {/* Gaps (not drops to zero) where a value couldn't be worked out. */}
                <Line
                  dataKey="value"
                  name="Market value"
                  type="linear"
                  stroke="var(--chart-value)"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  dot={false}
                  activeDot={{ r: 5, fill: 'var(--chart-value)', stroke: 'var(--surface)', strokeWidth: 2 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </figure>
  )
}

// Evenly spaced, round axis values (e.g. 1,800 / 1,900 / 2,000) that cover all the data.
function roundTicks(amounts: (number | null)[]): number[] {
  const known = amounts.filter((amount): amount is number => amount !== null)
  if (known.length === 0) {
    return [0, 1]
  }
  const low = Math.min(...known)
  const high = Math.max(...known)

  // Aim for about 4 steps, using a step size of 1, 2, 2.5 or 5 times a power of ten.
  const roughStep = Math.max(high - low, 1) / 4
  const power = 10 ** Math.floor(Math.log10(roughStep))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= roughStep) ?? 10 * power

  const first = Math.floor(low / step)
  // At least one step, so a portfolio whose value never changed still gets an axis.
  const last = Math.max(Math.ceil(high / step), first + 1)
  const ticks = []
  for (let i = first; i <= last; i++) {
    ticks.push(i * step)
  }
  return ticks
}

function ChartTooltip({
  active,
  payload,
  currency,
}: TooltipContentProps & { currency: Currency }) {
  if (!active || !payload || payload.length === 0) {
    return null
  }
  const day = (payload[0].payload as ChartRow).day

  return (
    <div className="chart-tooltip">
      <p className="tooltip-date">{formatDate(day.date)}</p>
      <TooltipRow keyClass="value" label="Market value" amount={day.value} currency={currency} />
      <TooltipRow keyClass="cost" label="Cost" amount={day.cost} currency={currency} />
      {day.gain !== null && (
        <p className="tooltip-row">
          <strong>
            {formatSignedMoney(day.gain, currency)}
            {day.gain_percent !== null && ` (${formatSignedPercent(day.gain_percent)})`}
          </strong>{' '}
          <span>gain / loss</span>
        </p>
      )}
    </div>
  )
}

function TooltipRow({
  keyClass,
  label,
  amount,
  currency,
}: {
  keyClass: string
  label: string
  amount: string | null
  currency: Currency
}) {
  return (
    <p className="tooltip-row">
      <span className={`legend-key ${keyClass}`} aria-hidden="true" />
      <strong>{amount === null ? 'unknown' : formatMoney(amount, currency)}</strong>{' '}
      <span>{label}</span>
    </p>
  )
}

// The same data as the chart, readable without hovering. Newest first.
function HistoryTable({ history, currency }: Omit<Props, 'subject'>) {
  const show = (amount: string | null) => (amount === null ? '—' : formatMoney(amount, currency))

  return (
    <div className="table-wrapper history-table">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th className="number">Market value</th>
            <th className="number">Cost</th>
            <th className="number">Gain / loss</th>
            <th className="number">%</th>
          </tr>
        </thead>
        <tbody>
          {[...history].reverse().map((day) => (
            <tr key={day.date}>
              <td>{formatDate(day.date)}</td>
              <td className="number">{show(day.value)}</td>
              <td className="number">{show(day.cost)}</td>
              <td className="number">
                {day.gain === null ? '—' : formatSignedMoney(day.gain, currency)}
              </td>
              <td className="number">
                {day.gain_percent === null ? '—' : formatSignedPercent(day.gain_percent)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
