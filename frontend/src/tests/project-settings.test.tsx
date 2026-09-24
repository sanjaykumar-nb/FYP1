import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { parseCapacity } from '@/lib/utils'
import { taskReference } from '@/components/tasks/task-github'

const api = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn(), delete: vi.fn() }))
const permissions = vi.hoisted(() => ({ granted: new Set<string>() }))

vi.mock('@/lib/api', () => ({ api }))
vi.mock('@/hooks/use-permissions', () => ({
  usePermissions: () => ({ can: (p: string) => permissions.granted.has(p) }),
}))
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'p1' }),
  useRouter: () => ({ push: vi.fn() }),
}))

import ProjectSettingsPage from '@/app/(dashboard)/projects/[id]/settings/page'

const PROJECT = {
  id: 'p1', organization_id: 'o1', team_id: null, name: 'Mesos', description: null, key: 'MESOS',
  status: 'active', start_date: null, target_end_date: null, actual_end_date: null,
  health_score: null, risk_score: null, sprint_capacity_points: 30, github_repo: null,
  created_at: '2026-01-01T00:00:00Z',
}

/** The capacity field, once the form has been filled from the loaded project. */
async function capacityField() {
  const field = await screen.findByLabelText('Sprint capacity (story points)')
  await waitFor(() => expect(field).toHaveValue('30'))
  return field
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ProjectSettingsPage />
    </QueryClientProvider>
  )
}

describe('parseCapacity', () => {
  it('reads empty as "use the measured velocity" and rejects what is not a whole number of points', () => {
    expect(parseCapacity('')).toBeNull()
    expect(parseCapacity('  ')).toBeNull()
    expect(parseCapacity('34')).toBe(34)
    expect(parseCapacity(' 8 ')).toBe(8)
    for (const bad of ['0', '-3', '2.5', 'ten', '10001']) expect(parseCapacity(bad)).toBeUndefined()
  })
})

describe('Project settings: sprint capacity', () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: PROJECT })
    api.patch.mockReset().mockResolvedValue({ data: PROJECT })
    permissions.granted = new Set(['project:update'])
  })

  it('shows the saved capacity and sends a changed one', async () => {
    renderPage()
    const field = await capacityField()

    fireEvent.change(field, { target: { value: '24' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalled())
    expect(api.patch.mock.calls[0][0]).toBe('/projects/p1')
    expect(api.patch.mock.calls[0][1]).toMatchObject({ sprint_capacity_points: 24 })
  })

  it('clears to null, so the planning agent falls back to measured velocity', async () => {
    renderPage()
    fireEvent.change(await capacityField(), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalled())
    expect(api.patch.mock.calls[0][1]).toMatchObject({ sprint_capacity_points: null })
  })

  it('will not save a capacity that is not a whole number of points', async () => {
    renderPage()
    fireEvent.change(await capacityField(), { target: { value: '2.5' } })
    expect(screen.getByText(/Enter a whole number of points/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
  })

  it('is read-only for a role that cannot change settings', async () => {
    permissions.granted = new Set()
    renderPage()
    expect(await capacityField()).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument()
  })
})

describe('GitHub repository setting', () => {
  beforeEach(() => {
    api.get.mockReset().mockResolvedValue({ data: PROJECT })
    api.patch.mockReset().mockResolvedValue({ data: PROJECT })
    permissions.granted = new Set(['project:update'])
  })

  it('saves a repository, and clears it to null when emptied', async () => {
    renderPage()
    const repo = await screen.findByLabelText('GitHub repository')
    fireEvent.change(repo, { target: { value: 'apache/mesos' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalled())
    expect(api.patch.mock.calls[0][1]).toMatchObject({ github_repo: 'apache/mesos' })

    api.patch.mockClear()
    fireEvent.change(repo, { target: { value: '  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(api.patch).toHaveBeenCalled())
    expect(api.patch.mock.calls[0][1]).toMatchObject({ github_repo: null })
  })

  it('offers the sync button only once a repository is set', async () => {
    renderPage()
    await capacityField()
    expect(screen.queryByRole('button', { name: /Sync with GitHub/ })).not.toBeInTheDocument()
  })
})

describe('taskReference', () => {
  it('is the first eight characters of the task id when the API sends none', () => {
    expect(taskReference({ id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890' })).toBe('a1b2c3d4')
    expect(taskReference({ id: 'ignored', reference: 'deadbeef' })).toBe('deadbeef')
  })
})
