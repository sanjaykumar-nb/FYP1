"use client"

import { useState } from "react"
import Link from "next/link"
import { Plus, FolderKanban, BarChart3, Calendar, Users, TrendingUp, Clock, AlertTriangle, Brain, LayoutDashboard, List, Lightbulb } from "lucide-react"
import { Card } from "@/components/ui/card"
import { CardContent } from "@/components/ui/card"
import { CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { formatDistanceToNow } from "date-fns"

const mockProjects = [
  {
    id: "1",
    name: "Website Redesign",
    key: "WEB",
    description: "Complete redesign of company website",
    status: "active",
    healthScore: 0.85,
    riskScore: 0.15,
    progress: 65,
    teamSize: 5,
    targetEndDate: "2024-03-15",
    lastActivity: "2 hours ago",
  },
  {
    id: "2",
    name: "Mobile App v2.0",
    key: "MOB",
    description: "Next version of mobile application",
    status: "active",
    healthScore: 0.72,
    riskScore: 0.28,
    progress: 40,
    teamSize: 8,
    targetEndDate: "2024-04-30",
    lastActivity: "30 minutes ago",
  },
  {
    id: "3",
    name: "API Platform",
    key: "API",
    description: "Internal API platform modernization",
    status: "active",
    healthScore: 0.55,
    riskScore: 0.45,
    progress: 25,
    teamSize: 4,
    targetEndDate: "2024-05-15",
    lastActivity: "1 day ago",
  },
]

const stats = [
  { label: "Active Projects", value: "3", icon: FolderKanban, color: "bg-blue-500" },
  { label: "Team Members", value: "17", icon: Users, color: "bg-green-500" },
  { label: "Open Risks", value: "5", icon: AlertTriangle, color: "bg-yellow-500" },
  { label: "AI Insights", value: "12", icon: Brain, color: "bg-purple-500" },
]

export default function WorkspacePage() {
  const [view, setView] = useState<"grid" | "list">("grid")
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workspace</h1>
          <p className="text-muted-foreground">Manage your projects and track team intelligence</p>
        </div>
        <Link href="/projects/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Button>
        </Link>
      </div>
      
      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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
      
      {/* Projects */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Projects</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setView("grid")}>
            <LayoutDashboard className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setView("list")}>
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>
      
      {view === "grid" ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {mockProjects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {mockProjects.map((project) => (
            <ProjectListItem key={project.id} project={project} />
          ))}
        </div>
      )}
      
      {/* Quick Actions */}
      <div className="grid gap-4 md:grid-cols-3">
        <QuickActionCard
          title="Run AI Analysis"
          description="Trigger multi-agent analysis on a project"
          icon={Brain}
          href="/analytics"
        />
        <QuickActionCard
          title="View Recommendations"
          description="Check AI-generated recommendations"
          icon={Lightbulb}
          href="/recommendations"
        />
        <QuickActionCard
          title="Team Intelligence Index"
          description="See overall team health scores"
          icon={TrendingUp}
          href="/analytics"
        />
      </div>
    </div>
  )
}

function ProjectCard({ project }: { project: typeof mockProjects[0] }) {
  const healthColor = project.healthScore > 0.7 ? "text-green-600" : project.healthScore > 0.5 ? "text-yellow-600" : "text-red-600"
  const riskColor = project.riskScore < 0.3 ? "text-green-600" : project.riskScore < 0.5 ? "text-yellow-600" : "text-red-600"
  
  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="hover:shadow-md transition-shadow h-full flex flex-col">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <Badge variant="secondary" className="mb-2">{project.key}</Badge>
              <h3 className="text-lg font-semibold">{project.name}</h3>
              <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
            </div>
            <Badge variant={project.status === "active" ? "default" : "secondary"}>
              {project.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col justify-between">
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>Progress</span>
                <span className="font-medium">{project.progress}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary rounded-full transition-all" 
                  style={{ width: `${project.progress}%` }}
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Health Score</p>
                <p className={`text-xl font-bold ${healthColor}`}>{Math.round(project.healthScore * 100)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Risk Score</p>
                <p className={`text-xl font-bold ${riskColor}`}>{Math.round(project.riskScore * 100)}</p>
              </div>
            </div>
          </div>
          
          <div className="border-t border-border pt-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Team</span>
              <span>{project.teamSize} members</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Target</span>
              <span>{new Date(project.targetEndDate).toLocaleDateString()}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Last activity</span>
              <span>{project.lastActivity}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function ProjectListItem({ project }: { project: typeof mockProjects[0] }) {
  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="hover:shadow-md transition-shadow">
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <Badge variant="secondary" className="w-16 text-center">{project.key}</Badge>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold truncate">{project.name}</h3>
              <p className="text-sm text-muted-foreground truncate">{project.description}</p>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>{project.progress}% complete</span>
              <Badge variant={project.status === "active" ? "default" : "secondary"} className="ml-2">
                {project.status}
              </Badge>
            </div>
            <div className="flex items-center gap-4 w-48">
              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${project.progress}%` }} />
              </div>
            </div>
            <div className="w-32 text-right">
              <span className="text-sm font-medium">Health: {Math.round(project.healthScore * 100)}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function QuickActionCard({ title, description, icon: Icon, href }: { title: string; description: string; icon: React.ComponentType<{ className?: string }>; href: string }) {
  return (
    <Link href={href}>
      <Card className="hover:shadow-md transition-shadow h-full">
        <CardContent className="p-6 flex flex-col">
          <div className="p-3 bg-primary/10 text-primary rounded-xl w-fit mb-4">
            <Icon className="h-6 w-6" />
          </div>
          <h3 className="font-semibold mb-1">{title}</h3>
          <p className="text-sm text-muted-foreground flex-1">{description}</p>
        </CardContent>
      </Card>
    </Link>
  )
}