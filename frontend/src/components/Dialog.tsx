import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

type Props = {
  // The id of the element that names the dialog, e.g. its heading.
  labelledBy: string
  // Called when the dialog closes itself, e.g. with the Esc key.
  onClose: () => void
  children: ReactNode
}

// A modal dialog, using the browser's own <dialog>: it dims the page, keeps
// keyboard focus inside, and closes with Esc. It's open while it's shown.
export default function Dialog({ labelledBy, onClose, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (dialog && !dialog.open) {
      dialog.showModal()
    }
    // No cleanup needed: removing the element from the page also closes it.
  }, [])

  // Clicking the dimmed backdrop deliberately doesn't close it, so a stray click
  // can't throw away a half-filled form.
  return (
    <dialog ref={ref} className="dialog" aria-labelledby={labelledBy} onClose={onClose}>
      {children}
    </dialog>
  )
}
