"use client"

import { ReactNode, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"
import { isAuthenticated } from "@/lib/auth"

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const router = useRouter()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login")
      return
    }
    setChecked(true)
  }, [router])

  if (!checked) {
    return null
  }

  return (
    <div className="min-h-screen bg-background">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="lg:pl-64 flex flex-col min-h-screen">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 p-4 md:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
