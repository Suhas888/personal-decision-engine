"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AuroraBackground } from "../../components/ui/AuroraBackground";
import { ShinyText } from "../../components/ui/ShinyText";
import { useToast } from "../../components/ui/Toast";
import { API_BASE_URL } from "../../api/config";

function ResetPasswordForm() {
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const { addToast } = useToast();
  const router = useRouter();

  useEffect(() => {
    if (!token) {
      addToast({
        title: "Invalid link",
        message: "No reset token found in the URL.",
        type: "error",
      });
    }
  }, [token, addToast]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !password) return;

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });

      if (res.ok) {
        addToast({
          title: "Password Reset",
          message: "Your password has been successfully reset.",
          type: "success",
        });
        setSuccess(true);
        // Remove token from URL for security
        window.history.replaceState(null, "", "/reset-password");
        
        setTimeout(() => {
          router.push("/");
        }, 3000);
      } else {
        const data = await res.json().catch(() => ({}));
        addToast({
          title: "Error",
          message: data.detail || "Failed to reset password. The link may have expired.",
          type: "error",
        });
      }
    } catch {
      addToast({
        title: "Network Error",
        message: "Could not reach the server.",
        type: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!token && !success) {
    return (
      <div className="w-full max-w-sm mt-4 bg-black/40 backdrop-blur-md p-8 rounded-2xl border border-white/10 shadow-2xl text-center">
        <div className="text-red-400 mb-4">Invalid or missing reset token.</div>
        <Link href="/" className="text-gray-400 hover:text-white hover:underline transition-colors">
          &larr; Back to Login
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="w-full max-w-sm mt-4 bg-black/40 backdrop-blur-md p-8 rounded-2xl border border-white/10 shadow-2xl text-center">
        <div className="text-green-400 mb-4">Your password has been reset successfully!</div>
        <div className="text-gray-300 mb-6">Redirecting you to login...</div>
        <Link href="/" className="text-blue-400 hover:text-blue-300 hover:underline transition-colors">
          Go to Login now
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full max-w-sm mt-4 bg-black/40 backdrop-blur-md p-8 rounded-2xl border border-white/10 shadow-2xl">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">New Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-black/50 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            placeholder="••••••••"
            required
            minLength={8}
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-4 bg-white dark:bg-white text-black px-4 py-2 rounded-full font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
        >
          <ShinyText text={isSubmitting ? "Resetting..." : "Reset Password"} />
        </button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuroraBackground>
      <div className="relative flex flex-col gap-4 items-center justify-center px-4 w-full h-full">
        <div className="text-3xl md:text-5xl font-bold dark:text-white text-center">
          Choose a New Password
        </div>
        
        <Suspense fallback={<div className="text-gray-400">Loading...</div>}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </AuroraBackground>
  );
}
