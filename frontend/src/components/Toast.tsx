export type ToastMessage = {
  // A new id for each message, so the same text twice still counts as new.
  id: number
  text: string
  // An optional button, e.g. "Undo".
  action?: { label: string; onClick: () => void }
}

type Props = {
  toast: ToastMessage | null
  onDismiss: () => void
}

// A short message at the bottom of the screen, e.g. "Purchase deleted · Undo".
// The live region is always on the page, so screen readers announce each new message.
export default function Toast({ toast, onDismiss }: Props) {
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {toast && (
        <div className="toast" key={toast.id}>
          <span>{toast.text}</span>
          {toast.action && (
            <button type="button" className="toast-action" onClick={toast.action.onClick}>
              {toast.action.label}
            </button>
          )}
          <button type="button" className="toast-close" aria-label="Dismiss" onClick={onDismiss}>
            ×
          </button>
        </div>
      )}
    </div>
  )
}
