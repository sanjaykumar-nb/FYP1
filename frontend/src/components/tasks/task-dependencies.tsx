"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { toast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import { TASK_STATUSES, type PaginatedResponse, type Task, type TaskDependency } from "@/types"

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"

const STATUS_LABELS = new Map(TASK_STATUSES.map((s) => [s.value, s.label]))

export function TaskDependencies({
  projectId,
  task,
  canEdit = true,
}: {
  projectId: string
  task: Task
  canEdit?: boolean
}) {
  const queryClient = useQueryClient()
  const [blockerId, setBlockerId] = useState("")

  const { data: tasks } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () =>
      api.get<PaginatedResponse<Task>>(`/projects/${projectId}/tasks`, { params: { page_size: 100 } }).then((res) => res.data),
  })

  const { data: dependencies, isLoading } = useQuery({
    queryKey: ["dependencies", projectId],
    queryFn: () => api.get<TaskDependency[]>(`/projects/${projectId}/dependencies`).then((res) => res.data),
  })

  const byId = new Map((tasks?.items ?? []).map((t) => [t.id, t]))
  const blockedBy = (dependencies ?? []).filter((d) => d.blocked_task_id === task.id)
  const blocks = (dependencies ?? []).filter((d) => d.blocking_task_id === task.id)
  const alreadyBlocking = new Set([task.id, ...blockedBy.map((d) => d.blocking_task_id)])
  const candidates = (tasks?.items ?? []).filter((t) => !alreadyBlocking.has(t.id))

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["dependencies", projectId] })
  const showError = (title: string) => (error: any) =>
    toast({ title, description: error.response?.data?.detail || "Please try again", variant: "destructive" })

  const add = useMutation({
    mutationFn: () =>
      api.post(`/projects/${projectId}/tasks/${task.id}/dependencies`, { blocking_task_id: blockerId }),
    onSuccess: () => {
      refresh()
      setBlockerId("")
    },
    onError: showError("Could not add dependency"),
  })

  const remove = useMutation({
    mutationFn: (dep: TaskDependency) =>
      api.delete(`/projects/${projectId}/tasks/${task.id}/dependencies/${dep.id}`),
    onSuccess: refresh,
    onError: showError("Could not remove dependency"),
  })

  function DependencyList({ items, other }: { items: TaskDependency[]; other: (d: TaskDependency) => string }) {
    if (items.length === 0) return <p className="text-sm text-muted-foreground">None</p>
    return (
      <ul className="space-y-1.5">
        {items.map((dep) => {
          const linked = byId.get(other(dep))
          const title = linked?.title ?? "Unknown task"
          return (
            <li key={dep.id} className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2">
              <span className={`text-sm flex-1 truncate ${linked?.status === "done" ? "line-through text-muted-foreground" : ""}`} title={title}>
                {title}
              </span>
              {linked && (
                <Badge variant="outline" className="text-xs shrink-0">
                  {STATUS_LABELS.get(linked.status) ?? linked.status}
                </Badge>
              )}
              {canEdit && (
                <button
                  type="button"
                  onClick={() => remove.mutate(dep)}
                  disabled={remove.isPending}
                  aria-label={`Remove dependency on ${title}`}
                  className="text-muted-foreground hover:text-destructive shrink-0"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </li>
          )
        })}
      </ul>
    )
  }

  if (isLoading) return <p className="text-sm text-muted-foreground py-4">Loading dependencies…</p>

  return (
    <div className="space-y-5">
      <section className="space-y-2">
        <h4 className="text-sm font-semibold">Blocked by</h4>
        <DependencyList items={blockedBy} other={(d) => d.blocking_task_id} />
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-semibold">Blocks</h4>
        <DependencyList items={blocks} other={(d) => d.blocked_task_id} />
      </section>

      {canEdit && (
      <form
        className="space-y-2 border-t border-border pt-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (blockerId) add.mutate()
        }}
      >
        <Label htmlFor="blocker">Add a task that blocks this one</Label>
        <div className="flex gap-2">
          <select id="blocker" className={selectClass} value={blockerId} onChange={(e) => setBlockerId(e.target.value)}>
            <option value="">Choose a task…</option>
            {candidates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
              </option>
            ))}
          </select>
          <Button type="submit" disabled={!blockerId || add.isPending} className="shrink-0">
            {add.isPending ? "Adding…" : "Add"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Blocking links feed the dependency and critical-path analysis. Circular chains are refused.
        </p>
      </form>
      )}
    </div>
  )
}
