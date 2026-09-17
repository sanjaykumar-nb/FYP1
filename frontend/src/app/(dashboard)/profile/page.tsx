"use client"

import { useEffect, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Check, X } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { toast } from "@/hooks/use-toast"
import { hasPermission, usePermissions } from "@/hooks/use-permissions"
import { api } from "@/lib/api"

// What a role allows, in plain language, read from its permissions.
const ABILITIES: { permission: string; label: string }[] = [
  { permission: "task:read", label: "See projects, tasks, discussions and AI insights" },
  { permission: "task:create", label: "Create tasks" },
  { permission: "task:update", label: "Edit tasks, comment, and apply suggested reassignments" },
  { permission: "task:delete", label: "Delete tasks" },
  { permission: "analytics:run", label: "Run the analysis" },
  { permission: "project:update", label: "Change project settings and sprints" },
  { permission: "member:invite", label: "Add teammates" },
  { permission: "project:create", label: "Create projects" },
]

export default function ProfilePage() {
  const queryClient = useQueryClient()
  const { me, role } = usePermissions()
  const [fullName, setFullName] = useState("")

  useEffect(() => {
    if (me) setFullName(me.full_name ?? "")
  }, [me])

  const save = useMutation({
    mutationFn: () => api.patch("/auth/me", { full_name: fullName.trim() || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] })
      toast({ title: "Profile saved", variant: "success" })
    },
    onError: () => toast({ title: "Could not save profile", description: "Please try again", variant: "destructive" }),
  })

  if (!me) return <p className="text-muted-foreground py-8 text-center">Loading profile…</p>

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Profile</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Your details</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              save.mutate()
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="profile-name">Name</Label>
              <Input id="profile-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="profile-email">Email</Label>
              <Input id="profile-email" value={me.email} disabled />
            </div>
            <Button type="submit" disabled={save.isPending || fullName.trim() === (me.full_name ?? "")}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Your role</CardTitle>
            {role && <Badge variant="secondary">{role.replace("_", " ")}</Badge>}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="space-y-2 text-sm">
            {ABILITIES.map((ability) => {
              const allowed = hasPermission(me.permissions, ability.permission)
              return (
                <li key={ability.permission} className={`flex items-center gap-2 ${allowed ? "" : "text-muted-foreground"}`}>
                  {allowed ? <Check className="h-4 w-4 text-green-600" /> : <X className="h-4 w-4" />}
                  {ability.label}
                </li>
              )
            })}
          </ul>
          <p className="text-xs text-muted-foreground">Your role is set by whoever added you to the organization.</p>
        </CardContent>
      </Card>
    </div>
  )
}
