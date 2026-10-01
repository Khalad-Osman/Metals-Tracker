import { useEffect, useState } from 'react'
import { deletePurchase, getPortfolioHistory, listPurchases } from './api'
import type { Currency, PortfolioDay, Purchase } from './api'
import { METAL_LABELS, UNIT_LABELS, formatDate } from './format'
import PortfolioChart from './components/PortfolioChart'
import PortfolioSummary from './components/PortfolioSummary'
import PurchaseForm from './components/PurchaseForm'
import PurchaseTable from './components/PurchaseTable'

// A CAD/USD toggle comes later; everything is shown in CAD for now.
const DISPLAY_CURRENCY: Currency = 'CAD'

function App() {
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // The purchase being edited in the form, if any.
  const [editing, setEditing] = useState<Purchase | undefined>()
  const [portfolio, setPortfolio] = useState<PortfolioDay[]>([])
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

  // The portfolio changes whenever purchases do, so it reloads at the same times.
  useEffect(() => {
    getPortfolioHistory(DISPLAY_CURRENCY)
      .then((data) => {
        setPortfolio(data)
        setPortfolioError(null)
      })
      .catch(() => setPortfolioError('Could not load the portfolio.'))
      .finally(() => setPortfolioRefreshing(false))
  }, [reloadCount])

  function reload() {
    setPortfolioRefreshing(true)
    setReloadCount((count) => count + 1)
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
        <h2>Portfolio</h2>
        {portfolioError ? (
          <p className="form-error">{portfolioError}</p>
        ) : portfolio.length === 0 ? (
          <p className="empty">
            {portfolioRefreshing ? 'Loading…' : 'Add a purchase to see your portfolio.'}
          </p>
        ) : (
          <>
            <PortfolioSummary history={portfolio} currency={DISPLAY_CURRENCY} />
            <PortfolioChart history={portfolio} currency={DISPLAY_CURRENCY} />
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
