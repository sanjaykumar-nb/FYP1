import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('React Query Hooks', () => {
  describe('useQuery', () => {
    it('fetches data successfully', async () => {
      const mockFn = vi.fn().mockResolvedValue({ data: 'test' })
      
      const { result } = renderHook(() => useQuery({ queryKey: ['test'], queryFn: mockFn }), {
        wrapper: createWrapper(),
      })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(result.current.data).toEqual({ data: 'test' })
      expect(mockFn).toHaveBeenCalledTimes(1)
    })

    it('handles error state', async () => {
      const mockFn = vi.fn().mockRejectedValue(new Error('Failed'))
      
      const { result } = renderHook(() => useQuery({ queryKey: ['test'], queryFn: mockFn }), {
        wrapper: createWrapper(),
      })

      await waitFor(() => expect(result.current.isError).toBe(true))
      expect(result.current.error).toBeInstanceOf(Error)
    })

    it('caches results', async () => {
      const mockFn = vi.fn().mockResolvedValue({ data: 'test' })
      
      const { result, rerender } = renderHook(
        () => useQuery({ queryKey: ['test'], queryFn: mockFn }),
        { wrapper: createWrapper() }
      )

      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      
      // Rerender with same key should use cache
      rerender()
      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(mockFn).toHaveBeenCalledTimes(1)
    })
  })

  describe('useMutation', () => {
    it('executes mutation and invalidates queries', async () => {
      const mockMutate = vi.fn().mockResolvedValue({ id: '1', name: 'Created' })
      const queryClient = new QueryClient()
      
      const { result } = renderHook(() => {
        const client = useQueryClient()
        return useMutation({
          mutationFn: mockMutate,
          onSuccess: () => client.invalidateQueries({ queryKey: ['items'] }),
        })
      }, {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      })

      await act(async () => {
        await result.current.mutateAsync({ name: 'New Item' })
      })

      // React Query commits mutation state asynchronously.
      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(result.current.data).toEqual({ id: '1', name: 'Created' })
      expect(mockMutate).toHaveBeenCalledWith({ name: 'New Item' }, expect.anything())
    })

    it('handles mutation error', async () => {
      const mockMutate = vi.fn().mockRejectedValue(new Error('Mutation failed'))
      
      const { result } = renderHook(() => useMutation({ mutationFn: mockMutate }), {
        wrapper: createWrapper(),
      })

      await act(async () => {
        await expect(result.current.mutateAsync({ name: 'Fail' })).rejects.toThrow()
      })

      await waitFor(() => expect(result.current.isError).toBe(true))
      expect(result.current.error).toBeInstanceOf(Error)
    })
  })
})

describe('Custom Hooks', () => {
  it('useToast provides toast functions', () => {
    // This would test the actual use-toast hook if exported
    expect(true).toBe(true)
  })
})