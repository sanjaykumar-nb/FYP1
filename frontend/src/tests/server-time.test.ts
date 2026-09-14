import { describe, it, expect } from 'vitest'
import { parseServerTime } from '@/components/tasks/task-comments'

describe('parseServerTime', () => {
  const instant = Date.UTC(2026, 8, 14, 9, 1, 22)

  it('reads zone-less timestamps as UTC', () => {
    expect(parseServerTime('2026-09-14T09:01:22').getTime()).toBe(instant)
    expect(parseServerTime('2026-09-14T09:01:22.500000').getTime()).toBe(instant + 500)
  })

  it('respects an explicit zone', () => {
    expect(parseServerTime('2026-09-14T09:01:22Z').getTime()).toBe(instant)
    expect(parseServerTime('2026-09-14T14:31:22+05:30').getTime()).toBe(instant)
  })
})
