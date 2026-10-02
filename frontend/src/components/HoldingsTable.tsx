import type { Currency, Holding } from '../api'
import {
  METAL_LABELS,
  formatMoney,
  formatOunces,
  formatSignedMoney,
  formatSignedPercent,
} from '../format'

type Props = {
  holdings: Holding[]
  currency: Currency
}

// Today's position in each metal: weight, value, cost, gain and share of the portfolio.
export default function HoldingsTable({ holdings, currency }: Props) {
  if (holdings.length === 0) {
    return null
  }

  const money = (amount: string | null) => (amount === null ? '—' : formatMoney(amount, currency))

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Metal</th>
            <th className="number">Troy ounces</th>
            <th className="number">Value</th>
            <th className="number">Cost</th>
            <th className="number">Gain / loss</th>
            <th>Share of value</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => (
            <tr key={holding.metal}>
              <td>{METAL_LABELS[holding.metal]}</td>
              <td className="number">{formatOunces(holding.weight_oz)}</td>
              <td className="number">{money(holding.value)}</td>
              <td className="number">{money(holding.cost)}</td>
              <td className="number">
                {holding.gain === null ? (
                  '—'
                ) : (
                  <>
                    {formatSignedMoney(holding.gain, currency)}
                    {holding.gain_percent !== null && (
                      <span className="muted"> ({formatSignedPercent(holding.gain_percent)})</span>
                    )}
                  </>
                )}
              </td>
              <td>
                {holding.share_percent === null ? (
                  '—'
                ) : (
                  <div className="share">
                    <span className="share-value">{Number(holding.share_percent).toFixed(1)}%</span>
                    <span className="share-track" aria-hidden="true">
                      <span
                        className="share-fill"
                        style={{ width: `${Number(holding.share_percent)}%` }}
                      />
                    </span>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
