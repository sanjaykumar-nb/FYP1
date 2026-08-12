"use client"

import { useParams } from "next/navigation"
import Link from "next/link"
import { Plus, TrendingUp, AlertTriangle, Users, Clock, Target, ArrowRight, RefreshCw } from "lucide-react"
import { Card } from "@/components/ui/card"
import { CardContent } from "@/components/ui/card"
import { CardHeader } from "@/components/ui/card"
import { CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { useQuery } from "@tanstack/react-query"

interface Project {
  id: string
  name: string
  key: string
  description: string
  status: string
  healthScore: number
  riskScore: number
  startDate: string
  targetEndDate: string
  actualEndDate: string | null
  createdAt: string
}

interface Task {
  id: string
  title: string
  status: string
  priority: string
  storyPoints: number | null
  assigneeId: string | null
  dueDate: string | null
}

export default function ProjectDashboardPage() {
  const params = useParams()
  const projectId = params.id as string
  
  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.get(`/projects/${projectId}`).then(res => res.data),
  })
  
  const { data: tasks } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => api.get(`/projects/${projectId}/tasks`).then(res => res.data),
  })
  
  const { data: health } = useQuery({
    queryKey: ["project-health", projectId],
    queryFn: () => api.get(`/analytics/projects/${projectId}/dashboard`).then(res => res.data),
  })

  if (!project) return <div className="flex items-center justify-center h-64">Loading...</div>

  const statusColors: Record<string, string> = {
    backlog: "bg-gray-100 text-gray-800",
    planned: "bg-blue-100 text-blue-800",
    in_progress: "bg-yellow-100 text-yellow-800",
    blocked: "bg-red-100 text-red-800",
    review: "bg-purple-100 text-purple-800",
    done: "bg-green-100 text-green-800",
  }

  const priorityColors: Record<string, string> = {
    low: "bg-gray-100 text-gray-800",
    medium: "bg-blue-100 text-blue-800",
    high: "bg-orange-100 text-orange-800",
    critical: "bg-red-100 text-red-800",
  }

  const taskStatusCounts = tasks?.items?.reduce((acc: Record<string, number>, task: Task) => {
    acc[task.status] = (acc[task.status] || 0) + 1
    return acc
  }, {}) || {}

  return (
    <div className="space-y-6">
      {/* Project Header */}
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
          <p className="text-muted-foreground mt-1">{project.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Run Analysis
          </Button>
          <Link href={`/projects/${projectId}/tasks`}>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Task
            </Button>
          </Link>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          title="Health Score"
          value={`${Math.round((health?.healthScore || project.healthScore || 0) * 100)}`}
          icon={TrendingUp}
          color="text-green-600"
          subtitle="Project health"
        />
        <MetricCard
          title="Risk Score"
          value={`${Math.round((health?.riskScore || project.riskScore || 0) * 100)}`}
          icon={AlertTriangle}
          color="text-red-600"
          subtitle="Overall risk"
        />
        <MetricCard
          title="Completion"
          value={`${health?.completionRate ? Math.round(health.completionRate * 100) : 0}%`}
          icon={Target}
          color="text-blue-600"
          subtitle="Task completion"
        />
        <MetricCard
          title="Overdue"
          value={`${health?.overdueTasks || 0}`}
          icon={Clock}
          color="text-yellow-600"
          subtitle="Overdue tasks"
        />
        <MetricCard
          title="Team"
          value={`${health?.teamSize || 0}`}
          icon={Users}
          color="text-purple-600"
          subtitle="Active members"
        />
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="ai">AI Insights</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Progress & Health */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Progress Overview</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Overall Progress</span>
                    <span className="font-medium">{health?.completionRate ? Math.round(health.completionRate * 100) : 0}%</span>
                  </div>
                  <Progress value={health?.completionRate ? Math.round(health.completionRate * 100) : 0} className="h-3" />
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
                  <div className="p-4 bg-green-50 rounded-lg">
                    <p className="text-sm text-muted-foreground">Health Score</p>
                    <p className="text-3xl font-bold text-green-600">
                      {Math.round((health?.healthScore || project.healthScore || 0) * 100)}
                    </p>
                  </div>
                  <div className="p-4 bg-red-50 rounded-lg">
                    <p className="text-sm text-muted-foreground">Risk Score</p>
                    <p className="text-3xl font-bold text-red-600">
                      {Math.round((health?.riskScore || project.riskScore || 0) * 100)}
                    </p>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Workload Balance</span>
                    <span className="font-medium">{Math.round((health?.workloadBalance || 0.8) * 100)}%</span>
                  </div>
                  <Progress value={Math.round((health?.workloadBalance || 0.8) * 100)} className="h-2" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <TimelineItem
                  label="Project Started"
                  date={project.startDate ? new Date(project.startDate).toLocaleDateString() : "Not set"}
                  icon={Target}
                />
                <TimelineItem
                  label="Target End Date"
                  date={project.targetEndDate ? new Date(project.targetEndDate).toLocaleDateString() : "Not set"}
                  icon={Target}
                  isCurrent
                />
                {project.actualEndDate && (
                  <TimelineItem
                    label="Completed"
                    date={new Date(project.actualEndDate).toLocaleDateString()}
                    icon={TrendingUp}
                    isCompleted
                  />
                )}
              </CardContent>
            </Card>
          </div>

          {/* Recent Tasks */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Recent Tasks</CardTitle>
              <Link href={`/projects/${projectId}/tasks`} className="text-sm text-primary hover:underline">
                View all →
              </Link>
            </CardHeader>
            <CardContent>
              {(() => {
                const recentTasks = tasks?.items?.slice(0, 5) || []
                if (recentTasks.length === 0) {
                  return (
                    <p className="text-center text-muted-foreground py-8">No tasks yet. <Link href={`/projects/${projectId}/tasks`} className="text-primary hover:underline">Create your first task</Link></p>
                  )
                }
                return (
                  <div className="space-y-3">
                    {recentTasks.map((task: Task) => (
                      <div key={task.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                        <div className="flex items-center gap-3">
                          <Badge variant="outline" className={statusColors[task.status] || ""}>
                            {task.status.replace("_", " ")}
                          </Badge>
                          <div>
                            <p className="font-medium">{task.title}</p>
                            <p className="text-sm text-muted-foreground">
                              {task.storyPoints ? `${task.storyPoints} pts` : "No estimate"} • 
                              {task.priority} priority
                            </p>
                          </div>
                        </div>
                        {task.dueDate && (
                          <Badge variant="outline" className="text-xs">
                            Due: {new Date(task.dueDate).toLocaleDateString()}
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
          <p className="text-muted-foreground">View the full Kanban board at <Link href={`/projects/${projectId}/tasks`} className="text-primary hover:underline">/tasks</Link></p>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Analytics</h2>
            <Link href={`/projects/${projectId}/analytics`}>
              <Button>View Full Analytics</Button>
            </Link>
          </div>
          <p className="text-muted-foreground">View detailed analytics at <Link href={`/projects/${projectId}/analytics`} className="text-primary hover:underline">/analytics</Link></p>
        </TabsContent>

        <TabsContent value="ai" className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">AI Insights</h2>
            <Button variant="outline">
              <RefreshCw className="mr-2 h-4 w-4" />
              Run Analysis
            </Button>
          </div>
          <Card>
            <CardContent className="p-8 text-center">
              <AlertTriangle className="h-12 w-12 text-muted-foreground/30 mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">No AI Analysis Run Yet</h3>
              <p className="text-muted-foreground mb-4">Run the multi-agent analysis to get predictive insights, risk scores, and recommendations.</p>
              <Button>
                <RefreshCw className="mr-2 h-4 w-4" />
                Run Analysis Now
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function MetricCard({ title, value, icon: Icon, color, subtitle }: { title: string; value: string; icon: React.ComponentType<{ className?: string }>; color: string; subtitle: string }) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold {color}">{value}</p>
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          </div>
          <div className="p-3 bg-muted rounded-xl">
            <Icon className="h-6 w-6 {color}" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function TimelineItem({ label, date, icon: Icon, isCurrent, isCompleted }: { label: string; date: string; icon: React.ComponentType<{ className?: string }>; isCurrent?: boolean; isCompleted?: boolean }) {
  return (
    <div className="flex items-start gap-3">
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isCurrent ? "bg-primary text-primary-foreground" : isCompleted ? "bg-green-500 text-white" : "bg-muted text-muted-foreground"}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 pt-1">
        <p className="font-medium">{label}</p>
        <p className="text-sm text-muted-foreground">{date}</p>
      </div>
    </div>
  )
}