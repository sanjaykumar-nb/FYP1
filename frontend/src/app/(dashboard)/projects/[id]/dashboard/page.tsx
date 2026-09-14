"use client"

import { useMemo } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, TrendingUp, AlertTriangle, Users, Clock, Target, RefreshCw } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { toast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import type { AgentRun, Member, PaginatedResponse, Project, Task } from "@/types"
import { AgentRunPanel } from "@/components/analytics/agent-run-panel"
import { TeamPanel } from "@/components/team/team-panel"

interface ProjectHealth {
  health_score: number
  risk_score: number
  completion_rate: number
  overdue_tasks: number
  blocked_tasks: number
  active_milestones: number
  team_size: number
  workload_balance: number
}

const statusColors: Record<string, string> = {
  backlog: "bg-gray-100 text-gray-800",
  planned: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  blocked: "bg-red-100 text-red-800",
  review: "bg-purple-100 text-purple-800",
  done: "bg-green-100 text-green-800",
}

export default function ProjectDashboardPage() {
  const params = useParams()
  const projectId = params.id as string
  const queryClient = useQueryClient()

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.get<Project>(`/projects/${projectId}`).then((res) => res.data),
  })

  const { data: tasks } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () =>
      api
        .get<PaginatedResponse<Task>>(`/projects/${projectId}/tasks`, { params: { page_size: 100 } })
        .then((res) => res.data),
  })

  const { data: health } = useQuery({
    queryKey: ["project-health", projectId],
    queryFn: () =>
      api.get<ProjectHealth>(`/analytics/projects/${projectId}/dashboard`).then((res) => res.data),
  })

  const { data: runs } = useQuery({
    queryKey: ["agent-runs", projectId],
    queryFn: () =>
      api.get<AgentRun[]>(`/analytics/projects/${projectId}/agent-runs`).then((res) => res.data),
  })

  const { data: members } = useQuery({
    queryKey: ["members", projectId],
    queryFn: () =>
      api
        .get<PaginatedResponse<Member>>(`/projects/${projectId}/members`, { params: { page_size: 100 } })
        .then((res) => res.data.items),
  })

  // Lets the AI panel name the tasks and people its findings cite.
  const taskTitles = useMemo(() => new Map((tasks?.items ?? []).map((t) => [t.id, t.title])), [tasks])
  const memberNames = useMemo(
    () => new Map((members ?? []).map((m) => [m.id, m.full_name || m.email])),
    [members]
  )

  const runAnalysis = useMutation({
    mutationFn: () => api.post<AgentRun>(`/analytics/projects/${projectId}/analyze`).then((res) => res.data),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["agent-runs", projectId] })
      if (run.status === "completed") {
        toast({ title: "Analysis complete", description: `Overall risk: ${run.coordinator_output?.overall_risk_level}`, variant: "success" })
      } else {
        toast({ title: "Analysis failed", description: run.error_message || "Unknown error", variant: "destructive" })
      }
    },
    onError: (error: any) => {
      toast({
        title: "Could not run analysis",
        description: error.response?.data?.detail || "Please try again",
        variant: "destructive",
      })
    },
  })

  if (!project) return <div className="flex items-center justify-center h-64">Loading...</div>

  const taskStatusCounts = (tasks?.items ?? []).reduce<Record<string, number>>((acc, task) => {
    acc[task.status] = (acc[task.status] || 0) + 1
    return acc
  }, {})

  const healthScore = health?.health_score ?? project.health_score ?? 0
  const riskScore = health?.risk_score ?? project.risk_score ?? 0
  const completionPct = health ? Math.round(health.completion_rate * 100) : 0
  const latestRun = runs?.[0]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <Link href="/workspace" className="text-sm text-muted-foreground hover:underline mb-2 inline-block">
            ← Back to Workspace
          </Link>
          <div className="flex items-center gap-3">
            <Badge variant="secondary">{project.key}</Badge>
            <h1 className="text-3xl font-bold">{project.name}</h1>
            <Badge variant={project.status === "active" ? "default" : "secondary"} className="ml-2">
              {project.status}
            </Badge>
          </div>
          {project.description && <p className="text-muted-foreground mt-1">{project.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => runAnalysis.mutate()} disabled={runAnalysis.isPending}>
            <RefreshCw className={`mr-2 h-4 w-4 ${runAnalysis.isPending ? "animate-spin" : ""}`} />
            {runAnalysis.isPending ? "Analyzing…" : "Run Analysis"}
          </Button>
          <Link href={`/projects/${projectId}/tasks`}>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Task
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <MetricCard title="Health Score" value={`${Math.round(healthScore * 100)}`} icon={TrendingUp} color="text-green-600" subtitle="Project health" />
        <MetricCard title="Risk Score" value={`${Math.round(riskScore * 100)}`} icon={AlertTriangle} color="text-red-600" subtitle="Overall risk" />
        <MetricCard title="Completion" value={`${completionPct}%`} icon={Target} color="text-blue-600" subtitle="Task completion" />
        <MetricCard title="Overdue" value={`${health?.overdue_tasks ?? 0}`} icon={Clock} color="text-yellow-600" subtitle="Overdue tasks" />
        <MetricCard title="Team" value={`${health?.team_size ?? 0}`} icon={Users} color="text-purple-600" subtitle="Active members" />
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="team">Team</TabsTrigger>
          <TabsTrigger value="ai">AI Insights</TabsTrigger>
        </TabsList>

        <TabsContent value="team" className="space-y-6">
          <TeamPanel projectId={projectId} />
        </TabsContent>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Progress Overview</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Overall Progress</span>
                    <span className="font-medium">{completionPct}%</span>
                  </div>
                  <Progress value={completionPct} className="h-3" />
                </div>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-2xl font-bold">{taskStatusCounts.in_progress || 0}</p>
                    <p className="text-xs text-muted-foreground">In Progress</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{taskStatusCounts.done || 0}</p>
                    <p className="text-xs text-muted-foreground">Done</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{taskStatusCounts.blocked || 0}</p>
                    <p className="text-xs text-muted-foreground">Blocked</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Health & Risk</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-green-50 dark:bg-green-950/30 rounded-lg">
                    <p className="text-sm text-muted-foreground">Health Score</p>
                    <p className="text-3xl font-bold text-green-600">{Math.round(healthScore * 100)}</p>
                  </div>
                  <div className="p-4 bg-red-50 dark:bg-red-950/30 rounded-lg">
                    <p className="text-sm text-muted-foreground">Risk Score</p>
                    <p className="text-3xl font-bold text-red-600">{Math.round(riskScore * 100)}</p>
                  </div>
                </div>
                {health && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Workload Balance</span>
                      <span className="font-medium">{Math.round(health.workload_balance * 100)}%</span>
                    </div>
                    <Progress value={Math.round(health.workload_balance * 100)} className="h-2" />
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <TimelineItem label="Project Started" date={project.start_date ? new Date(project.start_date).toLocaleDateString() : "Not set"} icon={Target} />
                <TimelineItem label="Target End Date" date={project.target_end_date ? new Date(project.target_end_date).toLocaleDateString() : "Not set"} icon={Target} isCurrent />
                {project.actual_end_date && (
                  <TimelineItem label="Completed" date={new Date(project.actual_end_date).toLocaleDateString()} icon={TrendingUp} isCompleted />
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Recent Tasks</CardTitle>
              <Link href={`/projects/${projectId}/tasks`} className="text-sm text-primary hover:underline">
                View all →
              </Link>
            </CardHeader>
            <CardContent>
              {(() => {
                const recentTasks = tasks?.items?.slice(0, 5) ?? []
                if (recentTasks.length === 0) {
                  return (
                    <p className="text-center text-muted-foreground py-8">
                      No tasks yet.{" "}
                      <Link href={`/projects/${projectId}/tasks`} className="text-primary hover:underline">
                        Create your first task
                      </Link>
                    </p>
                  )
                }
                return (
                  <div className="space-y-3">
                    {recentTasks.map((task) => (
                      <div key={task.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <Badge variant="outline" className={statusColors[task.status] || ""}>
                            {task.status.replace("_", " ")}
                          </Badge>
                          <div>
                            <p className="font-medium">{task.title}</p>
                            <p className="text-sm text-muted-foreground">
                              {task.story_points ? `${task.story_points} pts` : "No estimate"} · {task.priority} priority
                            </p>
                          </div>
                        </div>
                        {task.due_date && (
                          <Badge variant="outline" className="text-xs">
                            Due: {new Date(task.due_date).toLocaleDateString()}
                          </Badge>
                        )}
                      </div>
                    ))}
                  </div>
                )
              })()}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tasks" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Task Board</h2>
            <Link href={`/projects/${projectId}/tasks`}>
              <Button>Open Full Board</Button>
            </Link>
          </div>
        </TabsContent>

        <TabsContent value="ai" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">AI Insights</h2>
            <Button variant="outline" onClick={() => runAnalysis.mutate()} disabled={runAnalysis.isPending}>
              <RefreshCw className={`mr-2 h-4 w-4 ${runAnalysis.isPending ? "animate-spin" : ""}`} />
              {runAnalysis.isPending ? "Analyzing…" : "Run Analysis"}
            </Button>
          </div>
          {latestRun ? (
            <AgentRunPanel run={latestRun} taskTitles={taskTitles} memberNames={memberNames} />
          ) : (
            <Card>
              <CardContent className="p-8 text-center">
                <AlertTriangle className="h-12 w-12 text-muted-foreground/30 mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No AI Analysis Run Yet</h3>
                <p className="text-muted-foreground mb-4">
                  Run the multi-agent analysis to get predictive risk scores and recommendations.
                </p>
                <Button onClick={() => runAnalysis.mutate()} disabled={runAnalysis.isPending}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${runAnalysis.isPending ? "animate-spin" : ""}`} />
                  {runAnalysis.isPending ? "Analyzing…" : "Run Analysis Now"}
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function MetricCard({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  title: string
  value: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  subtitle: string
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          </div>
          <div className="p-3 bg-muted rounded-xl">
            <Icon className={`h-6 w-6 ${color}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function TimelineItem({
  label,
  date,
  icon: Icon,
  isCurrent,
  isCompleted,
}: {
  label: string
  date: string
  icon: React.ComponentType<{ className?: string }>
  isCurrent?: boolean
  isCompleted?: boolean
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isCurrent ? "bg-primary text-primary-foreground" : isCompleted ? "bg-green-500 text-white" : "bg-muted text-muted-foreground"
        }`}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 pt-1">
        <p className="font-medium">{label}</p>
        <p className="text-sm text-muted-foreground">{date}</p>
      </div>
    </div>
  )
}
