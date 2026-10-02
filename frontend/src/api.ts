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

export type PurchaseInput = {
  metal: Metal
  weight: string
  unit: WeightUnit
  purchase_date: string
  price_paid: string
  currency: Currency
}

// Field name -> message, e.g. { weight: "Input should be greater than 0" }
export type FieldErrors = Partial<Record<keyof PurchaseInput, string>>

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

export async function createPurchase(purchase: PurchaseInput): Promise<Purchase> {
  const response = await fetch(`${API_URL}/purchases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(purchase),
  })
  await throwIfFailed(response, 'Could not save purchase')
  return response.json()
}

export async function updatePurchase(id: number, purchase: PurchaseInput): Promise<Purchase> {
  const response = await fetch(`${API_URL}/purchases/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(purchase),
  })
  await throwIfFailed(response, 'Could not save changes')
  return response.json()
}

export async function deletePurchase(id: number): Promise<void> {
  const response = await fetch(`${API_URL}/purchases/${id}`, { method: 'DELETE' })
  await throwIfFailed(response, 'Could not delete purchase')
}

async function throwIfFailed(response: Response, message: string): Promise<void> {
  // 422 means the backend rejected some fields; collect a message for each one.
  if (response.status === 422) {
    const body: { detail: FastApiError[] } = await response.json()
    const fieldErrors: FieldErrors = {}
    for (const error of body.detail) {
      const field = error.loc[error.loc.length - 1] as keyof PurchaseInput
      fieldErrors[field] = error.msg.replace(/^Value error, /, '')
    }
    throw new ValidationError(fieldErrors)
  }

  if (!response.ok) {
    throw new Error(`${message} (error ${response.status})`)
  }
}

// One day of portfolio history. Amounts are exact strings, or null when the
// backend had no recent enough price or exchange rate to work them out.
export type PortfolioDay = {
  date: string
  value: string | null
  cost: string | null
  gain: string | null
  gain_percent: string | null
}

// With `metal`, only that metal's purchases count (e.g. just your gold).
export async function getPortfolioHistory(
  currency: Currency,
  metal?: Metal,
): Promise<PortfolioDay[]> {
  const params = new URLSearchParams({ currency })
  if (metal) {
    params.set('metal', metal)
  }
  const response = await fetch(`${API_URL}/portfolio/history?${params}`)
  if (!response.ok) {
    throw new Error(`Could not load portfolio (error ${response.status})`)
  }
  return response.json()
}

// One metal's position today. Amounts are exact strings, or null when unknown.
export type Holding = {
  metal: Metal
  weight_oz: string
  value: string | null
  cost: string | null
  gain: string | null
  gain_percent: string | null
  share_percent: string | null
}

export async function getHoldings(currency: Currency): Promise<Holding[]> {
  const response = await fetch(`${API_URL}/portfolio/holdings?currency=${currency}`)
  if (!response.ok) {
    throw new Error(`Could not load holdings (error ${response.status})`)
  }
  return response.json()
}
