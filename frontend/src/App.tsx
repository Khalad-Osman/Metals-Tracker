import { useEffect, useState } from 'react'
import { deletePurchase, getHoldings, getPortfolioHistory, listPurchases } from './api'
import type { Currency, Holding, PortfolioDay, Purchase } from './api'
import { METAL_LABELS, UNIT_LABELS, formatDate } from './format'
import CurrencyToggle from './components/CurrencyToggle'
import HoldingsTable from './components/HoldingsTable'
import PortfolioChart from './components/PortfolioChart'
import PortfolioSummary from './components/PortfolioSummary'
import PurchaseForm from './components/PurchaseForm'
import PurchaseTable from './components/PurchaseTable'

const CURRENCY_STORAGE_KEY = 'displayCurrency'

// The currency chosen last time, remembered in this browser. Defaults to CAD.
function savedCurrency(): Currency {
  try {
    return localStorage.getItem(CURRENCY_STORAGE_KEY) === 'USD' ? 'USD' : 'CAD'
  } catch {
    return 'CAD' // storage can be unavailable, e.g. in some private windows
  }
}

function App() {
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // The purchase being edited in the form, if any.
  const [editing, setEditing] = useState<Purchase | undefined>()
  // The currency the user picked, and the currency the loaded portfolio is in.
  // They differ briefly while new data loads, so the old numbers keep the right label.
  const [currency, setCurrency] = useState<Currency>(savedCurrency)
  const [portfolioCurrency, setPortfolioCurrency] = useState<Currency>(currency)
  const [portfolio, setPortfolio] = useState<PortfolioDay[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [portfolioError, setPortfolioError] = useState<string | null>(null)
  // True while the portfolio is reloading; the old chart stays visible but faded.
  const [portfolioRefreshing, setPortfolioRefreshing] = useState(true)
  // Bumping this number makes the effects below fetch the data again.
  const [reloadCount, setReloadCount] = useState(0)

  // Load the purchase history when the page opens, and again after each change.
  useEffect(() => {
    listPurchases()
      .then((data) => {
        setPurchases(data)
        setError(null)
      })
      .catch(() => {
        setError('Could not load purchases. Is the backend running on http://localhost:8000?')
      })
      .finally(() => setLoading(false))
  }, [reloadCount])

  // The portfolio reloads when purchases change and when the currency changes.
  useEffect(() => {
    // If another load starts before this one finishes, ignore this one's result,
    // so a slow, outdated response can't overwrite a newer one.
    let outdated = false
    // Loaded together so the chart and the holdings always show the same currency.
    Promise.all([getPortfolioHistory(currency), getHoldings(currency)])
      .then(([history, byMetal]) => {
        if (outdated) return
        setPortfolio(history)
        setHoldings(byMetal)
        setPortfolioCurrency(currency)
        setPortfolioError(null)
      })
      .catch(() => {
        if (!outdated) setPortfolioError('Could not load the portfolio.')
      })
      .finally(() => {
        if (!outdated) setPortfolioRefreshing(false)
      })
    return () => {
      outdated = true
    }
  }, [reloadCount, currency])

  function reload() {
    setPortfolioRefreshing(true)
    setReloadCount((count) => count + 1)
  }

  function handleCurrencyChange(newCurrency: Currency) {
    setPortfolioRefreshing(true)
    setCurrency(newCurrency)
    try {
      localStorage.setItem(CURRENCY_STORAGE_KEY, newCurrency)
    } catch {
      // Not remembering the choice is fine; the toggle still works.
    }
  }

  function handleSaved() {
    setEditing(undefined)
    reload()
  }

  function handleEdit(purchase: Purchase) {
    setEditing(purchase)
    document.getElementById('purchase-form')?.scrollIntoView({ behavior: 'smooth' })
  }

  async function handleDelete(purchase: Purchase) {
    const description =
      `${purchase.original_weight} ${UNIT_LABELS[purchase.original_unit]} of ` +
      `${METAL_LABELS[purchase.metal]} bought ${formatDate(purchase.purchase_date)}`
    if (!window.confirm(`Delete ${description}? This can't be undone.`)) {
      return
    }

    try {
      await deletePurchase(purchase.id)
      if (editing?.id === purchase.id) {
        setEditing(undefined)
      }
      reload()
    } catch {
      setError('Could not delete the purchase. Is the backend running?')
    }
  }

  return (
    <main>
      <h1>Metals Tracker</h1>

      <section className={portfolioRefreshing ? 'portfolio refreshing' : 'portfolio'}>
        <div className="section-header">
          <h2>Portfolio</h2>
          <CurrencyToggle value={currency} onChange={handleCurrencyChange} />
        </div>
        {portfolioError ? (
          <p className="form-error">{portfolioError}</p>
        ) : portfolio.length === 0 ? (
          <p className="empty">
            {portfolioRefreshing ? 'Loading…' : 'Add a purchase to see your portfolio.'}
          </p>
        ) : (
          <>
            <PortfolioSummary history={portfolio} currency={portfolioCurrency} />
            <PortfolioChart history={portfolio} currency={portfolioCurrency} />
            <HoldingsTable holdings={holdings} currency={portfolioCurrency} />
            <p className="chart-note">
              Values use the spot price. Dealers charge a premium above spot, so a new
              purchase usually starts out below what you paid.
            </p>
          </>
        )}
      </section>

      <PurchaseForm
        // A new key resets the form whenever we switch between adding and editing.
        key={editing?.id ?? 'new'}
        editing={editing}
        onSaved={handleSaved}
        onCancelEdit={() => setEditing(undefined)}
      />

      <section>
        <h2>Purchase history</h2>
        {loading ? (
          <p className="empty">Loading…</p>
        ) : error ? (
          <p className="form-error">{error}</p>
        ) : (
          <PurchaseTable
            purchases={purchases}
            editingId={editing?.id}
            onEdit={handleEdit}
            onDelete={handleDelete}
          />
        )}
      </section>
    </main>
  )
}

export default App
