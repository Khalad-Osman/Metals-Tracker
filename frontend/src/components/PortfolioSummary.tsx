import type { Currency, PortfolioDay } from '../api'
import { formatDate, formatMoney, formatSignedMoney, formatSignedPercent } from '../format'

type Props = {
  history: PortfolioDay[]
  currency: Currency
}

// Headline figures for the most recent day that has a known value.
export default function PortfolioSummary({ history, currency }: Props) {
  const latest = history.findLast((day) => day.value !== null)
  if (!latest || latest.value === null || latest.cost === null || latest.gain === null) {
    return null
  }

  const gain = Number(latest.gain)
  // Direction is shown by the sign and the arrow, not only by color.
  const direction = gain > 0 ? 'up' : gain < 0 ? 'down' : 'flat'
  const arrow = gain > 0 ? '▲' : gain < 0 ? '▼' : ''

  return (
    <div className="summary">
      <div className="stat">
        <p className="stat-label">Market value</p>
        <p className="stat-value hero">{formatMoney(latest.value, currency)}</p>
        <p className="stat-note">at spot price on {formatDate(latest.date)}</p>
      </div>

      <div className="stat">
        <p className="stat-label">Total cost</p>
        <p className="stat-value">{formatMoney(latest.cost, currency)}</p>
        <p className="stat-note">what you paid</p>
      </div>

      <div className="stat">
        <p className="stat-label">Gain / loss</p>
        <p className="stat-value">{formatSignedMoney(latest.gain, currency)}</p>
        {latest.gain_percent !== null && (
          <p className={`stat-delta ${direction}`}>
            <span aria-hidden="true">{arrow}</span> {formatSignedPercent(latest.gain_percent)}
          </p>
        )}
      </div>
    </div>
  )
}
