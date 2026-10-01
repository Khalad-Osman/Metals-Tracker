import { useEffect, useState } from 'react'
import { deletePurchase, listPurchases } from './api'
import type { Purchase } from './api'
import { METAL_LABELS, UNIT_LABELS, formatDate } from './format'
import PurchaseForm from './components/PurchaseForm'
import PurchaseTable from './components/PurchaseTable'

function App() {
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // The purchase being edited in the form, if any.
  const [editing, setEditing] = useState<Purchase | undefined>()
  // Bumping this number makes the effect below fetch the list again.
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

  function reload() {
    setReloadCount((count) => count + 1)
  }

  function handleSaved() {
    setEditing(undefined)
    reload()
  }

  function handleEdit(purchase: Purchase) {
    setEditing(purchase)
    // The form is at the top of the page.
    window.scrollTo({ top: 0, behavior: 'smooth' })
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
