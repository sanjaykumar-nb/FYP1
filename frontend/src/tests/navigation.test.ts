import { describe, it, expect } from 'vitest'
import { existsSync } from 'fs'
import path from 'path'
import { projectNavigation, workspaceNavigation } from '@/components/layout/sidebar'

// Guards against links to pages that were never built (they used to 404 in the demo).
const DASHBOARD = path.join(process.cwd(), 'src', 'app', '(dashboard)')
const pageExists = (...segments: string[]) => existsSync(path.join(DASHBOARD, ...segments, 'page.tsx'))

describe('navigation', () => {
  it('every workspace link has a page', () => {
    for (const item of workspaceNavigation) {
      expect(pageExists(item.href), item.href).toBe(true)
    }
  })

  it('every project link has a page', () => {
    for (const item of projectNavigation) {
      const exists = item.absolute ? pageExists(item.href) : pageExists('projects', '[id]', item.href)
      expect(exists, item.href).toBe(true)
    }
  })

  it('the account menu links to a page', () => {
    expect(pageExists('/profile')).toBe(true)
  })
})
