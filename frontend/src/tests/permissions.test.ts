import { describe, it, expect } from 'vitest'
import { grantableRoles, hasPermission } from '@/hooks/use-permissions'

describe('hasPermission', () => {
  it('grants what the role lists, and everything to an owner', () => {
    expect(hasPermission(['task:read', 'task:update'], 'task:update')).toBe(true)
    expect(hasPermission(['task:read'], 'task:update')).toBe(false)
    expect(hasPermission(['*'], 'analytics:run')).toBe(true)
  })

  it('grants nothing before the role has loaded', () => {
    expect(hasPermission(undefined, 'task:read')).toBe(false)
  })
})

describe('grantableRoles', () => {
  const offered = ['developer', 'project_manager', 'viewer']

  it('never offers a role above your own', () => {
    expect(grantableRoles('project_manager', offered)).toEqual(offered)
    expect(grantableRoles('developer', offered)).toEqual(['developer', 'viewer'])
    expect(grantableRoles('owner', offered)).toEqual(offered)
  })

  it('offers nothing to an unknown or missing role', () => {
    expect(grantableRoles(undefined, offered)).toEqual([])
    expect(grantableRoles('custom', offered)).toEqual([])
  })
})
