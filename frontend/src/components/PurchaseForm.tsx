import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, createPurchase, updatePurchase, ValidationError } from '../api'
import type { Currency, FieldErrors, Metal, Purchase, PurchaseInput, WeightUnit } from '../api'
import { METAL_LABELS, UNIT_LABELS, todayIso } from '../format'

type Props = {
  // When set, the form edits this purchase instead of adding a new one.
  editing?: Purchase
  onSaved: () => void
  onCancelEdit: () => void
}

function emptyForm(): PurchaseInput {
  return {
    metal: 'gold',
    weight: '',
    unit: 'troy_oz',
    purchase_date: todayIso(),
    price_paid: '',
    currency: 'CAD',
  }
}

// Fill the form with what the user originally entered for this purchase.
function formFromPurchase(purchase: Purchase): PurchaseInput {
  return {
    metal: purchase.metal,
    weight: purchase.original_weight,
    unit: purchase.original_unit,
    purchase_date: purchase.purchase_date,
    price_paid: purchase.price_paid,
    currency: purchase.currency,
  }
}

export default function PurchaseForm({ editing, onSaved, onCancelEdit }: Props) {
  const [form, setForm] = useState<PurchaseInput>(() =>
    editing ? formFromPurchase(editing) : emptyForm(),
  )
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function update<K extends keyof PurchaseInput>(field: K, value: PurchaseInput[K]) {
    setForm({ ...form, [field]: value })
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setFieldErrors({})

    try {
      if (editing) {
        await updatePurchase(editing.id, form)
      } else {
        await createPurchase(form)
        // Keep the metal, unit and currency choices; clear the rest for the next entry.
        setForm({ ...emptyForm(), metal: form.metal, unit: form.unit, currency: form.currency })
      }
      onSaved()
    } catch (err) {
      if (err instanceof ValidationError) {
        setFieldErrors(err.fieldErrors)
      } else if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Could not reach the server. Is the backend running?')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      id="purchase-form"
      className={editing ? 'purchase-form editing' : 'purchase-form'}
      onSubmit={handleSubmit}
      noValidate
    >
      <h2>{editing ? 'Edit purchase' : 'Add a purchase'}</h2>

      <div className="field">
        <label htmlFor="metal">Metal</label>
        <select
          id="metal"
          value={form.metal}
          onChange={(e) => update('metal', e.target.value as Metal)}
        >
          {Object.entries(METAL_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <FieldError message={fieldErrors.metal} />
      </div>

      <div className="field">
        <label htmlFor="weight">Weight</label>
        <div className="input-group">
          <input
            id="weight"
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            placeholder="e.g. 1"
            value={form.weight}
            onChange={(e) => update('weight', e.target.value)}
          />
          <select
            aria-label="Weight unit"
            value={form.unit}
            onChange={(e) => update('unit', e.target.value as WeightUnit)}
          >
            {Object.entries(UNIT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <FieldError message={fieldErrors.weight ?? fieldErrors.unit} />
      </div>

      <div className="field">
        <label htmlFor="purchase_date">Purchase date</label>
        <input
          id="purchase_date"
          type="date"
          max={todayIso()}
          value={form.purchase_date}
          onChange={(e) => update('purchase_date', e.target.value)}
        />
        <FieldError message={fieldErrors.purchase_date} />
      </div>

      <div className="field">
        <label htmlFor="price_paid">Total price paid</label>
        <div className="input-group">
          <input
            id="price_paid"
            type="number"
            inputMode="decimal"
            min="0"
            step="0.01"
            placeholder="e.g. 3500.00"
            value={form.price_paid}
            onChange={(e) => update('price_paid', e.target.value)}
          />
          <select
            aria-label="Currency"
            value={form.currency}
            onChange={(e) => update('currency', e.target.value as Currency)}
          >
            <option value="CAD">CAD</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <FieldError message={fieldErrors.price_paid ?? fieldErrors.currency} />
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="form-actions">
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Saving…' : editing ? 'Save changes' : 'Add purchase'}
        </button>
        {editing && (
          <button type="button" className="secondary" onClick={onCancelEdit} disabled={saving}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="field-error">{message}</p> : null
}
