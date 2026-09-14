"use client"

import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { Member } from "@/types"

// Mirrors ROLE_RANK in backend/app/core/permissions.py: nobody grants a role above their own.
export const ROLE_RANK: Record<string, number> = {
  viewer: 0,
  developer: 1,
  project_manager: 2,
  admin: 3,
  owner: 4,
}

export function hasPermission(permissions: string[] | undefined, permission: string): boolean {
  return !!permissions && (permissions.includes("*") || permissions.includes(permission))
}

export function grantableRoles(role: string | undefined, roles: string[]): string[] {
  const rank = ROLE_RANK[role ?? ""] ?? -1
  return roles.filter((r) => (ROLE_RANK[r] ?? Number.POSITIVE_INFINITY) <= rank)
}

/**
 * The signed-in person's role. `can` stays false until it has loaded, so controls
 * never flash on for someone who cannot use them. The API enforces the same rules.
 */
export function usePermissions() {
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<Member>("/auth/me").then((res) => res.data),
    staleTime: 5 * 60 * 1000,
  })
  return {
    me,
    role: me?.role,
    can: (permission: string) => hasPermission(me?.permissions, permission),
  }
}
