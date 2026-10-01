// Talks to the FastAPI backend. Weights and money come back as strings
// (e.g. "3.21507466") so they stay exact; we only turn them into numbers to display them.

const API_URL = 'http://localhost:8000'

export type Metal = 'gold' | 'silver' | 'platinum' | 'palladium'
export type WeightUnit = 'g' | 'troy_oz' | 'kg'
export type Currency = 'CAD' | 'USD'

export type Purchase = {
  id: number
  metal: Metal
  weight_oz: string
  original_weight: string
  original_unit: WeightUnit
  purchase_date: string
  price_paid: string
  currency: Currency
}

export type NewPurchase = {
  metal: Metal
  weight: string
  unit: WeightUnit
  purchase_date: string
  price_paid: string
  currency: Currency
}

// Field name -> message, e.g. { weight: "Input should be greater than 0" }
export type FieldErrors = Partial<Record<keyof NewPurchase, string>>

export class ValidationError extends Error {
  fieldErrors: FieldErrors

  constructor(fieldErrors: FieldErrors) {
    super('Some fields are invalid')
    this.fieldErrors = fieldErrors
  }
}

type FastApiError = { loc: (string | number)[]; msg: string }

export async function listPurchases(): Promise<Purchase[]> {
  const response = await fetch(`${API_URL}/purchases`)
  if (!response.ok) {
    throw new Error(`Could not load purchases (error ${response.status})`)
  }
  return response.json()
}

export async function createPurchase(purchase: NewPurchase): Promise<Purchase> {
  const response = await fetch(`${API_URL}/purchases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(purchase),
  })

  // 422 means the backend rejected some fields; collect a message for each one.
  if (response.status === 422) {
    const body: { detail: FastApiError[] } = await response.json()
    const fieldErrors: FieldErrors = {}
    for (const error of body.detail) {
      const field = error.loc[error.loc.length - 1] as keyof NewPurchase
      fieldErrors[field] = error.msg.replace(/^Value error, /, '')
    }
    throw new ValidationError(fieldErrors)
  }

  if (!response.ok) {
    throw new Error(`Could not save purchase (error ${response.status})`)
  }
  return response.json()
}
