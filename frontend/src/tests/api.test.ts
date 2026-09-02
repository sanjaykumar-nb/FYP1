import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// The api module installs interceptors on a real axios instance. Rather than
// asserting on mock call shapes, these tests exercise the interceptors
// directly — that is the behaviour we actually depend on.

describe('API client', () => {
  beforeEach(() => {
    vi.resetModules()
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('is configured with a base URL, JSON content type and a timeout', async () => {
    const { api } = await import('@/lib/api')

    expect(api.defaults.baseURL).toEqual(expect.any(String))
    expect(api.defaults.baseURL).not.toBe('')
    expect(api.defaults.headers['Content-Type']).toBe('application/json')
    expect(api.defaults.timeout).toBe(30000)
  })

  it('attaches the access token as a Bearer header when one is stored', async () => {
    const { api } = await import('@/lib/api')
    vi.mocked(localStorage.getItem).mockReturnValue('test-token')

    const handler = (api.interceptors.request as any).handlers[0].fulfilled
    const config = handler({ headers: {} as Record<string, string> })

    expect(config.headers.Authorization).toBe('Bearer test-token')
  })

  it('sends no Authorization header when no token is stored', async () => {
    const { api } = await import('@/lib/api')
    vi.mocked(localStorage.getItem).mockReturnValue(null)

    const handler = (api.interceptors.request as any).handlers[0].fulfilled
    const config = handler({ headers: {} as Record<string, string> })

    expect(config.headers.Authorization).toBeUndefined()
  })

  it('refreshes the token on a 401 and replays the original request', async () => {
    const axios = (await import('axios')).default
    const { api, API_BASE_URL } = await import('@/lib/api')

    const store: Record<string, string> = {
      access_token: 'expired-token',
      refresh_token: 'refresh-token',
    }
    vi.mocked(localStorage.getItem).mockImplementation((k: string) => store[k] ?? null)
    vi.mocked(localStorage.setItem).mockImplementation((k: string, v: string) => {
      store[k] = v
    })

    const post = vi
      .spyOn(axios, 'post')
      .mockResolvedValue({ data: { access_token: 'new-token', refresh_token: 'new-refresh' } })

    const rejected = (api.interceptors.response as any).handlers[0].rejected
    const originalRequest = { headers: {} as Record<string, string> }

    await rejected({ response: { status: 401 }, config: originalRequest }).catch(
      () => undefined
    )

    // The refresh call must send the token in the request BODY, never the query
    // string — the backend endpoint takes a JSON body.
    expect(post).toHaveBeenCalledWith(`${API_BASE_URL}/api/v1/auth/refresh`, {
      refresh_token: 'refresh-token',
    })
    expect(store.access_token).toBe('new-token')
    expect(store.refresh_token).toBe('new-refresh')
    expect(originalRequest.headers.Authorization).toBe('Bearer new-token')
  })

  it('clears stored tokens when the refresh itself fails', async () => {
    const axios = (await import('axios')).default
    const { api } = await import('@/lib/api')

    const store: Record<string, string> = {
      access_token: 'expired-token',
      refresh_token: 'invalid-refresh',
    }
    vi.mocked(localStorage.getItem).mockImplementation((k: string) => store[k] ?? null)
    vi.mocked(localStorage.removeItem).mockImplementation((k: string) => {
      delete store[k]
    })

    vi.spyOn(axios, 'post').mockRejectedValue(new Error('invalid refresh token'))
    vi.stubGlobal('location', { href: '' })

    const rejected = (api.interceptors.response as any).handlers[0].rejected
    await expect(
      rejected({ response: { status: 401 }, config: { headers: {} } })
    ).rejects.toBeTruthy()

    expect(store.access_token).toBeUndefined()
    expect(store.refresh_token).toBeUndefined()
  })

  it('passes non-401 errors straight through without refreshing', async () => {
    const axios = (await import('axios')).default
    const { api } = await import('@/lib/api')

    const post = vi.spyOn(axios, 'post')
    const rejected = (api.interceptors.response as any).handlers[0].rejected

    await expect(
      rejected({ response: { status: 500 }, config: { headers: {} } })
    ).rejects.toBeTruthy()
    expect(post).not.toHaveBeenCalled()
  })
})
