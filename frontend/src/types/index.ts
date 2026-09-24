// Mirrors backend/app/schemas/*.py response shapes. Kept in sync by hand —
// there is no shared package between the frontend and backend.

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface Project {
  id: string
  organization_id: string
  team_id: string | null
  name: string
  description: string | null
  key: string
  status: string
  start_date: string | null
  target_end_date: string | null
  actual_end_date: string | null
  health_score: number | null
  risk_score: number | null
  sprint_capacity_points: number | null
  /** "owner/name" of the GitHub repository this project's work lands in. */
  github_repo: string | null
  created_at: string
}

export interface Member {
  id: string
  organization_id: string
  email: string
  full_name: string | null
  role?: string
  permissions?: string[]
  github_username?: string | null
}

// A sprint or milestone. With a start date, the analysis can tell whether its work is on pace.
export interface Milestone {
  id: string
  project_id: string
  name: string
  description: string | null
  start_date: string | null
  target_date: string
  status: string
  progress: number
  completed_at: string | null
  created_at: string
}

export type TaskStatus = "backlog" | "planned" | "in_progress" | "blocked" | "review" | "done"
export type TaskPriority = "low" | "medium" | "high" | "critical"

export interface Task {
  id: string
  project_id: string
  milestone_id: string | null
  parent_task_id: string | null
  assignee_id: string | null
  reporter_id: string
  title: string
  description: string | null
  /** The code area or module the task touches. */
  component?: string | null
  status: TaskStatus
  priority: TaskPriority
  story_points: number | null
  estimated_hours: number | null
  actual_hours: number
  due_date: string | null
  blocked_reason: string | null
  position: number
  started_at: string | null
  completed_at: string | null
  created_at: string
  /** What to write in a branch name or commit message so GitHub sync finds this task. */
  reference?: string
}

/** A commit or pull request that named a task, found by GitHub sync. */
export interface GithubLink {
  id: string
  task_id: string
  kind: "commit" | "pull_request"
  ref: string
  url: string
  title: string
  author_login: string | null
  state: string | null
  authored_at: string | null
}

export interface GithubSyncResult {
  repository: string
  commits_read: number
  commits_matched: number
  pull_requests_read: number
  pull_requests_matched: number
  links_added: number
  tasks_moved: { task_id: string; title: string; from: string; to: string; because: string }[]
}

export interface TaskDependency {
  id: string
  project_id: string
  blocking_task_id: string
  blocked_task_id: string
  dependency_type: string
  created_at: string
}

export interface TaskComment {
  id: string
  task_id: string
  user_id: string
  author_name: string | null
  content: string
  created_at: string
}

export const TASK_STATUSES: { value: TaskStatus; label: string }[] = [
  { value: "backlog", label: "Backlog" },
  { value: "planned", label: "Planned" },
  { value: "in_progress", label: "In Progress" },
  { value: "blocked", label: "Blocked" },
  { value: "review", label: "Review" },
  { value: "done", label: "Done" },
]

export type RiskLevel = "low" | "medium" | "high" | "critical"

export interface AgentSignal {
  name: string
  value: number | string
  weight: number
}

export interface AgentEvidence {
  source: string
  reference_id: string
  excerpt: string
  relevance: number
}

// One graph-computed finding, stored on the risk agent's metadata. node_ids are
// "task:<uuid>" / "person:<uuid>" references to the nodes that witness it.
export interface GraphFinding {
  risk_type: string
  severity: RiskLevel
  title: string
  metric: string
  value: number
  node_ids: string[]
}

// A concrete change carrying out a recommendation; ids are graph node ids.
export interface RecommendedAction {
  kind: string
  task_id: string
  from_person: string | null
  to_person: string | null
  points: number | null
  summary: string
}

export interface AgentRecommendation {
  type: string
  title: string
  description: string
  reasoning: string
  priority: string
  confidence: number
  actions?: RecommendedAction[]
  expected_effect?: string | null
}

export interface AgentOutput {
  summary: string
  risk_level: RiskLevel
  confidence: number
  signals: AgentSignal[]
  evidence: AgentEvidence[]
  recommendations: AgentRecommendation[]
  next_action: string
  metadata: Record<string, unknown>
  risk_scores?: Record<string, RiskLevel>
  [key: string]: unknown
}

export interface CoordinatorOutput {
  project_id: string
  overall_summary: string
  overall_risk_level: RiskLevel
  overall_confidence: number
  specialist_outputs: Record<string, AgentOutput>
  merged_recommendations: AgentRecommendation[]
  next_actions: string[]
}

export interface AgentRun {
  id: string
  project_id: string
  triggered_by: string | null
  trigger_type: string | null
  status: "running" | "completed" | "failed"
  coordinator_output: CoordinatorOutput | null
  specialist_outputs: Record<string, AgentOutput> | null
  final_recommendations: { items: AgentRecommendation[] } | null
  execution_time_ms: number | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}
