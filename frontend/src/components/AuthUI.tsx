import React, { useState } from "react";
import { AuroraBackground } from "./ui/AuroraBackground";
import { ShinyText } from "./ui/ShinyText";

interface AuthUIProps {
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string) => Promise<void>;
  error: string | null;
  clearError: () => void;
}

export default function AuthUI({ login, register, error, clearError }: AuthUIProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    
    setIsSubmitting(true);
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(email, password);
      }
    } catch (err) {
      // Error is handled by the hook
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    clearError();
    setEmail("");
    setPassword("");
  };

  return (
    <AuroraBackground>
      <div className="relative flex flex-col gap-4 items-center justify-center px-4">
        <div className="text-3xl md:text-5xl font-bold dark:text-white text-center">
          Personal Decision Engine
        </div>
        <div className="font-extralight text-base md:text-2xl dark:text-neutral-200 py-2">
          {isLogin ? "Welcome back" : "Create your account"}
        </div>
        
        <div className="w-full max-w-sm mt-4 bg-black/40 backdrop-blur-md p-8 rounded-2xl border border-white/10 shadow-2xl">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-black/50 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-black/50 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <div className="text-red-400 text-sm mt-1 bg-red-900/20 px-3 py-2 rounded-md border border-red-900/50">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-4 bg-white dark:bg-white text-black px-4 py-2 rounded-full font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
            >
              <ShinyText text={isSubmitting ? "Processing..." : (isLogin ? "Sign In" : "Sign Up")} />
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-gray-400">
            {isLogin ? "Don't have an account? " : "Already have an account? "}
            <button
              onClick={toggleMode}
              disabled={isSubmitting}
              className="text-white hover:underline focus:outline-none"
            >
              {isLogin ? "Sign Up" : "Sign In"}
            </button>
          </div>
        </div>
      </div>
    </AuroraBackground>
  );
}
