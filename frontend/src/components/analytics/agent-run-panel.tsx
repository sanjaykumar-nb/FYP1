import { AlertTriangle, CheckCircle2, Lightbulb, Network, ShieldAlert } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { AgentRun, GraphFinding, RiskLevel } from "@/types"

const RISK_STYLES: Record<RiskLevel, { badge: string; icon: string }> = {
  low: { badge: "bg-green-100 text-green-800 dark:bg-green-950/50 dark:text-green-400", icon: "text-green-600" },
  medium: { badge: "bg-yellow-100 text-yellow-800 dark:bg-yellow-950/50 dark:text-yellow-400", icon: "text-yellow-600" },
  high: { badge: "bg-orange-100 text-orange-800 dark:bg-orange-950/50 dark:text-orange-400", icon: "text-orange-600" },
  critical: { badge: "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-400", icon: "text-red-600" },
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  const style = RISK_STYLES[level] ?? RISK_STYLES.low
  return <Badge className={style.badge}>{level}</Badge>
}

const SPECIALIST_LABELS: Record<string, string> = {
  planning: "Planning",
  progress: "Progress",
  workload: "Workload",
  risk: "Risk",
  recommendation: "Recommendation",
  meetings: "Meeting Intelligence",
  communication: "Communication Intelligence",
}

const RISK_TYPE_LABELS: Record<string, string> = {
  delay: "Delay",
  workload: "Workload",
  knowledge: "Knowledge concentration",
  dependency: "Dependencies",
  coordination: "Coordination",
  silent_member: "Silent members",
}

const MAX_CITED = 8

type Finding = Partial<GraphFinding> & { title: string; node_ids: string[] }

/** Turns a graph citation ("task:<uuid>", "person:<uuid>") into something a person can read. */
export function citationLabel(
  nodeId: string,
  taskTitles: Map<string, string>,
  memberNames: Map<string, string>
): { label: string; title?: string } {
  const sep = nodeId.indexOf(":")
  const kind = sep === -1 ? "" : nodeId.slice(0, sep)
  const id = nodeId.slice(sep + 1)
  if (kind === "task") {
    const title = taskTitles.get(id)
    if (!title) return { label: "unknown task" }
    // Imported issues are titled "KEY-123: summary"; the key is the compact handle.
    const key = title.match(/^([A-Z][A-Z0-9]*-\d+):/)
    return { label: key ? key[1] : title, title }
  }
  if (kind === "person") {
    const name = memberNames.get(id)
    return name ? { label: name, title: name } : { label: "former member" }
  }
  return { label: kind || nodeId, title: nodeId }
}

function formatValue(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

export function AgentRunPanel({
  run,
  taskTitles = new Map(),
  memberNames = new Map(),
}: {
  run: AgentRun
  taskTitles?: Map<string, string>
  memberNames?: Map<string, string>
}) {
  if (run.status === "failed") {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <AlertTriangle className="h-12 w-12 text-destructive/60 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Analysis Failed</h3>
          <p className="text-muted-foreground">{run.error_message || "Unknown error"}</p>
        </CardContent>
      </Card>
    )
  }

  const output = run.coordinator_output
  if (!output) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-muted-foreground">
          Analysis is still running…
        </CardContent>
      </Card>
    )
  }

  const specialists = Object.entries(output.specialist_outputs).filter(
    ([key]) => key !== "risk" && key !== "recommendation"
  )
  const recommendations = output.merged_recommendations ?? []

  const risk = output.specialist_outputs.risk
  const riskScores = risk?.risk_scores ?? {}
  const graphStats = risk?.metadata?.graph_stats as { nodes: number; edges: number } | undefined
  const findings: Finding[] =
    (risk?.metadata?.findings as GraphFinding[] | undefined) ??
    // Runs saved before full findings were stored keep one citation per finding.
    (risk?.evidence ?? []).map((e) => ({ title: e.excerpt, node_ids: [e.reference_id] }))

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5" />
              Overall Risk
            </CardTitle>
            <RiskBadge level={output.overall_risk_level} />
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{output.overall_summary}</p>
          <p className="text-xs text-muted-foreground mt-2">
            Confidence: {Math.round(output.overall_confidence * 100)}%
          </p>
        </CardContent>
      </Card>

      {risk && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Network className="h-5 w-5" />
              Why: evidence from the project graph
            </CardTitle>
            {graphStats && (
              <p className="text-sm text-muted-foreground">
                Scores are computed from a graph of {graphStats.nodes} nodes and {graphStats.edges} links built from
                this project&apos;s tasks, people, dependencies and comments. Each finding names what it rests on.
              </p>
            )}
          </CardHeader>
          <CardContent className="space-y-5">
            {Object.keys(riskScores).length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {Object.entries(RISK_TYPE_LABELS)
                  .filter(([key]) => key in riskScores)
                  .map(([key, label]) => (
                    <div key={key} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                      <span className="text-sm">{label}</span>
                      <RiskBadge level={riskScores[key]} />
                    </div>
                  ))}
              </div>
            )}

            {findings.length === 0 ? (
              <p className="text-sm text-muted-foreground">The graph shows nothing that needs attention.</p>
            ) : (
              <ul className="space-y-3">
                {findings.map((finding, i) => (
                  <li key={i} className="p-3 bg-muted/50 rounded-lg space-y-2">
                    {(finding.severity || finding.risk_type) && (
                      <div className="flex flex-wrap items-center gap-2">
                        {finding.severity && <RiskBadge level={finding.severity} />}
                        {finding.risk_type && (
                          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            {RISK_TYPE_LABELS[finding.risk_type] ?? finding.risk_type}
                          </span>
                        )}
                      </div>
                    )}
                    <p className="font-medium">{finding.title}</p>
                    {finding.metric && finding.value != null && (
                      <p className="text-xs text-muted-foreground font-mono">
                        {`${finding.metric} = ${formatValue(finding.value)}`}
                      </p>
                    )}
                    {finding.node_ids.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">Based on:</span>
                        {finding.node_ids.slice(0, MAX_CITED).map((nodeId) => {
                          const cited = citationLabel(nodeId, taskTitles, memberNames)
                          return (
                            <Badge key={nodeId} variant="outline" title={cited.title} className="font-normal max-w-[16rem] truncate">
                              {cited.label}
                            </Badge>
                          )
                        })}
                        {finding.node_ids.length > MAX_CITED && (
                          <span className="text-xs text-muted-foreground">
                            +{finding.node_ids.length - MAX_CITED} more
                          </span>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {specialists.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {specialists.map(([key, agent]) => (
            <Card key={key}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{SPECIALIST_LABELS[key] || key}</CardTitle>
                  <RiskBadge level={agent.risk_level} />
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{agent.summary}</p>
                {agent.next_action && agent.next_action !== "None" && (
                  <p className="text-xs mt-2">
                    <span className="text-muted-foreground">Next: </span>
                    {agent.next_action}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent>
          {recommendations.length === 0 ? (
            <div className="flex items-center gap-2 text-muted-foreground py-4">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              No significant risks found — nothing to recommend.
            </div>
          ) : (
            <div className="space-y-3">
              {recommendations.map((rec, i) => (
                <div key={i} className="p-3 bg-muted/50 rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-medium">{rec.title}</p>
                    <Badge variant={rec.priority === "high" ? "destructive" : "secondary"}>
                      {rec.priority}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{rec.description}</p>
                  <p className="text-xs text-muted-foreground mt-1 italic">{rec.reasoning}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
