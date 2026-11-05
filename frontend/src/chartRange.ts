// How much of the portfolio history the chart shows, e.g. the last 3 months.
// Kept out of PortfolioChart so the page can use it without loading the chart's code.

export type ChartRange = '1M' | '3M' | '6M' | '1Y' | 'YTD' | 'all'

export const CHART_RANGES: { value: ChartRange; label: string }[] = [
  { value: '1M', label: '1M' },
  { value: '3M', label: '3M' },
  { value: '6M', label: '6M' },
  { value: '1Y', label: '1Y' },
  { value: 'YTD', label: 'YTD' },
  { value: 'all', label: 'All' },
]

const MONTHS: Partial<Record<ChartRange, number>> = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12 }

// The first date (YYYY-MM-DD) a range covers, counting back from `lastDate`.
// Returns null for 'all'.
export function rangeStart(range: ChartRange, lastDate: string): string | null {
  if (range === 'all') {
    return null
  }
  if (range === 'YTD') {
    return `${lastDate.slice(0, 4)}-01-01`
  }
  // UTC, so the time zone can't shift the date. Near the end of a month this can
  // land a few days later than expected (e.g. Mar 31 - 1 month = Mar 3), which is fine.
  const date = new Date(`${lastDate}T00:00:00Z`)
  date.setUTCMonth(date.getUTCMonth() - (MONTHS[range] ?? 0))
  return date.toISOString().slice(0, 10)
}

// The ranges worth offering for this history: those that show less than all of it,
// plus 'all'. `dates` must be in order, oldest first.
export function availableRanges(dates: string[]): ChartRange[] {
  if (dates.length === 0) {
    return ['all']
  }
  const first = dates[0]
  const last = dates[dates.length - 1]
  return CHART_RANGES.map((option) => option.value).filter((range) => {
    const start = rangeStart(range, last)
    return start === null || start > first
  })
}
