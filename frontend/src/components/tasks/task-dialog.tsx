"use client"

import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import { TASK_STATUSES, type Member, type PaginatedResponse, type Task, type TaskStatus } from "@/types"

const taskSchema = z.object({
  title: z.string().min(1, "Title is required").max(500),
  description: z.string().optional(),
  status: z.enum(["backlog", "planned", "in_progress", "blocked", "review", "done"]),
  priority: z.enum(["low", "medium", "high", "critical"]),
  story_points: z.string().optional(),
  due_date: z.string().optional(),
  assignee_id: z.string().optional(),
})
type TaskForm = z.infer<typeof taskSchema>

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"

export function TaskDialog({
  projectId,
  task,
  open,
  onOpenChange,
  defaultStatus,
}: {
  projectId: string
  task?: Task
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultStatus?: TaskStatus
}) {
  const queryClient = useQueryClient()
  const isEdit = !!task

  const { data: members } = useQuery({
    queryKey: ["members", projectId],
    queryFn: () =>
      api
        .get<PaginatedResponse<Member>>(`/projects/${projectId}/members`, { params: { page_size: 100 } })
        .then((res) => res.data.items),
    enabled: open,
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TaskForm>({
    resolver: zodResolver(taskSchema),
    defaultValues: {
      status: defaultStatus || "backlog",
      priority: "medium",
    },
  })

  useEffect(() => {
    if (open) {
      reset(
        task
          ? {
              title: task.title,
              description: task.description || "",
              status: task.status,
              priority: task.priority,
              story_points: task.story_points != null ? String(task.story_points) : "",
              due_date: task.due_date ? task.due_date.slice(0, 10) : "",
              assignee_id: task.assignee_id ?? "",
            }
          : {
              title: "",
              description: "",
              status: defaultStatus || "backlog",
              priority: "medium",
              story_points: "",
              due_date: "",
              assignee_id: "",
            }
      )
    }
  }, [open, task, defaultStatus, reset])

  const save = useMutation({
    mutationFn: (data: TaskForm) => {
      const payload = {
        title: data.title,
        description: data.description || undefined,
        status: data.status,
        priority: data.priority,
        story_points: data.story_points ? Number(data.story_points) : undefined,
        due_date: data.due_date ? new Date(data.due_date).toISOString() : undefined,
        // On edit, an empty choice must clear the assignee rather than leave it unchanged.
        assignee_id: data.assignee_id || (isEdit ? null : undefined),
      }
      return isEdit
        ? api.patch(`/projects/${projectId}/tasks/${task!.id}`, payload)
        : api.post(`/projects/${projectId}/tasks`, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] })
      toast({ title: isEdit ? "Task updated" : "Task created", variant: "success" })
      onOpenChange(false)
    },
    onError: (error: any) => {
      toast({
        title: "Could not save task",
        description: error.response?.data?.detail || "Please try again",
        variant: "destructive",
      })
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Task" : "New Task"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit((data) => save.mutate(data))} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" {...register("title")} />
            {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input id="description" {...register("description")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
              <select id="status" className={selectClass} {...register("status")}>
                {TASK_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="priority">Priority</Label>
              <select id="priority" className={selectClass} {...register("priority")}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="assignee_id">Assignee</Label>
            <select id="assignee_id" className={selectClass} {...register("assignee_id")}>
              <option value="">Unassigned</option>
              {(members ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.full_name || m.email}
                </option>
              ))}
            </select>
            {members && members.length === 0 && (
              <p className="text-xs text-muted-foreground">Add teammates from the project&apos;s Team tab to assign work.</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="story_points">Story Points</Label>
              <Input id="story_points" type="number" min={0} {...register("story_points")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="due_date">Due Date</Label>
              <Input id="due_date" type="date" {...register("due_date")} />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "Saving…" : isEdit ? "Save Changes" : "Create Task"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
