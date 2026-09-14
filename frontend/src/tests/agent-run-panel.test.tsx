import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { AgentRunPanel, citationLabel } from '@/components/analytics/agent-run-panel'
import type { AgentEvidence, AgentRecommendation, AgentRun, RecommendedAction, RiskLevel } from '@/types'

const TASK = '11111111-1111-1111-1111-111111111111'
const PERSON = '22222222-2222-2222-2222-222222222222'
const taskTitles = new Map([[TASK, 'MESOS-8383: Fix the agent reconnect loop']])
const memberNames = new Map([[PERSON, 'Contributor #3409']])

function runWithRisk(
  metadata: Record<string, unknown>,
  evidence: AgentEvidence[] = [],
  extra: { recommendations?: AgentRecommendation[]; riskScores?: Record<string, RiskLevel> } = {}
): AgentRun {
  return {
    id: 'run-1',
    project_id: 'project-1',
    triggered_by: null,
    trigger_type: 'manual',
    status: 'completed',
    specialist_outputs: null,
    final_recommendations: null,
    execution_time_ms: 12,
    error_message: null,
    created_at: '2026-01-01T00:00:00Z',
    completed_at: '2026-01-01T00:00:01Z',
    coordinator_output: {
      project_id: 'project-1',
      overall_summary: 'Overall risk: high',
      overall_risk_level: 'high',
      overall_confidence: 0.7,
      merged_recommendations: extra.recommendations ?? [],
      next_actions: [],
      specialist_outputs: {
        risk: {
          summary: '',
          risk_level: 'high',
          confidence: 0.9,
          signals: [],
          evidence,
          recommendations: [],
          next_action: '',
          metadata,
          risk_scores: extra.riskScores ?? { delay: 'low', workload: 'high' },
        },
      },
    },
  }
}

describe('AgentRunPanel graph evidence', () => {
  it('names the tasks and people behind each finding', () => {
    const run = runWithRisk({
      graph_stats: { nodes: 46, edges: 160 },
      findings: [
        {
          risk_type: 'workload',
          severity: 'high',
          title: 'Contributor #3409 carries 9 open points vs a team mean of 3.8',
          metric: 'workload_skew',
          value: 2.3427,
          node_ids: [`person:${PERSON}`, `task:${TASK}`],
        },
      ],
    })
    render(<AgentRunPanel run={run} taskTitles={taskTitles} memberNames={memberNames} />)

    expect(screen.getByText(/46 nodes and 160 links/)).toBeInTheDocument()
    expect(screen.getByText('workload_skew = 2.34')).toBeInTheDocument()
    expect(screen.getByText('Contributor #3409')).toBeInTheDocument()
    expect(screen.getByText('MESOS-8383')).toHaveAttribute('title', 'MESOS-8383: Fix the agent reconnect loop')
  })

  it('shows only the risk types the run scored', () => {
    render(<AgentRunPanel run={runWithRisk({ findings: [] })} />)
    expect(screen.getByText('Delay')).toBeInTheDocument()
    expect(screen.queryByText('Knowledge concentration')).not.toBeInTheDocument()
    expect(screen.getByText('The graph shows nothing that needs attention.')).toBeInTheDocument()
  })

  it('falls back to single citations for runs saved before findings were stored', () => {
    const run = runWithRisk({}, [
      { source: 'graph', reference_id: `task:${TASK}`, excerpt: '1 of 1 open tasks are past their due date', relevance: 0.9 },
    ])
    render(<AgentRunPanel run={run} taskTitles={taskTitles} memberNames={memberNames} />)

    expect(screen.getByText('1 of 1 open tasks are past their due date')).toBeInTheDocument()
    expect(screen.getByText('MESOS-8383')).toBeInTheDocument()
  })
})

describe('citationLabel', () => {
  it('keeps unresolved citations readable', () => {
    expect(citationLabel(`task:${TASK}`, new Map(), new Map()).label).toBe('unknown task')
    expect(citationLabel(`person:${PERSON}`, new Map(), new Map()).label).toBe('former member')
    expect(citationLabel(`task:${TASK}`, new Map([[TASK, 'Untracked chore']]), new Map()).label).toBe('Untracked chore')
  })
})

const OTHER = '33333333-3333-3333-3333-333333333333'
const THIRD = '44444444-4444-4444-4444-444444444444'
const names = new Map([[PERSON, 'Contributor #3409'], [OTHER, 'Contributor #3415']])
const move: RecommendedAction = {
  kind: 'reassign',
  task_id: `task:${TASK}`,
  from_person: `person:${PERSON}`,
  to_person: `person:${OTHER}`,
  points: 3,
  summary: 'Move MESOS-8383',
}
const redistribute: AgentRecommendation = {
  type: 'redistribute',
  title: 'Redistribute workload',
  description: 'Contributor #3409 carries 9 open points',
  reasoning: 'Uneven workload increases delay and burnout risk',
  priority: 'high',
  confidence: 0.75,
  actions: [move],
  expected_effect: 'Heaviest open load falls from 9 to 6 points',
}

describe('AgentRunPanel suggested reassignments', () => {
  const run = () => runWithRisk({ findings: [] }, [], { recommendations: [redistribute] })
  const panel = (assignee: string, onApply = vi.fn()) => (
    <AgentRunPanel
      run={run()}
      taskTitles={taskTitles}
      memberNames={names}
      taskAssignees={new Map([[TASK, assignee]])}
      onApplyAction={onApply}
    />
  )

  it('describes the move and applies it on request', () => {
    const onApply = vi.fn()
    render(panel(PERSON, onApply))

    expect(screen.getByText('Move MESOS-8383 (3 pts) from Contributor #3409 to Contributor #3415')).toBeInTheDocument()
    expect(screen.getByText(/falls from 9 to 6 points/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApply).toHaveBeenCalledWith(move)
  })

  it('shows a move as applied once the task has the new assignee', () => {
    render(panel(OTHER))
    expect(screen.getByText('Applied')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
    expect(screen.getByText('Run the analysis again to measure the effect.')).toBeInTheDocument()
  })

  it('will not apply a move the board has overtaken', () => {
    render(panel(THIRD))
    expect(screen.getByText('Changed since this analysis')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Apply' })).not.toBeInTheDocument()
  })
})

describe('AgentRunPanel comparison with the previous run', () => {
  it('marks the risk scores that changed', () => {
    const previous = runWithRisk({ findings: [] }, [], { riskScores: { delay: 'low', workload: 'critical' } })
    render(<AgentRunPanel run={runWithRisk({ findings: [] })} previousRun={previous} />)

    expect(screen.getByText('was critical')).toBeInTheDocument()
    expect(screen.queryByText('was low')).not.toBeInTheDocument()
  })
})
