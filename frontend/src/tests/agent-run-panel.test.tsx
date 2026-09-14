import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentRunPanel, citationLabel } from '@/components/analytics/agent-run-panel'
import type { AgentEvidence, AgentRun } from '@/types'

const TASK = '11111111-1111-1111-1111-111111111111'
const PERSON = '22222222-2222-2222-2222-222222222222'
const taskTitles = new Map([[TASK, 'MESOS-8383: Fix the agent reconnect loop']])
const memberNames = new Map([[PERSON, 'Contributor #3409']])

function runWithRisk(metadata: Record<string, unknown>, evidence: AgentEvidence[] = []): AgentRun {
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
      merged_recommendations: [],
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
          risk_scores: { delay: 'low', workload: 'high' },
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
