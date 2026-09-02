/** Thin localStorage-backed auth helpers shared by the route guard and pages. */

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem("access_token")
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null
}

export function clearTokens(): void {
  localStorage.removeItem("access_token")
  localStorage.removeItem("refresh_token")
}

export function logout(): void {
  clearTokens()
  window.location.href = "/login"
}
