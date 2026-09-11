import React from 'react';
import { PlanResponse } from '../types';
import { SpotlightCard } from './ui/SpotlightCard';
import { Activity, Clock, AlertCircle } from 'lucide-react';
import { ShinyText } from './ui/ShinyText';

interface DashboardMetricsProps {
  plan: PlanResponse | null;
  health: string;
}

export default function DashboardMetrics({ plan, health }: DashboardMetricsProps) {
  const isHealthy = health === "Connected";
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <SpotlightCard className="p-5 bg-surface border-subtle">
        <div className="flex items-center gap-2 mb-3 text-muted">
          <Activity className="w-4 h-4 text-blue-400" />
          <h3 className="text-[10px] font-bold uppercase tracking-widest">System Status</h3>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${isHealthy ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-red-500'}`} />
          <span className={`text-xl font-medium tracking-tight ${isHealthy ? 'text-white' : 'text-red-400'}`}>{health}</span>
        </div>
      </SpotlightCard>
      
      <SpotlightCard className="p-5 md:col-span-2 bg-surface border-subtle">
        <div className="flex items-center gap-2 mb-3 text-muted">
          <Clock className="w-4 h-4 text-accent-brand" />
          <h3 className="text-[10px] font-bold uppercase tracking-widest">Weekly Progress</h3>
        </div>
        <div className="flex items-end gap-3 mb-4">
          <ShinyText 
            text={`${plan ? Math.round(plan.completion_percentage) : 0}%`}
            className="text-3xl font-bold tracking-tighter" 
          />
          <div className="text-xs text-muted mb-1 font-medium bg-white/5 px-2 py-0.5 rounded-md">
            {plan ? `${Math.round(plan.total_scheduled_minutes / 60)}h Scheduled` : '0h Scheduled'}
          </div>
        </div>
        <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden shadow-inner">
          <div 
            className="h-full bg-accent-brand rounded-full transition-all duration-1000 ease-out"
            style={{ width: `${plan ? plan.completion_percentage : 0}%` }}
          ></div>
        </div>
      </SpotlightCard>
      
      <SpotlightCard className="p-5 bg-surface border-subtle">
        <div className="flex items-center gap-2 mb-3 text-muted">
          <AlertCircle className="w-4 h-4 text-amber-500" />
          <h3 className="text-[10px] font-bold uppercase tracking-widest">Unscheduled</h3>
        </div>
        <p className={`text-3xl font-bold tracking-tighter ${plan && plan.unscheduled_tasks.length > 0 ? 'text-amber-500' : 'text-white'}`}>
          {plan ? plan.unscheduled_tasks.length : '--'}
        </p>
      </SpotlightCard>
    </div>
  );
}
