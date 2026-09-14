"use client"

import { useMemo, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { DragDropContext, Droppable, type DropResult } from "@hello-pangea/dnd"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { toast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import { TASK_STATUSES, type Member, type PaginatedResponse, type Task, type TaskStatus } from "@/types"
import { TaskCard } from "@/components/tasks/task-card"
import { TaskDialog } from "@/components/tasks/task-dialog"

export default function TaskBoardPage() {
  const params = useParams()
  const projectId = params.id as string
  const queryClient = useQueryClient()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | undefined>(undefined)
  const [newTaskStatus, setNewTaskStatus] = useState<TaskStatus | undefined>(undefined)

  const { data, isLoading } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () =>
      api.get<PaginatedResponse<Task>>(`/projects/${projectId}/tasks`, { params: { page_size: 100 } }).then((res) => res.data),
  })

  const { data: members } = useQuery({
    queryKey: ["members", projectId],
    queryFn: () =>
      api
        .get<PaginatedResponse<Member>>(`/projects/${projectId}/members`, { params: { page_size: 100 } })
        .then((res) => res.data.items),
  })
  const memberNames = useMemo(
    () => new Map((members ?? []).map((m) => [m.id, m.full_name || m.email])),
    [members]
  )

  const tasks = data?.items ?? []
  const columns = useMemo(() => {
    const byStatus: Record<TaskStatus, Task[]> = {
      backlog: [],
      planned: [],
      in_progress: [],
      blocked: [],
      review: [],
      done: [],
    }
    for (const task of tasks) {
      ;(byStatus[task.status] ?? byStatus.backlog).push(task)
    }
    for (const status of Object.keys(byStatus) as TaskStatus[]) {
      byStatus[status].sort((a, b) => a.position - b.position)
    }
    return byStatus
  }, [tasks])

  const moveTask = useMutation({
    mutationFn: ({ taskId, status, position }: { taskId: string; status: TaskStatus; position: number }) =>
      api.patch(`/projects/${projectId}/tasks/${taskId}/move`, { status, position }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tasks", projectId] }),
    onError: (error: any) => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] })
      toast({
        title: "Could not move task",
        description: error.response?.data?.detail || "Please try again",
        variant: "destructive",
      })
    },
  })

  function onDragEnd(result: DropResult) {
    const { destination, source, draggableId } = result
    if (!destination) return
    if (destination.droppableId === source.droppableId && destination.index === source.index) return

    moveTask.mutate({
      taskId: draggableId,
      status: destination.droppableId as TaskStatus,
      position: destination.index,
    })
  }

  function openNewTask(status: TaskStatus) {
    setEditingTask(undefined)
    setNewTaskStatus(status)
    setDialogOpen(true)
  }

  function openEditTask(task: Task) {
    setEditingTask(task)
    setNewTaskStatus(undefined)
    setDialogOpen(true)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link href={`/projects/${projectId}/dashboard`} className="text-sm text-muted-foreground hover:underline mb-2 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="text-3xl font-bold tracking-tight">Task Board</h1>
        </div>
        <Button onClick={() => openNewTask("backlog")}>
          <Plus className="mr-2 h-4 w-4" />
          New Task
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground py-8 text-center">Loading tasks…</p>
      ) : (
        <DragDropContext onDragEnd={onDragEnd}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 items-start">
            {TASK_STATUSES.map(({ value, label }) => (
              <Droppable droppableId={value} key={value}>
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={`rounded-lg border border-border bg-muted/30 p-3 min-h-[200px] space-y-2 ${
                      snapshot.isDraggingOver ? "ring-2 ring-primary bg-muted/60" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="text-sm font-semibold">{label}</h3>
                      <span className="text-xs text-muted-foreground bg-background rounded-full px-2 py-0.5">
                        {columns[value].length}
                      </span>
                    </div>
                    {columns[value].map((task, index) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        index={index}
                        onClick={() => openEditTask(task)}
                        assigneeName={task.assignee_id ? memberNames.get(task.assignee_id) : null}
                      />
                    ))}
                    {provided.placeholder}
                    <button
                      onClick={() => openNewTask(value)}
                      className="w-full text-xs text-muted-foreground hover:text-foreground py-1.5 flex items-center justify-center gap-1 rounded border border-dashed border-border hover:border-foreground/30 transition-colors"
                    >
                      <Plus className="h-3 w-3" />
                      Add task
                    </button>
                  </div>
                )}
              </Droppable>
            ))}
          </div>
        </DragDropContext>
      )}

      <TaskDialog
        projectId={projectId}
        task={editingTask}
        defaultStatus={newTaskStatus}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </div>
  )
}
