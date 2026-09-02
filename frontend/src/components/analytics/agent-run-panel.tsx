import { AlertTriangle, CheckCircle2, Lightbulb, ShieldAlert } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { AgentRun, RiskLevel } from "@/types"

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

export function AgentRunPanel({ run }: { run: AgentRun }) {
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
