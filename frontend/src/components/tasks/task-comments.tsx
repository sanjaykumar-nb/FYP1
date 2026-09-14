"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { toast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import type { PaginatedResponse, TaskComment } from "@/types"

/** The backend stores UTC, but SQLite hands timestamps back without a zone; read those as UTC. */
export function parseServerTime(value: string): Date {
  return new Date(/(Z|[+-]\d\d:?\d\d)$/i.test(value) ? value : `${value}Z`)
}

export function TaskComments({
  projectId,
  taskId,
  canComment = true,
}: {
  projectId: string
  taskId: string
  canComment?: boolean
}) {
  const queryClient = useQueryClient()
  const [content, setContent] = useState("")

  const { data, isLoading } = useQuery({
    queryKey: ["comments", taskId],
    queryFn: () =>
      api
        .get<PaginatedResponse<TaskComment>>(`/projects/${projectId}/tasks/${taskId}/comments`, { params: { page_size: 100 } })
        .then((res) => res.data),
  })

  const add = useMutation({
    mutationFn: () => api.post(`/projects/${projectId}/tasks/${taskId}/comments`, { content: content.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["comments", taskId] })
      setContent("")
    },
    onError: (error: any) =>
      toast({
        title: "Could not post comment",
        description: error.response?.data?.detail || "Please try again",
        variant: "destructive",
      }),
  })

  const comments = data?.items ?? []

  return (
    <div className="space-y-4">
      {isLoading ? (
        <p className="text-sm text-muted-foreground py-4">Loading discussion…</p>
      ) : comments.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4">No comments yet.</p>
      ) : (
        <ul className="space-y-3 max-h-80 overflow-y-auto pr-1">
          {comments.map((c) => (
            <li key={c.id} className="rounded-md bg-muted/50 px-3 py-2">
              <div className="flex items-baseline justify-between gap-2 mb-1">
                <span className="text-sm font-medium">{c.author_name ?? "Former member"}</span>
                <time className="text-xs text-muted-foreground shrink-0" dateTime={c.created_at}>
                  {parseServerTime(c.created_at).toLocaleString()}
                </time>
              </div>
              <p className="text-sm whitespace-pre-wrap break-words">{c.content}</p>
            </li>
          ))}
        </ul>
      )}
      {data && data.total > comments.length && (
        <p className="text-xs text-muted-foreground">Showing the first {comments.length} of {data.total} comments.</p>
      )}

      {canComment && (
      <form
        className="space-y-2 border-t border-border pt-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (content.trim()) add.mutate()
        }}
      >
        <Label htmlFor="comment">Add a comment</Label>
        <textarea
          id="comment"
          rows={3}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={!content.trim() || add.isPending}>
            {add.isPending ? "Posting…" : "Comment"}
          </Button>
        </div>
      </form>
      )}
    </div>
  )
}
