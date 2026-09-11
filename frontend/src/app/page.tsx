"use client";
import { useCallback, useEffect, useState, useRef } from "react";
import DashboardMetrics from "../components/DashboardMetrics";
import Calendar from "../components/Calendar";
import AIAssistant from "../components/AIAssistant";
import TaskManager from "../components/TaskManager";
import TodayView from "../components/TodayView";
import { PlanResponse, Task } from "../types";
import { useToast } from "../components/ui/Toast";
import { AuroraBackground } from "../components/ui/AuroraBackground";
import { ShinyText } from "../components/ui/ShinyText";
import { useAuth } from "../hooks/useAuth";
import AuthUI from "../components/AuthUI";
import SettingsModal from "../components/SettingsModal";
import { authenticatedFetch } from "../api/apiClient";
import { API_BASE_URL } from "../api/config";
import { handleApiError } from "../utils/errors";

export default function Dashboard() {
  const { loading: authLoading, error: authError, login, register, logout, clearError, isAuthenticated } = useAuth();
  
  const [health, setHealth] = useState<string>("Checking backend...");
  const [loadingStep, setLoadingStep] = useState<string | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [viewMode, setViewMode] = useState<'today' | 'tasks' | 'calendar'>('today');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  
  const { addToast } = useToast();

  // LLM State
  const [llmInput, setLlmInput] = useState("");
  const [llmResponse, setLlmResponse] = useState<Record<string, unknown> | null>(null);
  const [llmLoadingStep, setLlmLoadingStep] = useState<string | null>(null);
  const [conversationContext, setConversationContext] = useState("");
  
  // Replan State
  const [replanInput, setReplanInput] = useState("");
  const [replanParsed, setReplanParsed] = useState<Record<string, unknown> | null>(null);
  const [replanLoadingStep, setReplanLoadingStep] = useState<string | null>(null);
  
  // Double-click prevention refs
  const isPlanSubmitting = useRef(false);
  const isLlmSubmitting = useRef(false);
  const isReplanSubmitting = useRef(false);
  const isReplanApplySubmitting = useRef(false);

  const fetchTasks = useCallback(async () => {
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/tasks/`);
      if (res.ok) {
        const data = await res.json();
        setTasks(data);
      }
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => res.json())
      .then((data) => setHealth(data.status === "ok" ? "Connected" : "Error"))
      .catch(() => setHealth("Disconnected"));
      
    if (isAuthenticated) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      fetchTasks();
    }
  }, [isAuthenticated, fetchTasks]);

  const handleCommandExecuted = async () => {
    if (isPlanSubmitting.current) return;
    isPlanSubmitting.current = true;
    setLoadingStep("Refreshing...");
    try {
      await fetchTasks();
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
      setLoadingStep(null);
      isPlanSubmitting.current = false;
    }
  };

  const handlePlanMyWeek = async () => {
    if (isPlanSubmitting.current) return;
    isPlanSubmitting.current = true;
    const startTime = performance.now();
    setLoadingStep("Building schedule...");
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/plan/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ week_start: new Date().toISOString().split('T')[0] })
      });
      if (!res.ok) {
        let errMessage = "Failed to generate plan";
        try {
           const errData = await res.json();
           if (errData.detail) {
             if (typeof errData.detail === "string" && errData.detail.includes("GENERIC_INFEASIBLE")) {
               errMessage = "Schedule couldn't be completed. You have more work requested than available time before your deadlines.\n\nWhat you can do: reduce task duration, move a deadline, or add availability.";
               addToast({ type: 'warning', title: 'Schedule Infeasible', message: errMessage, duration: 8000 });
               return;
             }
             errMessage = String(errData.detail);
           }
        } catch {}
        addToast({ type: 'error', title: 'Error', message: errMessage });
        return;
      }
      const data = await res.json();
      setPlan(data);
      const latency = Math.round(performance.now() - startTime);
      console.log(`Plan generated in ${latency}ms`);
      addToast({ type: 'success', title: 'Schedule generated', message: `Optimized in ${latency}ms` });
    } catch (e) {
      console.error(e);
      addToast({ type: 'error', title: 'Error', message: "Failed to generate plan" });
    } finally {
      setLoadingStep(null);
      isPlanSubmitting.current = false;
    }
  };

  const handleLlmSubmit = async () => {
    if (!llmInput || isLlmSubmitting.current) return;
    isLlmSubmitting.current = true;
    setLlmLoadingStep("Interpreting request...");
    const startTime = performance.now();
    
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
        await handleApiError(res, "Failed to parse with LLM");
      }
      const data = await res.json();
      setLlmResponse(data);
      
      if (data.clarification_question) {
        setConversationContext(fullPrompt + `\nSystem: ${data.clarification_question}`);
      } else {
        setConversationContext("");
      }
      console.log(`LLM Parse latency: ${Math.round(performance.now() - startTime)}ms`);
    } catch (e: unknown) {
      console.error(e);
      addToast({ type: 'error', title: 'Error', message: e instanceof Error ? e.message : "Failed to parse input" });
    } finally {
      setLlmLoadingStep(null);
      isLlmSubmitting.current = false;
    }
  };

  const handleApproveAndSave = async () => {
    if (!llmResponse || isLlmSubmitting.current) return;
    isLlmSubmitting.current = true;
    setLlmLoadingStep("Saving data...");
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
      if (!res.ok) {
        await handleApiError(res, "Failed to save data");
      }
      
      setLlmResponse(null);
      setLlmInput("");
      setConversationContext("");
      addToast({ type: 'success', title: 'Data saved successfully' });
      fetchTasks();
    } catch (e: unknown) {
      console.error(e);
      addToast({ type: 'error', title: 'Error', message: e instanceof Error ? e.message : "Failed to save data" });
    } finally {
      setLlmLoadingStep(null);
      isLlmSubmitting.current = false;
    }
  };

  const handleToggleComplete = async (taskId: number, currentStatus?: boolean) => {
    try {
      const statusToUse = currentStatus !== undefined ? currentStatus : (tasks.find(t => t.id === taskId)?.completed || false);
      const res = await authenticatedFetch(`${API_BASE_URL}/api/tasks/${taskId}/complete`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed: !statusToUse })
      });
      if (!res.ok) {
        await handleApiError(res, "Failed to update task");
      }
      
      // Re-fetch tasks
      fetchTasks();
      
      // Update local plan if present
      if (plan && !statusToUse) {
        setPlan({
          ...plan,
          scheduled_blocks: plan.scheduled_blocks.filter(b => b.task_id !== taskId)
        });
      }
      
      addToast({ type: 'success', title: !statusToUse ? 'Task completed' : 'Task restored' });
    } catch (e: unknown) {
      console.error(e);
      addToast({ type: 'error', title: 'Error', message: e instanceof Error ? e.message : "Failed to update task" });
    }
  };

  const handleReplanSubmit = async () => {
    if (!replanInput || !plan || isReplanSubmitting.current) return;
    isReplanSubmitting.current = true;
    setReplanLoadingStep("Analyzing change...");
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/replan/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: replanInput })
      });
      if (!res.ok) {
        await handleApiError(res, "Failed to parse replan input");
      }
      const data = await res.json();
      setReplanParsed(data);
    } catch (e: unknown) {
      console.error(e);
      addToast({ type: 'error', title: 'Error', message: e instanceof Error ? e.message : "Failed to parse replan input" });
    } finally {
      setReplanLoadingStep(null);
      isReplanSubmitting.current = false;
    }
  };

  const handleReplanApply = async () => {
    if (!replanParsed || isReplanApplySubmitting.current) return;
    isReplanApplySubmitting.current = true;
    setReplanLoadingStep("Applying changes...");
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/replan/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(replanParsed)
      });
      if (!res.ok) {
        await handleApiError(res, "Failed to apply replan");
      }
      const data = await res.json();
      setPlan(data.plan);
      setReplanParsed(null);
      setReplanInput("");
      addToast({ type: 'success', title: 'Schedule updated' });
    } catch (e: unknown) {
      console.error(e);
      addToast({ type: 'error', title: 'Error', message: e instanceof Error ? e.message : "Failed to apply replan" });
    } finally {
      setReplanLoadingStep(null);
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
        <header className="mb-8 flex flex-col md:flex-row md:justify-between md:items-end gap-6">
          <div>
            <ShinyText 
              text="Decision Engine" 
              className="text-3xl font-black tracking-tighter" 
            />
            <p className="text-neutral-500 text-sm mt-1 font-medium">Phase 8D: Optimization Core</p>
          </div>
          
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6 w-full md:w-auto">
            {/* View navigation */}
            <div className="flex bg-black/40 p-1 rounded-xl w-full md:w-auto">
              <button 
                onClick={() => setViewMode('today')}
                className={`flex-1 md:flex-none px-6 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${viewMode === 'today' ? 'bg-indigo-600 text-white' : 'text-neutral-500 hover:text-white'}`}
              >
                Today
              </button>
              <button 
                onClick={() => setViewMode('tasks')}
                className={`flex-1 md:flex-none px-6 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${viewMode === 'tasks' ? 'bg-indigo-600 text-white' : 'text-neutral-500 hover:text-white'}`}
              >
                Tasks
              </button>
              <button 
                onClick={() => setViewMode('calendar')}
                className={`flex-1 md:flex-none px-6 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${viewMode === 'calendar' ? 'bg-indigo-600 text-white' : 'text-neutral-500 hover:text-white'}`}
              >
                Calendar
              </button>
            </div>
            
            <div className="flex items-center gap-4 ml-auto">
                <button 
                  onClick={() => setIsSettingsOpen(true)}
                  className="text-sm text-white/60 hover:text-white transition-colors mr-4"
                >
                  Settings
                </button>
                <button 
                  onClick={logout}
                  className="text-sm text-white/60 hover:text-white transition-colors"
                >
                  Sign out
                </button>
              <button 
                onClick={handlePlanMyWeek}
                disabled={loadingStep !== null}
                className={`px-8 py-3 rounded-2xl transition-all font-bold tracking-wide relative overflow-hidden ${
                  loadingStep !== null 
                    ? 'bg-neutral-800 text-neutral-400 cursor-not-allowed' 
                    : 'bg-white text-black hover:bg-neutral-200 shadow-[0_0_20px_rgba(255,255,255,0.2)] hover:scale-[1.02]'
                }`}
              >
                {loadingStep !== null ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                    {loadingStep}
                  </span>
                ) : "PLAN MY WEEK"}
              </button>
            </div>
          </div>
        </header>

        <DashboardMetrics plan={plan} health={health} />

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 h-full mt-8">
          <div className={`xl:col-span-3 transition-opacity duration-300 ${loadingStep === "Building schedule..." ? "opacity-40" : "opacity-100"}`}>
            {viewMode === 'tasks' && <TaskManager tasks={tasks} onToggleComplete={handleToggleComplete} />}
            {viewMode === 'calendar' && <Calendar plan={plan} onToggleComplete={handleToggleComplete} />}
            {viewMode === 'today' && (
              <TodayView plan={plan} tasks={tasks} onToggleComplete={handleToggleComplete} />
            )}
          </div>
          
          <div className="xl:col-span-1 h-[600px] xl:h-[calc(100vh-250px)]">
            <AIAssistant 
              llmInput={llmInput}
              setLlmInput={setLlmInput}
              handleLlmSubmit={handleLlmSubmit}
              llmLoading={llmLoadingStep !== null}
              llmLoadingStep={llmLoadingStep}
              llmResponse={llmResponse}
              setLlmResponse={setLlmResponse}
              handleApproveAndSave={handleApproveAndSave}
              replanInput={replanInput}
              setReplanInput={setReplanInput}
              handleReplanSubmit={handleReplanSubmit}
              replanLoading={replanLoadingStep !== null}
              replanLoadingStep={replanLoadingStep}
              replanParsed={replanParsed}
              setReplanParsed={setReplanParsed}
              handleReplanApply={handleReplanApply}
              hasPlan={!!plan}
              onCommandExecuted={handleCommandExecuted}
            />
          </div>
        </div>
      </div>
      {isSettingsOpen && <SettingsModal onClose={() => setIsSettingsOpen(false)} />}
    </AuroraBackground>
  );
}
