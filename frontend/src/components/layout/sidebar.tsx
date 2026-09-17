"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { ArrowLeft, Brain, ChevronLeft, FolderKanban, LayoutDashboard, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

export interface NavItem {
  name: string
  href: string
  icon: typeof LayoutDashboard
  /** Project items are relative to /projects/{id} unless marked absolute. */
  absolute?: boolean
}

// Only destinations that exist: src/tests/navigation.test.ts fails if an item has no page.
// Sprints, Team and AI Insights are tabs on a project's Overview.
export const workspaceNavigation: NavItem[] = [
  { name: "Workspace", href: "/workspace", icon: LayoutDashboard },
]

export const projectNavigation: NavItem[] = [
  { name: "All projects", href: "/workspace", icon: ArrowLeft, absolute: true },
  { name: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { name: "Task board", href: "/tasks", icon: FolderKanban },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname()
  const projectMatch = pathname.match(/^\/projects\/([^/]+)/)
  const isProjectPage = !!projectMatch && projectMatch[1] !== "new"
  const projectRoot = projectMatch ? `/projects/${projectMatch[1]}` : ""

  const items = isProjectPage
    ? projectNavigation.map((item) => ({ ...item, href: item.absolute ? item.href : `${projectRoot}${item.href}` }))
    : workspaceNavigation

  return (
    <>
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-screen w-64 border-r border-border bg-card transition-transform duration-200 ease-in-out lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="Sidebar"
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center justify-between px-4 border-b border-border">
            <Link href="/workspace" className="flex items-center gap-2">
              <Brain className="h-8 w-8 text-primary" />
              <span className="font-bold text-xl">TeamSync AI</span>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={onClose}
              aria-label="Close sidebar"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 p-4" aria-label="Main navigation">
            <div className="flex items-center gap-2 px-2 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {isProjectPage ? "Project" : "Workspace"}
            </div>
            {items.map((item) => (
              <NavLink key={item.name} item={item} pathname={pathname} onClose={onClose} />
            ))}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-border">
            <div className="text-xs text-muted-foreground text-center">
              TeamSync AI v1.0.0
            </div>
          </div>
        </div>
      </aside>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-background/80 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
    </>
  )
}

function NavLink({ item, pathname, onClose }: { item: NavItem; pathname: string; onClose: () => void }) {
  const isActive = pathname === item.href || pathname.startsWith(item.href + "/")

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
        isActive
          ? "bg-primary text-primary-foreground hover:bg-primary/90"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      )}
      onClick={onClose}
    >
      <item.icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
      <span>{item.name}</span>
    </Link>
  )
}
