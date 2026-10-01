import { useEffect, useState } from 'react'
import { listPurchases } from './api'
import type { Purchase } from './api'
import PurchaseForm from './components/PurchaseForm'
import PurchaseTable from './components/PurchaseTable'

function App() {
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Bumping this number makes the effect below fetch the list again.
  const [reloadCount, setReloadCount] = useState(0)

  // Load the purchase history when the page opens, and again after each new purchase.
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

  return (
    <main>
      <h1>Metals Tracker</h1>

      <PurchaseForm
        // Reload from the server so the list stays sorted by purchase date.
        onCreated={() => setReloadCount((count) => count + 1)}
      />

      <section>
        <h2>Purchase history</h2>
        {loading ? (
          <p className="empty">Loading…</p>
        ) : error ? (
          <p className="form-error">{error}</p>
        ) : (
          <PurchaseTable purchases={purchases} />
        )}
      </section>
    </main>
  )
}

export default App
