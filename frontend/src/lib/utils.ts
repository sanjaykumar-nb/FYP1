import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * The sprint-capacity field: empty means "use the team's measured velocity" (null),
 * a whole number of story points from 1 to 10000 is kept, anything else is invalid (undefined).
 */
export function parseCapacity(value: string): number | null | undefined {
  const trimmed = value.trim()
  if (!trimmed) return null
  if (!/^\d+$/.test(trimmed)) return undefined
  const points = Number(trimmed)
  return points >= 1 && points <= 10000 ? points : undefined
}
