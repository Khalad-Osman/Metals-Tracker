import type { Currency, Metal, WeightUnit } from './api'

export const METAL_LABELS: Record<Metal, string> = {
  gold: 'Gold',
  silver: 'Silver',
  platinum: 'Platinum',
  palladium: 'Palladium',
}

export const UNIT_LABELS: Record<WeightUnit, string> = {
  g: 'g',
  troy_oz: 'troy oz',
  kg: 'kg',
}

export function formatMoney(amount: string, currency: Currency): string {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency }).format(
    Number(amount),
  )
}

export function formatOunces(ounces: string): string {
  return `${Number(ounces).toLocaleString('en-CA', { maximumFractionDigits: 4 })} oz`
}

export function formatDate(isoDate: string): string {
  // Parse as a local date; new Date("2026-09-15") would be read as UTC midnight
  // and can show the previous day in Canadian time zones.
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// Today's date as "YYYY-MM-DD" in the user's own time zone.
export function todayIso(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
