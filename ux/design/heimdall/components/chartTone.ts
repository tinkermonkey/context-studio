export type ChartTone = 'light' | 'dark'

export interface ToneTokens {
  fg1: string; fg2: string; fg3: string; fg4: string
  grid: string; border: string; card: string; inset: string
}

export const TONE: Record<ChartTone, ToneTokens> = {
  light: { fg1: '#0B1220', fg2: '#475569', fg3: '#64748B', fg4: '#94A3B8', grid: '#EEF1F4', border: '#E5E9EE', card: '#FFFFFF', inset: '#F7F9FB' },
  dark:  { fg1: '#E2E8F0', fg2: '#94A3B8', fg3: '#64748B', fg4: '#475569', grid: '#1B2949', border: '#243763', card: '#1B2949', inset: '#13203A' },
}

export function fmt(n: number): string {
  return Math.abs(n) >= 1000 ? (n / 1000).toFixed(1) + 'k' : Number.isInteger(n) ? String(n) : n.toFixed(1)
}
