import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { TOAST_REMOVE_DELAY, toast, useToast } from '@/hooks/use-toast'

afterEach(() => {
  vi.useRealTimers()
})

describe('toast', () => {
  it('leaves the page soon after it is dismissed', () => {
    // A dismissed toast is invisible but still catches clicks until it is removed,
    // so it must not linger: this was once ~17 minutes.
    expect(TOAST_REMOVE_DELAY).toBeLessThanOrEqual(2000)

    vi.useFakeTimers()
    const { result } = renderHook(() => useToast())
    let shown: ReturnType<typeof toast>
    act(() => {
      shown = toast({ title: 'Welcome back!' })
    })
    expect(result.current.toasts).toHaveLength(1)

    act(() => shown.dismiss())
    expect(result.current.toasts[0].open).toBe(false)

    act(() => {
      vi.advanceTimersByTime(TOAST_REMOVE_DELAY)
    })
    expect(result.current.toasts).toHaveLength(0)
  })
})
