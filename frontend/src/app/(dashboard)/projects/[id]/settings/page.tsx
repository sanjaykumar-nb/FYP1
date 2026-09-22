"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Archive } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { toast } from "@/hooks/use-toast"
import { usePermissions } from "@/hooks/use-permissions"
import { api } from "@/lib/api"
import { parseCapacity } from "@/lib/utils"
import type { Project } from "@/types"

const STATUSES = [
  { value: "active", label: "Active" },
  { value: "on_hold", label: "On hold" },
  { value: "completed", label: "Completed" },
]

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"

/** "2026-09-01T00:00:00" -> "2026-09-01" for a date input, and back. */
const toDay = (value: string | null) => (value ? value.slice(0, 10) : "")
const toDateTime = (day: string) => (day ? `${day}T00:00:00` : null)

const errorDetail = (error: any, fallback: string) => {
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : fallback
}

export default function ProjectSettingsPage() {
  const params = useParams()
  const projectId = params.id as string
  const router = useRouter()
  const queryClient = useQueryClient()
  const { can } = usePermissions()
  const canEdit = can("project:update")
  const canArchive = can("project:delete")

  const [form, setForm] = useState({
    name: "", description: "", status: "active", start_date: "", target_end_date: "", capacity: "",
  })
  const [confirmArchive, setConfirmArchive] = useState(false)

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.get<Project>(`/projects/${projectId}`).then((res) => res.data),
  })

  useEffect(() => {
    if (project) {
      setForm({
        name: project.name,
        description: project.description ?? "",
        status: project.status,
        start_date: toDay(project.start_date),
        target_end_date: toDay(project.target_end_date),
        capacity: project.sprint_capacity_points?.toString() ?? "",
      })
    }
  }, [project])

  const datesValid = !form.start_date || !form.target_end_date || form.start_date < form.target_end_date
  const capacity = parseCapacity(form.capacity)

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/projects/${projectId}`, {
        name: form.name.trim(),
        description: form.description.trim() || null,
        status: form.status,
        start_date: toDateTime(form.start_date),
        target_end_date: toDateTime(form.target_end_date),
        sprint_capacity_points: capacity,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast({ title: "Settings saved", variant: "success" })
    },
    onError: (error: any) =>
      toast({ title: "Could not save settings", description: errorDetail(error, "Check the fields and try again"), variant: "destructive" }),
  })

  const archive = useMutation({
    mutationFn: () => api.delete(`/projects/${projectId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast({ title: "Project archived", description: `${project?.name} moved to the workspace's Archived list.`, variant: "success" })
      router.push("/workspace")
    },
    onError: (error: any) =>
      toast({ title: "Could not archive project", description: errorDetail(error, "Please try again"), variant: "destructive" }),
  })

  if (!project) return <p className="text-muted-foreground py-8 text-center">Loading settings…</p>

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  return (
    <div className="max-w-2xl space-y-6">
      <div className="space-y-1">
        <Badge variant="secondary">{project.key}</Badge>
        <h1 className="text-3xl font-bold tracking-tight">Project settings</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Details</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              save.mutate()
            }}
          >
            <fieldset disabled={!canEdit} className="space-y-4 min-w-0">
              <div className="space-y-1.5">
                <Label htmlFor="project-name">Name</Label>
                <Input id="project-name" required value={form.name} onChange={set("name")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="project-description">Description</Label>
                <Input id="project-description" value={form.description} onChange={set("description")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="project-status">Status</Label>
                <select id="project-status" className={selectClass} value={form.status} onChange={set("status")}>
                  {STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="project-start">Start date</Label>
                  <Input id="project-start" type="date" value={form.start_date} onChange={set("start_date")} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="project-end">Target end date</Label>
                  <Input id="project-end" type="date" value={form.target_end_date} onChange={set("target_end_date")} />
                </div>
              </div>
              {!datesValid && <p className="text-xs text-destructive">The end date must be after the start date.</p>}
              <div className="space-y-1.5">
                <Label htmlFor="project-capacity">Sprint capacity (story points)</Label>
                <Input
                  id="project-capacity"
                  inputMode="numeric"
                  placeholder="Measured from finished sprints"
                  value={form.capacity}
                  onChange={set("capacity")}
                  className="sm:w-64"
                />
                {capacity === undefined ? (
                  <p className="text-xs text-destructive">Enter a whole number of points from 1 to 10000, or leave it empty.</p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    The planning agent warns when a sprint plans more than this. Leave it empty to use the average the
                    team completed in its last three finished sprints.
                  </p>
                )}
              </div>
            </fieldset>
            {canEdit ? (
              <Button type="submit" disabled={save.isPending || !form.name.trim() || !datesValid || capacity === undefined}>
                {save.isPending ? "Saving…" : "Save changes"}
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">View only: your role can&apos;t change project settings.</p>
            )}
          </form>
        </CardContent>
      </Card>

      {canArchive && (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle className="text-lg">Archive project</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Archiving hides the project from the workspace. Its tasks, discussions and analysis history are kept,
              and it can be restored from the workspace's Archived list.
            </p>
            <Button variant="destructive" onClick={() => setConfirmArchive(true)}>
              <Archive className="mr-2 h-4 w-4" />
              Archive project
            </Button>
          </CardContent>
        </Card>
      )}

      <Dialog open={confirmArchive} onOpenChange={setConfirmArchive}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive {project.name}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">It disappears from the workspace. Nothing is deleted, and you can restore it from the workspace's Archived list.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmArchive(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => archive.mutate()} disabled={archive.isPending}>
              {archive.isPending ? "Archiving…" : "Archive"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
