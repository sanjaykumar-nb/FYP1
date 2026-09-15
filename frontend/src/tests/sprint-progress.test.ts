import { describe, it, expect } from 'vitest'
import { sprintProgress } from '@/components/sprints/sprints-panel'
import type { Milestone, Task } from '@/types'

const sprint: Milestone = {
  id: 'sprint-1',
  project_id: 'p',
  name: 'Sprint 1',
  description: null,
  start_date: '2026-09-01T00:00:00',
  target_date: '2026-09-11T00:00:00',
  status: 'upcoming',
  progress: 0,
  completed_at: null,
  created_at: '2026-08-30T00:00:00',
}

function task(id: string, status: Task['status'], points: number | null, milestone_id: string | null = 'sprint-1'): Task {
  return {
    id, project_id: 'p', milestone_id, parent_task_id: null, assignee_id: null, reporter_id: 'r',
    title: id, description: null, status, priority: 'medium', story_points: points, estimated_hours: null,
    actual_hours: 0, due_date: null, blocked_reason: null, position: 0, started_at: null, completed_at: null,
    created_at: '2026-09-01T00:00:00',
  }
}

describe('sprintProgress', () => {
  const tasks = [
    task('big', 'done', 8),
    task('small', 'in_progress', 1),
    task('unestimated', 'backlog', null),
    task('elsewhere', 'done', 13, 'other-sprint'),
  ]

  it('weighs work like the analysis: story points, each task counting at least 1', () => {
    const p = sprintProgress(sprint, tasks, new Date('2026-09-06T00:00:00'))
    expect(p.tasks).toBe(3)
    expect(p.open).toBe(2)
    expect(p.workDone).toBeCloseTo(0.8)
  })

  it('reports how much of the schedule has passed', () => {
    const p = sprintProgress(sprint, tasks, new Date('2026-09-06T00:00:00'))
    expect(p.timeElapsed).toBeCloseTo(0.5)
    expect(p.phase).toBe('active')
  })

  it('names the phase before, after, and without a schedule', () => {
    expect(sprintProgress(sprint, tasks, new Date('2026-08-20T00:00:00')).phase).toBe('upcoming')
    expect(sprintProgress(sprint, tasks, new Date('2026-09-20T00:00:00')).phase).toBe('ended')
    const unscheduled = sprintProgress({ ...sprint, start_date: null }, tasks, new Date('2026-09-06T00:00:00'))
    expect(unscheduled.phase).toBe('unscheduled')
    expect(unscheduled.timeElapsed).toBeNull()
  })

  it('treats an empty sprint as nothing done', () => {
    expect(sprintProgress(sprint, [], new Date('2026-09-06T00:00:00')).workDone).toBe(0)
  })
})
