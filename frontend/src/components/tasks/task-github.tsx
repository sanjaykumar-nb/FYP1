"use client"

import { useQuery } from "@tanstack/react-query"
import { GitCommit, GitPullRequest } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import type { GithubLink } from "@/types"

/** What a person writes in a branch name so the sync finds this task. */
export function taskReference(task: { id: string; reference?: string }) {
  return task.reference ?? task.id.replace(/-/g, "").slice(0, 8)
}

export function TaskGithub({ projectId, task }: { projectId: string; task: { id: string; reference?: string } }) {
  const { data, isLoading } = useQuery({
    queryKey: ["github-links", projectId],
    queryFn: () => api.get<GithubLink[]>(`/projects/${projectId}/github/links`).then((res) => res.data),
  })
  const links = (data ?? []).filter((l) => l.task_id === task.id)
  const reference = taskReference(task)

  return (
    <div className="space-y-4 py-2">
      <div className="space-y-1.5">
        <p className="text-sm">
          Put <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{reference}</code> in a branch name or
          commit message and this task follows the work.
        </p>
        <p className="text-xs text-muted-foreground">
          For example: <span className="font-mono">git checkout -b fix/{reference}-retry-loop</span>
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : links.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No commits or pull requests name this task yet. They appear here after a sync.
        </p>
      ) : (
        <ul className="space-y-2">
          {links.map((link) => (
            <li key={link.id} className="flex items-start gap-2 text-sm">
              {link.kind === "commit" ? (
                <GitCommit className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              ) : (
                <GitPullRequest className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <div className="min-w-0 flex-1">
                <a href={link.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                  {link.title}
                </a>
                <p className="text-xs text-muted-foreground">
                  {link.kind === "commit" ? link.ref.slice(0, 7) : `#${link.ref}`}
                  {link.author_login ? ` · ${link.author_login}` : ""}
                  {link.authored_at ? ` · ${new Date(link.authored_at).toLocaleDateString()}` : ""}
                </p>
              </div>
              {link.state && <Badge variant="secondary">{link.state}</Badge>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
