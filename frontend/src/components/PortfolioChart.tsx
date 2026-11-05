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
import { CHART_RANGES, availableRanges, rangeStart } from '../chartRange'
import type { ChartRange } from '../chartRange'
import Toggle from './Toggle'
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
  // The time range the user picked, and how to change it.
  range: ChartRange
  onRangeChange: (range: ChartRange) => void
  // Called with the day under the pointer, and with null when it leaves the chart.
  onHoverDay: (day: PortfolioDay | null) => void
}

// One point on the chart. Numbers are only for drawing; the exact strings
// from the API are kept for the tooltip and table.
type ChartRow = {
  date: string
  value: number | null
  cost: number | null
  day: PortfolioDay
}

export default function PortfolioChart({
  history,
  currency,
  subject,
  range,
  onRangeChange,
  onHoverDay,
}: Props) {
  const [showTable, setShowTable] = useState(false)

  // Only offer ranges shorter than the history. If the saved range isn't one of
  // them (e.g. 1Y for a portfolio started last month), show everything.
  const offered = availableRanges(history.map((day) => day.date))
  const shownRange = offered.includes(range) ? range : 'all'
  const start = history.length > 0 ? rangeStart(shownRange, history[history.length - 1].date) : null
  const shown = start === null ? history : history.filter((day) => day.date >= start)

  const rows: ChartRow[] = shown.map((day) => ({
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
        <div className="chart-controls">
          {offered.length > 1 && (
            <Toggle
              label="Time range"
              options={CHART_RANGES.filter((option) => offered.includes(option.value))}
              value={shownRange}
              onChange={onRangeChange}
            />
          )}
          <button type="button" className="secondary" onClick={() => setShowTable(!showTable)}>
            {showTable ? 'Show chart' : 'Show table'}
          </button>
        </div>
      </div>

      {showTable ? (
        <HistoryTable history={shown} currency={currency} />
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
              <LineChart
                data={rows}
                margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
                // The headline figures above follow the pointer (activeLabel is the date).
                onMouseMove={(state) =>
                  onHoverDay(shown.find((day) => day.date === state.activeLabel) ?? null)
                }
                onMouseLeave={() => onHoverDay(null)}
              >
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
                  content={(props) => <ChartTooltip {...props} />}
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
  // Pad by 5% of the spread, so neither line runs along the top or bottom edge.
  // (Never below zero when the data isn't.)
  const smallest = Math.min(...known)
  const largest = Math.max(...known)
  const pad = (largest - smallest) * 0.05
  const low = smallest >= 0 ? Math.max(smallest - pad, 0) : smallest - pad
  const high = largest + pad

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

// Just the date: the headline figures above show that day's numbers.
function ChartTooltip({ active, payload }: TooltipContentProps) {
  if (!active || !payload || payload.length === 0) {
    return null
  }
  const day = (payload[0].payload as ChartRow).day

  return (
    <div className="chart-tooltip">
      <p className="tooltip-date">{formatDate(day.date)}</p>
      {/* The headline keeps showing the latest figures on these days. */}
      {day.value === null && <p className="tooltip-row">Value unknown (no price that day)</p>}
    </div>
  )
}

// The same data as the chart, readable without hovering. Newest first.
function HistoryTable({ history, currency }: { history: PortfolioDay[]; currency: Currency }) {
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
