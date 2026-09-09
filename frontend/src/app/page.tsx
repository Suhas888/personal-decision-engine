"use client";
import { useEffect, useState, useRef } from "react";
import DashboardMetrics from "../components/DashboardMetrics";
import Calendar from "../components/Calendar";
import AIAssistant from "../components/AIAssistant";
import { PlanResponse } from "../types";
import { AuroraBackground } from "../components/ui/AuroraBackground";
import { ShinyText } from "../components/ui/ShinyText";
import { useAuth } from "../hooks/useAuth";
import AuthUI from "../components/AuthUI";
import { authenticatedFetch } from "../api/apiClient";
import { API_BASE_URL } from "../api/config";

export default function Dashboard() {
  const { user, loading: authLoading, error: authError, login, register, logout, clearError, isAuthenticated } = useAuth();
  
  const [health, setHealth] = useState<string>("Checking backend...");
  const [loading, setLoading] = useState(false);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  
  // LLM State
  const [llmInput, setLlmInput] = useState("");
  const [llmResponse, setLlmResponse] = useState<Record<string, unknown> | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [conversationContext, setConversationContext] = useState("");
  
  // Replan State
  const [replanInput, setReplanInput] = useState("");
  const [replanParsed, setReplanParsed] = useState<Record<string, unknown> | null>(null);
  const [replanLoading, setReplanLoading] = useState(false);
  
  // Double-click prevention refs
  const isPlanSubmitting = useRef(false);
  const isLlmSubmitting = useRef(false);
  const isReplanSubmitting = useRef(false);
  const isReplanApplySubmitting = useRef(false);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => res.json())
      .then((data) => setHealth(data.status === "ok" ? "Connected" : "Error"))
      .catch(() => setHealth("Disconnected"));
  }, []);

  const handleCommandExecuted = async () => {
    if (isPlanSubmitting.current) return;
    isPlanSubmitting.current = true;
    setLoading(true);
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/plan/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ week_start: new Date().toISOString().split('T')[0] })
      });
      if (res.ok) {
        const data = await res.json();
        setPlan(data);
      }
    } catch {
      // Silent refresh failure
    } finally {
      setLoading(false);
      isPlanSubmitting.current = false;
    }
  };

  const handlePlanMyWeek = async () => {
    if (isPlanSubmitting.current) return;
    isPlanSubmitting.current = true;
    setLoading(true);
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/plan/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ week_start: new Date().toISOString().split('T')[0] })
      });
      const data = await res.json();
      setPlan(data);
    } catch (e) {
      console.error(e);
      alert("Failed to generate plan");
    } finally {
      setLoading(false);
      isPlanSubmitting.current = false;
    }
  };

  const handleLlmSubmit = async () => {
    if (!llmInput || isLlmSubmitting.current) return;
    isLlmSubmitting.current = true;
    setLlmLoading(true);
    
    const fullPrompt = conversationContext 
      ? `${conversationContext}\nUser answers: ${llmInput}`
      : llmInput;
      
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/llm/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: fullPrompt })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Network or server error." }));
        throw new Error(errData.detail || "Failed to parse with LLM");
      }
      const data = await res.json();
      setLlmResponse(data);
      
      if (data.clarification_question) {
        setConversationContext(fullPrompt + `\nSystem: ${data.clarification_question}`);
      } else {
        setConversationContext("");
      }
    } catch (e: unknown) {
      console.error(e);
      alert(e instanceof Error ? e.message : "Failed to parse input");
    } finally {
      setLlmLoading(false);
      isLlmSubmitting.current = false;
    }
  };

  const handleApproveAndSave = async () => {
    if (!llmResponse || isLlmSubmitting.current) return;
    isLlmSubmitting.current = true;
    setLlmLoading(true);
    try {
      const payload = {
        tasks: llmResponse.tasks || [],
        fixed_events: llmResponse.fixed_events || llmResponse.events || [],
        preferences: llmResponse.preferences || {},
        clarification_needed: false
      };
      
      const res = await authenticatedFetch(`${API_BASE_URL}/api/llm/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Failed to save data");
      
      setLlmResponse(null);
      setLlmInput("");
      setConversationContext("");
    } catch (e: unknown) {
      console.error(e);
      alert(e instanceof Error ? e.message : "Failed to save data");
    } finally {
      setLlmLoading(false);
      isLlmSubmitting.current = false;
    }
  };

  const handleReplanSubmit = async () => {
    if (!replanInput || !plan || isReplanSubmitting.current) return;
    isReplanSubmitting.current = true;
    setReplanLoading(true);
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/replan/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: replanInput
        })
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Network or server error." }));
        throw new Error(errData.detail || "Failed to parse replan input");
      }
      const data = await res.json();
      setReplanParsed(data);
    } catch (e: unknown) {
      console.error(e);
      alert(e instanceof Error ? e.message : "Failed to parse replan input");
    } finally {
      setReplanLoading(false);
      isReplanSubmitting.current = false;
    }
  };

  const handleReplanApply = async () => {
    if (!replanParsed || isReplanApplySubmitting.current) return;
    isReplanApplySubmitting.current = true;
    setReplanLoading(true);
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/replan/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(replanParsed)
      });
      if (!res.ok) throw new Error("Failed to apply replan");
      const data = await res.json();
      setPlan(data.plan);
      setReplanParsed(null);
      setReplanInput("");
    } catch (e: unknown) {
      console.error(e);
      alert(e instanceof Error ? e.message : "Failed to apply replan");
    } finally {
      setReplanLoading(false);
      isReplanApplySubmitting.current = false;
    }
  };

  if (authLoading) {
    return (
      <AuroraBackground>
        <div className="flex flex-col items-center justify-center h-screen">
          <ShinyText text="Initializing..." className="text-3xl font-black" />
        </div>
      </AuroraBackground>
    );
  }

  if (!isAuthenticated) {
    return <AuthUI login={login} register={register} error={authError} clearError={clearError} />;
  }

  return (
    <AuroraBackground className="p-4 md:p-8 font-sans">
      <div className="w-full max-w-screen-2xl mx-auto relative z-10">
        <header className="mb-8 flex flex-col md:flex-row md:justify-between md:items-center gap-4">
          <div>
            <ShinyText 
              text="Decision Engine" 
              className="text-3xl font-black tracking-tighter" 
            />
            <p className="text-neutral-500 text-sm mt-1 font-medium">Phase 8B: Intelligence UI</p>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-400">
              {user?.email}
            </div>
            <button
              onClick={logout}
              className="text-sm text-white/60 hover:text-white transition-colors"
            >
              Sign out
            </button>
            <button 
              onClick={handlePlanMyWeek}
              disabled={loading}
              className={`px-8 py-3 rounded-2xl transition-all font-bold tracking-wide ${
                loading 
                  ? 'bg-neutral-800 text-neutral-500 cursor-not-allowed' 
                  : 'bg-white text-black hover:bg-neutral-200 shadow-[0_0_20px_rgba(255,255,255,0.2)] hover:scale-[1.02]'
              }`}
            >
              {loading ? "OPTIMIZING..." : "PLAN MY WEEK"}
            </button>
          </div>
        </header>

        <DashboardMetrics plan={plan} health={health} />

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 h-full mt-8">
          <div className="xl:col-span-3">
            <Calendar plan={plan} />
          </div>
          
          <div className="xl:col-span-1 h-[600px] xl:h-auto">
            <AIAssistant 
              llmInput={llmInput}
              setLlmInput={setLlmInput}
              handleLlmSubmit={handleLlmSubmit}
              llmLoading={llmLoading}
              llmResponse={llmResponse}
              setLlmResponse={setLlmResponse}
              handleApproveAndSave={handleApproveAndSave}
              replanInput={replanInput}
              setReplanInput={setReplanInput}
              handleReplanSubmit={handleReplanSubmit}
              replanLoading={replanLoading}
              replanParsed={replanParsed}
              setReplanParsed={setReplanParsed}
              handleReplanApply={handleReplanApply}
              hasPlan={!!plan}
              onCommandExecuted={handleCommandExecuted}
            />
          </div>
        </div>
      </div>
    </AuroraBackground>
  );
}
