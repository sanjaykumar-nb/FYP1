"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  FolderKanban,
  Users,
  Calendar,
  MessageSquare,
  BarChart3,
  Lightbulb,
  Database,
  Settings,
  Brain,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

const navigation = [
  { name: "Dashboard", href: "/workspace", icon: LayoutDashboard },
  { name: "Projects", href: "/projects", icon: FolderKanban },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Admin", href: "/admin", icon: Settings, adminOnly: true },
]

// Relative to a project's root — resolved against /projects/{id} below.
// Pages not yet built in the MVP (meetings, recommendations, memory, review,
// settings) still route correctly; they 404 until their phase lands rather
// than silently going to the workspace root.
const projectNavigation = [
  { name: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { name: "Tasks", href: "/tasks", icon: FolderKanban },
  { name: "Meetings", href: "/meetings", icon: MessageSquare },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Recommendations", href: "/recommendations", icon: Lightbulb },
  { name: "Memory", href: "/memory", icon: Database },
  { name: "Review", href: "/review", icon: Brain },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname()
  const projectMatch = pathname.match(/^\/projects\/([^/]+)/)
  const isProjectPage = !!projectMatch && projectMatch[1] !== "new"
  const projectRoot = projectMatch ? `/projects/${projectMatch[1]}` : ""

  const resolvedProjectNavigation = projectNavigation.map((item) => ({
    ...item,
    href: `${projectRoot}${item.href}`,
  }))

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
            {isProjectPage ? (
              <>
                <div className="flex items-center gap-2 px-2 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Project
                </div>
                {resolvedProjectNavigation.map((item) => (
                  <NavLink key={item.name} item={item} pathname={pathname} onClose={onClose} />
                ))}
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 px-2 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Workspace
                </div>
                {navigation.map((item) => (
                  <NavLink key={item.name} item={item} pathname={pathname} onClose={onClose} />
                ))}
              </>
            )}
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

function NavLink({ item, pathname, onClose }: { item: typeof navigation[0]; pathname: string; onClose: () => void }) {
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