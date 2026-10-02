import { Suspense, lazy, useEffect, useState } from 'react'
import { ApiError, deletePurchase, getDemoMode, getHoldings, getPortfolioHistory, listPurchases } from './api'
import type { Currency, DemoMode, Holding, Metal, PortfolioDay, Purchase } from './api'
import { METAL_LABELS, UNIT_LABELS, formatDate } from './format'
import HoldingsTable from './components/HoldingsTable'
import PortfolioSummary from './components/PortfolioSummary'
import PurchaseForm from './components/PurchaseForm'
import PurchaseTable from './components/PurchaseTable'
import Toggle from './components/Toggle'

// The chart library (Recharts) is most of the app's code, so it's downloaded
// separately: the page and summary figures show first, then the chart.
const PortfolioChart = lazy(() => import('./components/PortfolioChart'))

// Which metals the portfolio chart and summary show: all of them, or just one.
type MetalFilter = Metal | 'all'

const CURRENCY_STORAGE_KEY = 'displayCurrency'
const METAL_FILTER_STORAGE_KEY = 'portfolioMetal'

// Choices are remembered in this browser. Storage can be unavailable (e.g. in
// some private windows); then the defaults are used and nothing is remembered.
function loadSetting(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function saveSetting(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Not remembering the choice is fine; the controls still work.
  }
}

function savedCurrency(): Currency {
  return loadSetting(CURRENCY_STORAGE_KEY) === 'USD' ? 'USD' : 'CAD'
}

function savedMetalFilter(): MetalFilter {
  const saved = loadSetting(METAL_FILTER_STORAGE_KEY)
  return saved && Object.hasOwn(METAL_LABELS, saved) ? (saved as Metal) : 'all'
}

function App() {
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // The purchase being edited in the form, if any.
  const [editing, setEditing] = useState<Purchase | undefined>()
  // Whether this is a public demo, and if so whether purchases can be changed.
  const [demoMode, setDemoMode] = useState<DemoMode>('off')
  const readOnly = demoMode === 'readonly'

  // What the user picked, and what the loaded data is actually for. They differ
  // briefly while new data loads, so the old numbers keep their correct labels.
  const [currency, setCurrency] = useState<Currency>(savedCurrency)
  const [metalFilter, setMetalFilter] = useState<MetalFilter>(savedMetalFilter)
  const [loadedCurrency, setLoadedCurrency] = useState<Currency>(currency)
  const [loadedMetal, setLoadedMetal] = useState<MetalFilter>('all')

  const [portfolio, setPortfolio] = useState<PortfolioDay[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [portfolioError, setPortfolioError] = useState<string | null>(null)
  // True while the portfolio is reloading; the old chart stays visible but faded.
  const [portfolioRefreshing, setPortfolioRefreshing] = useState(true)
  // Bumping this number makes the effects below fetch the data again.
  const [reloadCount, setReloadCount] = useState(0)
  // True if the first load is taking a while, e.g. a free-plan server waking up.
  const [slowStart, setSlowStart] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setSlowStart(true), 4000)
    return () => clearTimeout(timer)
  }, [])

  // Ask the backend once whether this is a public demo.
  useEffect(() => {
    getDemoMode()
      .then(setDemoMode)
      .catch(() => {
        // If settings can't load, the other requests will show the error.
      })
  }, [])

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

  // The portfolio reloads when purchases change, and when the currency or metal changes.
  useEffect(() => {
    // If another load starts before this one finishes, ignore this one's result,
    // so a slow, outdated response can't overwrite a newer one.
    let outdated = false
    const metal = metalFilter === 'all' ? undefined : metalFilter

    // Loaded together so the chart and the holdings always show the same currency.
    Promise.all([getPortfolioHistory(currency, metal), getHoldings(currency)])
      .then(([history, byMetal]) => {
        if (outdated) return
        // A single metal only makes sense if it's owned and there's more than one
        // metal to choose from; otherwise show everything (this loads again).
        const owned = byMetal.some((holding) => holding.metal === metal)
        if (metal && (!owned || byMetal.length < 2)) {
          setMetalFilter('all')
          return
        }
        setPortfolio(history)
        setHoldings(byMetal)
        setLoadedCurrency(currency)
        setLoadedMetal(metalFilter)
        setPortfolioError(null)
        setPortfolioRefreshing(false)
      })
      .catch(() => {
        if (outdated) return
        setPortfolioError('Could not load the portfolio.')
        setPortfolioRefreshing(false)
      })
    return () => {
      outdated = true
    }
  }, [reloadCount, currency, metalFilter])

  function reload() {
    setPortfolioRefreshing(true)
    setReloadCount((count) => count + 1)
  }

  function handleCurrencyChange(newCurrency: Currency) {
    setPortfolioRefreshing(true)
    setCurrency(newCurrency)
    saveSetting(CURRENCY_STORAGE_KEY, newCurrency)
  }

  function handleMetalFilterChange(newFilter: MetalFilter) {
    setPortfolioRefreshing(true)
    setMetalFilter(newFilter)
    saveSetting(METAL_FILTER_STORAGE_KEY, newFilter)
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
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Could not delete the purchase. Is the backend running?',
      )
    }
  }

  // The metal filter is only offered when there's more than one metal to pick from.
  const metalOptions = [
    { value: 'all' as MetalFilter, label: 'All' },
    ...holdings.map((holding) => ({
      value: holding.metal as MetalFilter,
      label: METAL_LABELS[holding.metal],
    })),
  ]
  // What the summary and chart describe, e.g. "Portfolio" or "Gold".
  const subject = loadedMetal === 'all' ? 'Portfolio' : METAL_LABELS[loadedMetal]

  return (
    <main>
      <header className="page-header">
        <h1>Metals Tracker</h1>
        <Toggle
          label="Display currency"
          options={[
            { value: 'CAD', label: 'CAD' },
            { value: 'USD', label: 'USD' },
          ]}
          value={currency}
          onChange={handleCurrencyChange}
        />
      </header>

      {demoMode !== 'off' && (
        <p className="demo-banner" role="note">
          <strong>Demo</strong> with sample purchases and real market prices.{' '}
          {readOnly
            ? 'Adding and editing purchases are turned off.'
            : 'Try adding or editing a purchase: changes are shared with other visitors and reset every night.'}{' '}
          <a href="https://github.com/Khalad-Osman/Metals-Tracker">View the code on GitHub</a>
        </p>
      )}

      <section className={portfolioRefreshing ? 'portfolio refreshing' : 'portfolio'}>
        <div className="section-header">
          <h2>Portfolio</h2>
          {holdings.length > 1 && (
            <Toggle
              label="Show metal"
              options={metalOptions}
              value={metalFilter}
              onChange={handleMetalFilterChange}
            />
          )}
        </div>
        {portfolioError ? (
          <p className="form-error">{portfolioError}</p>
        ) : portfolio.length === 0 ? (
          <p className="empty">
            {!portfolioRefreshing
              ? 'Add a purchase to see your portfolio.'
              : slowStart
                ? 'Starting the server… On free hosting this can take up to a minute after it has been idle.'
                : 'Loading…'}
          </p>
        ) : (
          <>
            <PortfolioSummary history={portfolio} currency={loadedCurrency} subject={subject} />
            {/* Holds the chart's space while its code downloads, so nothing jumps. */}
            <Suspense fallback={<div className="chart-placeholder" aria-busy="true" />}>
              <PortfolioChart history={portfolio} currency={loadedCurrency} subject={subject} />
            </Suspense>
            <p className="chart-note">
              Values use the spot price. Dealers charge a premium above spot, so a new
              purchase usually starts out below what you paid.
            </p>
          </>
        )}
      </section>

      {holdings.length > 0 && (
        <section className={portfolioRefreshing ? 'portfolio refreshing' : 'portfolio'}>
          <h2>Holdings by metal</h2>
          <HoldingsTable holdings={holdings} currency={loadedCurrency} />
        </section>
      )}

      {!readOnly && (
        <PurchaseForm
          // A new key resets the form whenever we switch between adding and editing.
          key={editing?.id ?? 'new'}
          editing={editing}
          onSaved={handleSaved}
          onCancelEdit={() => setEditing(undefined)}
        />
      )}

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
            // Without these the table is read-only, as in the demo.
            onEdit={readOnly ? undefined : handleEdit}
            onDelete={readOnly ? undefined : handleDelete}
          />
        )}
      </section>
    </main>
  )
}

export default App
