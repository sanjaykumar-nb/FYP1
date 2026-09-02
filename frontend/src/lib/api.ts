import axios from "axios"

// The origin only (no /api/v1) — used directly by the raw refresh-token call
// below, which deliberately bypasses the `api` instance to avoid re-entering
// its own interceptors.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token")
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      
      try {
        const refreshToken = localStorage.getItem("refresh_token")
        if (refreshToken) {
          const response = await axios.post(
            `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/auth/refresh`,
            { refresh_token: refreshToken }
          )
          
          const { access_token, refresh_token: newRefreshToken } = response.data
          localStorage.setItem("access_token", access_token)
          localStorage.setItem("refresh_token", newRefreshToken)
          
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
        window.location.href = "/login"
        return Promise.reject(refreshError)
      }
    }
    
    return Promise.reject(error)
  }
)

export { api }