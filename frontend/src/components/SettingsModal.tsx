import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../api/config';
import { authenticatedFetch } from '../api/apiClient';
import { useToast } from './ui/Toast';
import { X, RefreshCw, Unplug } from 'lucide-react';

interface CalendarStatus {
  isConnected: boolean;
  provider?: string;
  providerEmail?: string;
  lastSyncedAt?: string;
}

export default function SettingsModal({ onClose }: { onClose: () => void }) {
  const [calendarStatus, setCalendarStatus] = useState<CalendarStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const { addToast } = useToast();

  const fetchStatus = async () => {
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/calendar/status`);
      if (res.ok) {
        const data = await res.json();
        setCalendarStatus(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchStatus();
  }, []);

  const handleConnect = async () => {
    // Redirect to the backend auth flow
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = `${API_BASE_URL}/api/calendar/auth/google`;
  };

  const handleDisconnect = async () => {
    if (!confirm("Are you sure you want to disconnect Google Calendar and remove all imported events?")) return;
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/calendar/disconnect`, { method: "DELETE" });
      if (res.ok) {
        addToast({ title: "Disconnected", message: "Google Calendar has been disconnected.", type: "success" });
        await fetchStatus();
      } else {
        addToast({ title: "Error", message: "Failed to disconnect", type: "error" });
      }
    } catch {
      addToast({ title: "Error", message: "Network error", type: "error" });
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/calendar/sync`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        addToast({ 
          title: "Sync Successful", 
          message: `Synced ${data.synced_count} events.`, 
          type: "success" 
        });
        await fetchStatus();
      } else {
        addToast({ title: "Sync Failed", message: "Failed to sync calendar", type: "error" });
      }
    } catch {
      addToast({ title: "Sync Failed", message: "Network error", type: "error" });
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-surface border border-subtle rounded-2xl p-6 w-full max-w-md shadow-2xl relative overflow-hidden">
        {/* Background flare effect */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-accent-brand/10 blur-[50px] pointer-events-none rounded-full" />
        
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-muted hover:text-white transition-colors bg-white/5 hover:bg-white/10 p-2 rounded-full"
        >
          <X className="w-4 h-4" />
        </button>
        <h2 className="text-xl font-bold text-white mb-6 tracking-tight">Settings</h2>

        <div className="space-y-6 relative z-10">
          {/* Calendar Integration Section */}
          <section className="bg-surface-hover border border-subtle p-5 rounded-xl">
            <h3 className="text-xs font-bold text-muted mb-4 uppercase tracking-widest">Integrations</h3>
            
            {isLoading ? (
              <div className="text-muted text-sm flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" /> Loading status...
              </div>
            ) : calendarStatus?.isConnected ? (
              <div className="space-y-5">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-white font-medium flex items-center gap-2">
                      <svg viewBox="0 0 24 24" className="w-4 h-4 text-blue-400" fill="currentColor">
                        <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z" />
                      </svg>
                      Google Calendar Connected
                    </div>
                    <div className="text-muted text-sm mt-1">{calendarStatus.providerEmail}</div>
                    <div className="text-muted/60 text-xs mt-2 font-mono">
                      Last sync: {calendarStatus.lastSyncedAt ? new Date(calendarStatus.lastSyncedAt).toLocaleString() : 'Never'}
                    </div>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button 
                    onClick={handleSync}
                    disabled={isSyncing}
                    className="flex-1 py-2.5 bg-accent-brand/10 hover:bg-accent-brand/20 border border-accent-brand/20 text-accent-brand rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
                    {isSyncing ? "Syncing..." : "Sync Now"}
                  </button>
                  <button 
                    onClick={handleDisconnect}
                    className="flex-1 py-2.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 rounded-xl text-sm font-medium transition-colors flex items-center justify-center gap-2"
                  >
                    <Unplug className="w-4 h-4" />
                    Disconnect
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <p className="text-sm text-muted mb-5 leading-relaxed">
                  Connect your Google Calendar to sync read-only events into your Personal Decision Engine plan.
                </p>
                <button 
                  onClick={handleConnect}
                  className="w-full py-3 bg-white text-black font-bold rounded-xl flex items-center justify-center gap-3 hover:bg-neutral-200 transition-colors shadow-lg shadow-white/10"
                >
                  <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor">
                    <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z" />
                  </svg>
                  Connect Google Calendar
                </button>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
