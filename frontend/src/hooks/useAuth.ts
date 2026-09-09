import { useState, useEffect } from "react";
import { API_BASE_URL } from "../api/config";
import { authenticatedFetch, setAccessToken, getAccessToken } from "../api/apiClient";

export interface User {
  id: string;
  email: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize session (attempt silent refresh)
  useEffect(() => {
    let mounted = true;

    const init = async () => {
      try {
        const refreshRes = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });

        if (refreshRes.ok) {
          const data = await refreshRes.json();
          setAccessToken(data.access_token);

          // Now fetch user details
          const meRes = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
          if (meRes.ok) {
            const userData = await meRes.json();
            if (mounted) setUser(userData);
          }
        }
      } catch (err) {
        console.error("Auth init error:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    init();

    const handleLogoutEvent = () => {
      setUser(null);
      setAccessToken(null);
    };

    window.addEventListener("auth-logout", handleLogoutEvent);
    return () => {
      mounted = false;
      window.removeEventListener("auth-logout", handleLogoutEvent);
    };
  }, []);

  const login = async (email: string, password: string) => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Invalid email or password.");
      }

      const data = await res.json();
      setAccessToken(data.access_token);

      const meRes = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
      if (meRes.ok) {
        const userData = await meRes.json();
        setUser(userData);
      } else {
        throw new Error("Failed to load user profile.");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred during login.");
      throw err;
    }
  };

  const register = async (email: string, password: string) => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        credentials: "include",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Registration failed.");
      }

      // Auto-login after registration
      await login(email, password);
    } catch (err: any) {
      setError(err.message || "An error occurred during registration.");
      throw err;
    }
  };

  const logout = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch (err) {
      // Ignore network errors on logout
    } finally {
      setUser(null);
      setAccessToken(null);
    }
  };

  return {
    user,
    loading,
    error,
    login,
    register,
    logout,
    clearError: () => setError(null),
    isAuthenticated: !!user && !!getAccessToken(),
  };
}
