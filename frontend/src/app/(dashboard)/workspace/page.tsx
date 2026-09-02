"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, FolderKanban, AlertTriangle, LayoutDashboard, List } from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { toast } from "@/hooks/use-toast"
import { api } from "@/lib/api"
import type { PaginatedResponse, Project } from "@/types"

const createProjectSchema = z.object({
  name: z.string().min(1, "Name is required"),
  key: z
    .string()
    .min(1, "Key is required")
    .max(10, "Key must be 10 characters or fewer")
    .regex(/^[A-Za-z0-9]+$/, "Key must be alphanumeric"),
  description: z.string().optional(),
})
type CreateProjectForm = z.infer<typeof createProjectSchema>

export default function WorkspacePage() {
  const [view, setView] = useState<"grid" | "list">("grid")

  const { data, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () =>
      api.get<PaginatedResponse<Project>>("/projects").then((res) => res.data),
  })

  const projects = data?.items ?? []
  const activeCount = projects.filter((p) => p.status === "active").length
  const atRiskCount = projects.filter((p) => (p.risk_score ?? 0) >= 0.4).length

  const stats = [
    { label: "Total Projects", value: String(data?.total ?? 0), icon: FolderKanban, color: "bg-blue-500" },
    { label: "Active", value: String(activeCount), icon: LayoutDashboard, color: "bg-green-500" },
    { label: "At Risk", value: String(atRiskCount), icon: AlertTriangle, color: "bg-yellow-500" },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workspace</h1>
          <p className="text-muted-foreground">Manage your projects and track team intelligence</p>
        </div>
        <NewProjectDialog />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label} className="hover:shadow-md transition-shadow">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
                  <p className="text-3xl font-bold">{stat.value}</p>
                </div>
                <div className={`p-3 rounded-xl ${stat.color}`}>
                  <stat.icon className="h-6 w-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Projects</h2>
        <div className="flex items-center gap-2">
          <Button variant={view === "grid" ? "secondary" : "outline"} size="sm" onClick={() => setView("grid")}>
            <LayoutDashboard className="h-4 w-4" />
          </Button>
          <Button variant={view === "list" ? "secondary" : "outline"} size="sm" onClick={() => setView("list")}>
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground py-8 text-center">Loading projects…</p>
      ) : projects.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <FolderKanban className="h-12 w-12 text-muted-foreground/30 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No projects yet</h3>
            <p className="text-muted-foreground mb-4">Create your first project to start tracking work.</p>
            <NewProjectDialog />
          </CardContent>
        </Card>
      ) : view === "grid" ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {projects.map((project) => (
            <ProjectListItem key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  )
}

function scoreColor(score: number | null, invert = false): string {
  const v = score ?? 0
  const good = invert ? v < 0.3 : v > 0.7
  const bad = invert ? v >= 0.5 : v <= 0.4
  if (good) return "text-green-600"
  if (bad) return "text-red-600"
  return "text-yellow-600"
}

function ProjectCard({ project }: { project: Project }) {
  return (
    <Link href={`/projects/${project.id}/dashboard`}>
      <Card className="hover:shadow-md transition-shadow h-full flex flex-col">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <Badge variant="secondary" className="mb-2">{project.key}</Badge>
              <h3 className="text-lg font-semibold">{project.name}</h3>
              {project.description && (
                <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
              )}
            </div>
            <Badge variant={project.status === "active" ? "default" : "secondary"}>
              {project.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col justify-between">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Health Score</p>
              <p className={`text-xl font-bold ${scoreColor(project.health_score)}`}>
                {project.health_score != null ? Math.round(project.health_score * 100) : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Risk Score</p>
              <p className={`text-xl font-bold ${scoreColor(project.risk_score, true)}`}>
                {project.risk_score != null ? Math.round(project.risk_score * 100) : "—"}
              </p>
            </div>
          </div>
          {project.target_end_date && (
            <div className="border-t border-border pt-4 mt-4 text-sm">
              <span className="text-muted-foreground">Target: </span>
              {new Date(project.target_end_date).toLocaleDateString()}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}

function ProjectListItem({ project }: { project: Project }) {
  return (
    <Link href={`/projects/${project.id}/dashboard`}>
      <Card className="hover:shadow-md transition-shadow">
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <Badge variant="secondary" className="w-16 text-center">{project.key}</Badge>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold truncate">{project.name}</h3>
              {project.description && (
                <p className="text-sm text-muted-foreground truncate">{project.description}</p>
              )}
            </div>
            <Badge variant={project.status === "active" ? "default" : "secondary"}>
              {project.status}
            </Badge>
            <div className="w-24 text-right text-sm">
              <span className={scoreColor(project.health_score)}>
                Health: {project.health_score != null ? Math.round(project.health_score * 100) : "—"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function NewProjectDialog() {
  const [open, setOpen] = useState(false)
  const router = useRouter()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateProjectForm>({ resolver: zodResolver(createProjectSchema) })

  const createProject = useMutation({
    mutationFn: (data: CreateProjectForm) => api.post<Project>("/projects", data).then((res) => res.data),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast({ title: "Project created", variant: "success" })
      setOpen(false)
      reset()
      router.push(`/projects/${project.id}/dashboard`)
    },
    onError: (error: any) => {
      toast({
        title: "Failed to create project",
        description: error.response?.data?.detail || "Please try again",
        variant: "destructive",
      })
    },
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit((data) => createProject.mutate(data))} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" placeholder="Website Redesign" {...register("name")} />
            {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="key">Key</Label>
            <Input id="key" placeholder="WEB" {...register("key")} />
            {errors.key && <p className="text-sm text-destructive">{errors.key.message}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input id="description" placeholder="Optional" {...register("description")} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={createProject.isPending}>
              {createProject.isPending ? "Creating…" : "Create Project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
