"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { UserPlus } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { toast } from "@/hooks/use-toast"
import { grantableRoles, usePermissions } from "@/hooks/use-permissions"
import { api } from "@/lib/api"
import type { Member, PaginatedResponse } from "@/types"

const EMPTY_FORM = { full_name: "", email: "", password: "", role: "developer" }

const ROLE_LABELS: Record<string, string> = {
  developer: "Developer",
  project_manager: "Project manager",
  viewer: "Viewer",
}

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"

export function TeamPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(EMPTY_FORM)
  const { me, role, can } = usePermissions()
  const canInvite = can("member:invite")
  const roleOptions = grantableRoles(role, Object.keys(ROLE_LABELS))

  const { data: members, isLoading } = useQuery({
    queryKey: ["members", projectId],
    queryFn: () =>
      api
        .get<PaginatedResponse<Member>>(`/projects/${projectId}/members`, { params: { page_size: 100 } })
        .then((res) => res.data.items),
  })

  const addMember = useMutation({
    // Two steps: the person gets an account in the organization, then joins this project.
    mutationFn: async () => {
      const created = await api
        .post<Member>(`/organizations/${me!.organization_id}/members`, form)
        .then((res) => res.data)
      await api.post(`/projects/${projectId}/members`, { user_id: created.id, role: form.role })
      return created
    },
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["members", projectId] })
      queryClient.invalidateQueries({ queryKey: ["project-health", projectId] })
      toast({
        title: "Teammate added",
        description: `${created.full_name || created.email} can now sign in as ${ROLE_LABELS[form.role] ?? form.role}.`,
        variant: "success",
      })
      setForm(EMPTY_FORM)
    },
    onError: (error: any) => {
      const detail = error.response?.data?.detail
      toast({
        title: "Could not add teammate",
        description: typeof detail === "string" ? detail : "Check the email and use a password of at least 8 characters.",
        variant: "destructive",
      })
    },
  })

  const set = (key: keyof typeof EMPTY_FORM) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <Card className={canInvite ? "md:col-span-2" : "md:col-span-3"}>
        <CardHeader>
          <CardTitle className="text-lg">Team ({members?.length ?? 0})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-6 text-center">Loading team…</p>
          ) : !members?.length ? (
            <p className="text-muted-foreground py-6 text-center">
              No teammates yet. Add people so work can be assigned and analyzed.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {members.map((m) => (
                <li key={m.id} className="flex items-center justify-between py-2.5">
                  <div>
                    <p className="font-medium">{m.full_name || m.email}</p>
                    <p className="text-sm text-muted-foreground">{m.email}</p>
                  </div>
                  {m.role && <Badge variant="secondary">{m.role.replace("_", " ")}</Badge>}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {canInvite && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Add teammate</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault()
                addMember.mutate()
              }}
            >
              <div className="space-y-1.5">
                <Label htmlFor="member-name">Name</Label>
                <Input id="member-name" value={form.full_name} onChange={set("full_name")} required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="member-email">Email</Label>
                <Input id="member-email" type="email" value={form.email} onChange={set("email")} required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="member-password">Initial password</Label>
                <Input
                  id="member-password"
                  type="password"
                  minLength={8}
                  value={form.password}
                  onChange={set("password")}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="member-role">Role</Label>
                <select id="member-role" className={selectClass} value={form.role} onChange={set("role")}>
                  {roleOptions.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit" className="w-full" disabled={!me || addMember.isPending}>
                <UserPlus className="mr-2 h-4 w-4" />
                {addMember.isPending ? "Adding…" : "Add teammate"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
