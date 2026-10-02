import type { Purchase } from '../api'
import { METAL_LABELS, UNIT_LABELS, formatDate, formatMoney, formatOunces } from '../format'

type Props = {
  purchases: Purchase[]
  editingId?: number
  // Without these, the table is read-only (no Edit/Delete column), e.g. in the demo.
  onEdit?: (purchase: Purchase) => void
  onDelete?: (purchase: Purchase) => void
}

export default function PurchaseTable({ purchases, editingId, onEdit, onDelete }: Props) {
  const editable = onEdit !== undefined && onDelete !== undefined

  if (purchases.length === 0) {
    return <p className="empty">No purchases yet. Add your first one above.</p>
  }

  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Metal</th>
            <th className="number">Weight entered</th>
            <th className="number">Troy ounces</th>
            <th className="number">Price paid</th>
            {editable && (
              <th>
                <span className="visually-hidden">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {purchases.map((purchase) => (
            <tr key={purchase.id} className={purchase.id === editingId ? 'editing' : undefined}>
              <td>{formatDate(purchase.purchase_date)}</td>
              <td>{METAL_LABELS[purchase.metal]}</td>
              <td className="number">
                {purchase.original_weight} {UNIT_LABELS[purchase.original_unit]}
              </td>
              <td className="number">{formatOunces(purchase.weight_oz)}</td>
              <td className="number">{formatMoney(purchase.price_paid, purchase.currency)}</td>
              {editable && (
                <td className="actions">
                  <button type="button" className="link" onClick={() => onEdit(purchase)}>
                    Edit
                  </button>
                  <button type="button" className="link danger" onClick={() => onDelete(purchase)}>
                    Delete
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
