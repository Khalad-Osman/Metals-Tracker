type Option<T extends string> = {
  value: T
  label: string
}

type Props<T extends string> = {
  // Read out by screen readers, e.g. "Display currency".
  label: string
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
}

// A row of side-by-side buttons where exactly one is selected (e.g. CAD / USD).
export default function Toggle<T extends string>({ label, options, value, onChange }: Props<T>) {
  return (
    <div className="toggle" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
