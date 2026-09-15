"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CalendarPlus } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { toast } from "@/hooks/use-toast"
import { usePermissions } from "@/hooks/use-permissions"
import { api } from "@/lib/api"
import type { Milestone, PaginatedResponse, Task } from "@/types"

export type SprintPhase = "upcoming" | "active" | "ended" | "unscheduled"

export interface SprintProgress {
  tasks: number
  open: number
  /** Share of the sprint's work done: story points, each task counting at least 1 (as the analysis weighs it). */
  workDone: number
  /** Share of the start -> end window that has passed, or null without a start date. */
  timeElapsed: number | null
  phase: SprintPhase
}

/** Display-only progress for a sprint. The pace verdict itself comes from the analysis. */
export function sprintProgress(milestone: Milestone, tasks: Task[], now: Date = new Date()): SprintProgress {
  const inSprint = tasks.filter((t) => t.milestone_id === milestone.id)
  const weight = (t: Task) => Math.max(t.story_points ?? 0, 1)
  const total = inSprint.reduce((sum, t) => sum + weight(t), 0)
  const done = inSprint.filter((t) => t.status === "done").reduce((sum, t) => sum + weight(t), 0)

  const end = new Date(milestone.target_date)
  const start = milestone.start_date ? new Date(milestone.start_date) : null
  let timeElapsed: number | null = null
  let phase: SprintPhase = now >= end ? "ended" : "unscheduled"
  if (start && end > start) {
    const raw = (now.getTime() - start.getTime()) / (end.getTime() - start.getTime())
    timeElapsed = Math.min(1, Math.max(0, raw))
    phase = raw < 0 ? "upcoming" : raw >= 1 ? "ended" : "active"
  }

  return {
    tasks: inSprint.length,
    open: inSprint.filter((t) => t.status !== "done").length,
    workDone: total ? done / total : 0,
    timeElapsed,
    phase,
  }
}

const PHASE_LABELS: Record<SprintPhase, string> = {
  upcoming: "Upcoming",
  active: "In progress",
  ended: "Ended",
  unscheduled: "No start date",
}

const EMPTY_FORM = { name: "", start_date: "", target_date: "" }

/** Date inputs give "YYYY-MM-DD"; the API takes a datetime. */
const asDateTime = (day: string) => (day ? `${day}T00:00:00` : null)
const formatDay = (value: string) => new Date(value).toLocaleDateString()
const endsAfterStart = (start: string, end: string) => !start || !end || start < end

function Bar({ label, value }: { label: string; value: number }) {
  const percent = Math.round(value * 100)
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{percent}%</span>
      </div>
      <Progress value={percent} className="h-2" />
    </div>
  )
}

export function SprintsPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const { can } = usePermissions()
  const canEdit = can("project:update")
  const [form, setForm] = useState(EMPTY_FORM)
  const [editing, setEditing] = useState<string | null>(null)
  const [dates, setDates] = useState({ start_date: "", target_date: "" })

  const { data: milestones, isLoading } = useQuery({
    queryKey: ["milestones", projectId],
    queryFn: () =>
      api
        .get<PaginatedResponse<Milestone>>(`/projects/${projectId}/milestones`, { params: { page_size: 100 } })
        .then((res) => res.data.items),
  })

  const { data: tasks } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () =>
      api.get<PaginatedResponse<Task>>(`/projects/${projectId}/tasks`, { params: { page_size: 100 } }).then((res) => res.data),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["milestones", projectId] })
  const showError = (title: string) => (error: any) => {
    const detail = error.response?.data?.detail
    toast({ title, description: typeof detail === "string" ? detail : "Check the name and dates", variant: "destructive" })
  }

  const create = useMutation({
    mutationFn: () =>
      api.post(`/projects/${projectId}/milestones`, {
        name: form.name,
        start_date: asDateTime(form.start_date),
        target_date: asDateTime(form.target_date),
      }),
    onSuccess: () => {
      refresh()
      setForm(EMPTY_FORM)
      toast({ title: "Sprint created", description: "Add tasks to it from the task dialog.", variant: "success" })
    },
    onError: showError("Could not create sprint"),
  })

  const update = useMutation({
    mutationFn: (id: string) =>
      api.patch(`/projects/${projectId}/milestones/${id}`, {
        start_date: asDateTime(dates.start_date),
        target_date: asDateTime(dates.target_date),
      }),
    onSuccess: () => {
      refresh()
      setEditing(null)
    },
    onError: showError("Could not update sprint"),
  })

  return (
    <div className="grid gap-6 md:grid-cols-3">
      <Card className={canEdit ? "md:col-span-2" : "md:col-span-3"}>
        <CardHeader>
          <CardTitle className="text-lg">Sprints ({milestones?.length ?? 0})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-6 text-center">Loading sprints…</p>
          ) : !milestones?.length ? (
            <p className="text-muted-foreground py-6 text-center">
              No sprints yet. Give one a start and end date so the analysis can tell whether its work is on pace.
            </p>
          ) : (
            <ul className="space-y-4">
              {milestones.map((m) => {
                const progress = sprintProgress(m, tasks?.items ?? [])
                return (
                  <li key={m.id} className="rounded-lg border border-border p-4 space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-medium">{m.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {m.start_date ? `${formatDay(m.start_date)} → ${formatDay(m.target_date)}` : `Due ${formatDay(m.target_date)}`}
                          {` · ${progress.tasks} task${progress.tasks === 1 ? "" : "s"}, ${progress.open} open`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">{PHASE_LABELS[progress.phase]}</Badge>
                        {canEdit && editing !== m.id && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditing(m.id)
                              setDates({ start_date: m.start_date?.slice(0, 10) ?? "", target_date: m.target_date.slice(0, 10) })
                            }}
                          >
                            Edit dates
                          </Button>
                        )}
                      </div>
                    </div>

                    <Bar label="Work done" value={progress.workDone} />
                    {progress.timeElapsed != null ? (
                      <Bar label="Time elapsed" value={progress.timeElapsed} />
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Add a start date to compare progress with time. The analysis needs it to warn when work falls behind pace.
                      </p>
                    )}

                    {editing === m.id && (
                      <form
                        className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] items-end border-t border-border pt-3"
                        onSubmit={(e) => {
                          e.preventDefault()
                          update.mutate(m.id)
                        }}
                      >
                        <div className="space-y-1.5">
                          <Label htmlFor="edit-start">Start</Label>
                          <Input id="edit-start" type="date" value={dates.start_date}
                            onChange={(e) => setDates((d) => ({ ...d, start_date: e.target.value }))} />
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="edit-end">End</Label>
                          <Input id="edit-end" type="date" required value={dates.target_date}
                            onChange={(e) => setDates((d) => ({ ...d, target_date: e.target.value }))} />
                        </div>
                        <div className="flex gap-2">
                          <Button type="submit" size="sm"
                            disabled={update.isPending || !endsAfterStart(dates.start_date, dates.target_date)}>
                            Save
                          </Button>
                          <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(null)}>
                            Cancel
                          </Button>
                        </div>
                      </form>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {canEdit && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">New sprint</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault()
                create.mutate()
              }}
            >
              <div className="space-y-1.5">
                <Label htmlFor="sprint-name">Name</Label>
                <Input id="sprint-name" required value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sprint-start">Start date</Label>
                <Input id="sprint-start" type="date" value={form.start_date}
                  onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sprint-end">End date</Label>
                <Input id="sprint-end" type="date" required value={form.target_date}
                  onChange={(e) => setForm((f) => ({ ...f, target_date: e.target.value }))} />
              </div>
              {!endsAfterStart(form.start_date, form.target_date) && (
                <p className="text-xs text-destructive">The end date must be after the start date.</p>
              )}
              <Button type="submit" className="w-full"
                disabled={create.isPending || !endsAfterStart(form.start_date, form.target_date)}>
                <CalendarPlus className="mr-2 h-4 w-4" />
                {create.isPending ? "Creating…" : "Create sprint"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
