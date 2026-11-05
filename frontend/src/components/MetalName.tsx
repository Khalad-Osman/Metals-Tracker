import type { Metal } from '../api'
import { METAL_LABELS } from '../format'

// A metal's name with its color dot, e.g. "● Gold". The name is always written
// out, so the color is never the only way to tell metals apart.
export default function MetalName({ metal }: { metal: Metal }) {
  return (
    <span className="metal-name">
      <span className={`metal-dot ${metal}`} aria-hidden="true" />
      {METAL_LABELS[metal]}
    </span>
  )
}
