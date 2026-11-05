import { Suspense, lazy, useEffect, useState } from 'react'
import {
  ApiError,
  createPurchase,
  deletePurchase,
  getDemoMode,
  getHoldings,
  getPortfolioHistory,
  listPurchases,
  purchaseInput,
} from './api'
import type { Currency, DemoMode, Holding, Metal, PortfolioDay, Purchase } from './api'
import { CHART_RANGES } from './chartRange'
import type { ChartRange } from './chartRange'
import { METAL_LABELS, UNIT_LABELS, formatDate } from './format'
import Dialog from './components/Dialog'
import HoldingsTable from './components/HoldingsTable'
import MetalName from './components/MetalName'
import PortfolioSummary from './components/PortfolioSummary'
import PurchaseForm from './components/PurchaseForm'
import PurchaseTable from './components/PurchaseTable'
import Toast from './components/Toast'
import type { ToastMessage } from './components/Toast'
import Toggle from './components/Toggle'

// The chart library (Recharts) is most of the app's code, so it's downloaded
// separately: the page and summary figures show first, then the chart.
const PortfolioChart = lazy(() => import('./components/PortfolioChart'))

// Which metals the portfolio chart and summary show: all of them, or just one.
type MetalFilter = Metal | 'all'

const CURRENCY_STORAGE_KEY = 'displayCurrency'
const METAL_FILTER_STORAGE_KEY = 'portfolioMetal'
const CHART_RANGE_STORAGE_KEY = 'chartRange'
// Also read by the script in index.html, which applies it before the page draws.
const THEME_STORAGE_KEY = 'theme'

type Theme = 'system' | 'light' | 'dark'

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

function savedTheme(): Theme {
  const saved = loadSetting(THEME_STORAGE_KEY)
  return saved === 'light' || saved === 'dark' ? saved : 'system'
}

function savedChartRange(): ChartRange {
  const saved = loadSetting(CHART_RANGE_STORAGE_KEY)
  return CHART_RANGES.find((option) => option.value === saved)?.value ?? 'all'
}

function App() {
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // The purchase dialog: closed, adding a new purchase, or editing this one.
  const [dialogFor, setDialogFor] = useState<Purchase | 'new' | null>(null)
  const editing = dialogFor !== null && dialogFor !== 'new' ? dialogFor : undefined
  // The message at the bottom of the screen, e.g. "Purchase deleted · Undo".
  const [toast, setToast] = useState<ToastMessage | null>(null)
  // Whether this is a public demo, and if so whether purchases can be changed.
  const [demoMode, setDemoMode] = useState<DemoMode>('off')
  const readOnly = demoMode === 'readonly'

  // What the user picked, and what the loaded data is actually for. They differ
  // briefly while new data loads, so the old numbers keep their correct labels.
  const [currency, setCurrency] = useState<Currency>(savedCurrency)
  const [metalFilter, setMetalFilter] = useState<MetalFilter>(savedMetalFilter)
  const [loadedCurrency, setLoadedCurrency] = useState<Currency>(currency)
  const [loadedMetal, setLoadedMetal] = useState<MetalFilter>('all')
  // How much history the chart shows. Changing it doesn't reload anything.
  const [chartRange, setChartRange] = useState<ChartRange>(savedChartRange)
  const [theme, setTheme] = useState<Theme>(savedTheme)
  // The day under the pointer on the chart; the summary figures show it.
  const [hoveredDay, setHoveredDay] = useState<PortfolioDay | null>(null)

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

  // Each message disappears after 10 seconds (a new message restarts the clock).
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 10000)
    return () => clearTimeout(timer)
  }, [toast])

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

  function handleThemeChange(newTheme: Theme) {
    setTheme(newTheme)
    saveSetting(THEME_STORAGE_KEY, newTheme)
    // The colors in index.css switch on this attribute; without it they follow the system.
    if (newTheme === 'system') {
      delete document.documentElement.dataset.theme
    } else {
      document.documentElement.dataset.theme = newTheme
    }
  }

  function handleChartRangeChange(newRange: ChartRange) {
    setChartRange(newRange)
    saveSetting(CHART_RANGE_STORAGE_KEY, newRange)
  }

  function showToast(text: string, action?: ToastMessage['action']) {
    setToast({ id: Date.now(), text, action })
  }

  function handleSaved() {
    showToast(editing ? 'Changes saved.' : 'Purchase added.')
    setDialogFor(null)
    reload()
  }

  // Deletes straight away, with an Undo that adds the same purchase back.
  async function handleDelete(purchase: Purchase) {
    try {
      await deletePurchase(purchase.id)
      reload()
      showToast(`Deleted ${describe(purchase)}.`, {
        label: 'Undo',
        onClick: () => handleUndoDelete(purchase),
      })
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : 'Could not delete the purchase. Is the backend running?',
      )
    }
  }

  async function handleUndoDelete(purchase: Purchase) {
    setToast(null)
    try {
      // Same details as before; only its internal id is new.
      await createPurchase(purchaseInput(purchase))
      reload()
      showToast(`Restored ${describe(purchase)}.`)
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : 'Could not restore the purchase. Is the backend running?',
      )
    }
  }

  // The metal filter is only offered when there's more than one metal to pick from.
  const metalOptions = [
    { value: 'all' as MetalFilter, label: 'All' },
    ...holdings.map((holding) => ({
      value: holding.metal as MetalFilter,
      label: <MetalName metal={holding.metal} />,
    })),
  ]
  // What the summary and chart describe, e.g. "Portfolio" or "Gold".
  const subject = loadedMetal === 'all' ? 'Portfolio' : METAL_LABELS[loadedMetal]

  return (
    <main>
      <header className="page-header">
        <div className="brand">
          <h1>
            <img className="logo" src="/favicon.svg" alt="" width="32" height="32" />
            Troy Ledger
          </h1>
          <p className="tagline">Precious metals portfolio tracker</p>
        </div>
        <div className="header-actions">
          <Toggle
            label="Display currency"
            options={[
              { value: 'CAD', label: 'CAD' },
              { value: 'USD', label: 'USD' },
            ]}
            value={currency}
            onChange={handleCurrencyChange}
          />
          {!readOnly && (
            <button type="button" className="primary" onClick={() => setDialogFor('new')}>
              Add purchase
            </button>
          )}
        </div>
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
        ) : portfolio.length === 0 && portfolioRefreshing ? (
          <>
            <PortfolioSkeleton />
            {slowStart && (
              <p className="empty">
                Starting the server… On free hosting this can take up to a minute after it has
                been idle.
              </p>
            )}
          </>
        ) : portfolio.length === 0 ? (
          <p className="empty">Add a purchase to see your portfolio.</p>
        ) : (
          <>
            <PortfolioSummary
              history={portfolio}
              currency={loadedCurrency}
              subject={subject}
              hoveredDay={hoveredDay}
            />
            {/* Holds the chart's space while its code downloads, so nothing jumps. */}
            <Suspense fallback={<div className="chart-placeholder skeleton" aria-busy="true" />}>
              <PortfolioChart
                history={portfolio}
                currency={loadedCurrency}
                subject={subject}
                range={chartRange}
                onRangeChange={handleChartRangeChange}
                onHoverDay={setHoveredDay}
                // Matches the loaded chart data, so markers never show another metal.
                purchases={
                  loadedMetal === 'all'
                    ? purchases
                    : purchases.filter((purchase) => purchase.metal === loadedMetal)
                }
              />
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

      <section>
        <h2>Purchase history</h2>
        {loading ? (
          <RowsSkeleton />
        ) : error ? (
          <p className="form-error">{error}</p>
        ) : (
          <PurchaseTable
            purchases={purchases}
            editingId={editing?.id}
            // Without these the table is read-only, as in the demo.
            onEdit={readOnly ? undefined : setDialogFor}
            onDelete={readOnly ? undefined : handleDelete}
          />
        )}
      </section>

      {dialogFor !== null && (
        <Dialog labelledBy="purchase-form-title" onClose={() => setDialogFor(null)}>
          <PurchaseForm
            editing={editing}
            onSaved={handleSaved}
            onCancel={() => setDialogFor(null)}
          />
        </Dialog>
      )}

      <footer className="page-footer">
        <span className="muted">Theme</span>
        <Toggle
          label="Theme"
          options={[
            { value: 'system', label: 'System' },
            { value: 'light', label: 'Light' },
            { value: 'dark', label: 'Dark' },
          ]}
          value={theme}
          onChange={handleThemeChange}
        />
      </footer>

      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </main>
  )
}

// Gray shapes where the summary and chart will appear, while they load.
function PortfolioSkeleton() {
  return (
    <div aria-busy="true">
      <span className="visually-hidden">Loading…</span>
      <div className="summary" aria-hidden="true">
        <div className="skeleton skeleton-stat" />
        <div className="skeleton skeleton-stat" />
        <div className="skeleton skeleton-stat" />
      </div>
      <div className="skeleton skeleton-chart" aria-hidden="true" />
    </div>
  )
}

// Gray rows where a table will appear, while it loads.
function RowsSkeleton() {
  return (
    <div aria-busy="true">
      <span className="visually-hidden">Loading…</span>
      {[1, 2, 3].map((row) => (
        <div key={row} className="skeleton skeleton-row" aria-hidden="true" />
      ))}
    </div>
  )
}

// e.g. "1 troy oz of Gold bought Oct 1, 2026"
function describe(purchase: Purchase): string {
  return (
    `${purchase.original_weight} ${UNIT_LABELS[purchase.original_unit]} of ` +
    `${METAL_LABELS[purchase.metal]} bought ${formatDate(purchase.purchase_date)}`
  )
}

export default App
