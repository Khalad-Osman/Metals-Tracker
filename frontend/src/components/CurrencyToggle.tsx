import type { Currency } from '../api'

type Props = {
  value: Currency
  onChange: (currency: Currency) => void
}

const CURRENCIES: Currency[] = ['CAD', 'USD']

// Two side-by-side buttons for choosing the display currency.
export default function CurrencyToggle({ value, onChange }: Props) {
  return (
    <div className="toggle" role="group" aria-label="Display currency">
      {CURRENCIES.map((currency) => (
        <button
          key={currency}
          type="button"
          aria-pressed={currency === value}
          onClick={() => onChange(currency)}
        >
          {currency}
        </button>
      ))}
    </div>
  )
}
