import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'fs'
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

describe('landing page links', () => {
  const APP = path.join(process.cwd(), 'src', 'app')
  const source = readFileSync(path.join(APP, 'page.tsx'), 'utf-8')
  const hrefs = Array.from(source.matchAll(/href="([^"]*)"/g), (m) => m[1])
  const routeExists = (route: string) =>
    existsSync(path.join(APP, route, 'page.tsx')) || existsSync(path.join(APP, '(auth)', route, 'page.tsx'))

  it('has links, and none of them go nowhere', () => {
    expect(hrefs.length).toBeGreaterThan(0)
    expect(hrefs).not.toContain('#')
  })

  it('every page link has a page and every anchor has its section', () => {
    for (const href of hrefs) {
      if (href === '/') continue
      if (href.startsWith('#')) expect(source.includes(`id="${href.slice(1)}"`), href).toBe(true)
      else expect(routeExists(href), href).toBe(true)
    }
  })
})
