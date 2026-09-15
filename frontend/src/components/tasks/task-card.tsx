import { Draggable } from "@hello-pangea/dnd"
import { Calendar, GripVertical, Lock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { Task } from "@/types"

const PRIORITY_STYLES: Record<string, string> = {
  low: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  medium: "bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-400",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-950/50 dark:text-orange-400",
  critical: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-400",
}

function initials(name: string) {
  // Anonymised imports ("… contributor #3409") share every word but the number.
  const trailingNumber = name.match(/(\d+)\s*$/)
  if (trailingNumber) return trailingNumber[1].slice(-2)
  return name
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("")
}

export function TaskCard({
  task,
  index,
  onClick,
  assigneeName,
  openBlockers,
  dragDisabled = false,
}: {
  task: Task
  index: number
  onClick: () => void
  assigneeName?: string | null
  /** How many unfinished tasks block this one. */
  openBlockers?: number
  /** For people whose role cannot change tasks. */
  dragDisabled?: boolean
}) {
  const overdue = task.due_date && task.status !== "done" && new Date(task.due_date) < new Date()

  return (
    <Draggable draggableId={task.id} index={index} isDragDisabled={dragDisabled}>
      {(provided, snapshot) => (
        <Card
          ref={provided.innerRef}
          {...provided.draggableProps}
          onClick={onClick}
          className={`cursor-pointer hover:shadow-md transition-shadow ${
            snapshot.isDragging ? "shadow-lg ring-2 ring-primary" : ""
          }`}
        >
          <CardContent className="p-3 space-y-2">
            <div className="flex items-start gap-2">
              <span
                {...provided.dragHandleProps}
                className={`mt-0.5 text-muted-foreground/50 hover:text-muted-foreground ${dragDisabled ? "invisible" : ""}`}
              >
                <GripVertical className="h-4 w-4" />
              </span>
              <p className="text-sm font-medium flex-1">{task.title}</p>
            </div>
            {task.component && <p className="pl-6 text-xs text-muted-foreground">{task.component}</p>}
            <div className="flex items-center justify-between flex-wrap gap-2 pl-6">
              <Badge className={PRIORITY_STYLES[task.priority] || ""} variant="outline">
                {task.priority}
              </Badge>
              {task.story_points != null && (
                <Badge variant="secondary" className="text-xs">
                  {task.story_points} pts
                </Badge>
              )}
              {task.due_date && (
                <span className={`text-xs flex items-center gap-1 ${overdue ? "text-destructive" : "text-muted-foreground"}`}>
                  <Calendar className="h-3 w-3" />
                  {new Date(task.due_date).toLocaleDateString()}
                </span>
              )}
              {openBlockers ? (
                <span className="text-xs flex items-center gap-1 text-destructive" title="Waiting on unfinished tasks">
                  <Lock className="h-3 w-3" />
                  Blocked by {openBlockers}
                </span>
              ) : null}
              {assigneeName ? (
                <span
                  title={assigneeName}
                  className="ml-auto h-6 w-6 rounded-full bg-primary/10 text-primary text-[10px] font-semibold flex items-center justify-center"
                >
                  {initials(assigneeName)}
                </span>
              ) : (
                <span className="ml-auto text-[10px] text-muted-foreground">Unassigned</span>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </Draggable>
  )
}
