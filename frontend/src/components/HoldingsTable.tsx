import type { Currency, Holding } from '../api'
import MetalName from './MetalName'
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
    <>
      <AllocationBar holdings={holdings} />
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Metal</th>
              <th className="number">Troy ounces</th>
              <th className="number">Value</th>
              <th className="number">Cost</th>
              <th className="number">Gain / loss</th>
              <th className="number">Share of value</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((holding) => (
              <tr key={holding.metal}>
                <td>
                  <MetalName metal={holding.metal} />
                </td>
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
                <td className="number">{formatShare(holding.share_percent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function formatShare(percent: string | null): string {
  return percent === null ? '—' : `${Number(percent).toFixed(1)}%`
}

// One bar split into a block per metal, sized by its share of the portfolio's value.
// The table below carries the exact figures (and the metal names, as the legend).
function AllocationBar({ holdings }: { holdings: Holding[] }) {
  const parts = holdings.filter((holding) => Number(holding.share_percent ?? 0) > 0)
  if (parts.length < 2) {
    return null // one metal is 100%; a bar wouldn't say anything
  }
  const description = parts
    .map((holding) => `${METAL_LABELS[holding.metal]} ${formatShare(holding.share_percent)}`)
    .join(', ')

  return (
    <div className="allocation-bar" role="img" aria-label={`Share of value: ${description}`}>
      {parts.map((holding) => (
        <span
          key={holding.metal}
          className={`allocation-part ${holding.metal}`}
          style={{ flexGrow: Number(holding.share_percent) }}
          title={`${METAL_LABELS[holding.metal]}: ${formatShare(holding.share_percent)}`}
        />
      ))}
    </div>
  )
}
