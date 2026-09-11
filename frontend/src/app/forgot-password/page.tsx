"use client";

import React, { useState } from "react";
import Link from "next/link";
import { AuroraBackground } from "../../components/ui/AuroraBackground";
import { ShinyText } from "../../components/ui/ShinyText";
import { useToast } from "../../components/ui/Toast";
import { API_BASE_URL } from "../../api/config";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { addToast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (res.ok) {
        addToast({
          title: "Reset link sent",
          message: "If that email exists, a reset link has been sent.",
          type: "success",
        });
        setEmail("");
      } else {
        const data = await res.json().catch(() => ({}));
        addToast({
          title: "Error",
          message: data.detail || "Failed to request password reset",
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

  return (
    <AuroraBackground>
      <div className="relative flex flex-col gap-4 items-center justify-center px-4 w-full h-full">
        <div className="text-3xl md:text-5xl font-bold dark:text-white text-center">
          Reset Password
        </div>
        <div className="font-extralight text-base md:text-xl dark:text-neutral-200 py-2 text-center max-w-sm">
          Enter your email address and we&apos;ll send you a link to reset your password.
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

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-4 bg-white dark:bg-white text-black px-4 py-2 rounded-full font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
            >
              <ShinyText text={isSubmitting ? "Sending..." : "Send Reset Link"} />
            </button>
          </form>

          <div className="mt-6 text-center text-sm">
            <Link href="/" className="text-gray-400 hover:text-white hover:underline transition-colors">
              &larr; Back to Login
            </Link>
          </div>
        </div>
      </div>
    </AuroraBackground>
  );
}
