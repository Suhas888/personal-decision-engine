import React from 'react';
import { PlanResponse } from '../types';
import { SpotlightCard } from './ui/SpotlightCard';
import { Activity, Clock, AlertCircle } from 'lucide-react';

interface DashboardMetricsProps {
  plan: PlanResponse | null;
  health: string;
}

export default function DashboardMetrics({ plan, health }: DashboardMetricsProps) {
  const isHealthy = health === "Connected";
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <SpotlightCard className="p-6">
        <div className="flex items-center gap-3 mb-4 text-neutral-400">
          <Activity className="w-5 h-5 text-blue-400" />
          <h3 className="text-xs font-bold uppercase tracking-widest">System Status</h3>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${isHealthy ? 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.8)]' : 'bg-red-500'}`} />
          <span className={`text-2xl font-light ${isHealthy ? 'text-emerald-50' : 'text-red-400'}`}>{health}</span>
        </div>
      </SpotlightCard>
      
      <SpotlightCard className="p-6 md:col-span-2">
        <div className="flex items-center gap-3 mb-4 text-neutral-400">
          <Clock className="w-5 h-5 text-indigo-400" />
          <h3 className="text-xs font-bold uppercase tracking-widest">Weekly Progress</h3>
        </div>
        <div className="flex items-end gap-3 mb-3">
          <p className="text-3xl font-light text-white">{plan ? Math.round(plan.completion_percentage) : 0}<span className="text-neutral-500 text-xl ml-1">%</span></p>
          <div className="text-sm text-neutral-500 mb-1 font-medium">
            {plan ? `${Math.round(plan.total_scheduled_minutes / 60)}h Scheduled` : '0h Scheduled'}
          </div>
        </div>
        <div className="h-1.5 w-full bg-black/50 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-indigo-500 to-blue-400 rounded-full transition-all duration-1000 ease-out"
            style={{ width: `${plan ? plan.completion_percentage : 0}%` }}
          ></div>
        </div>
      </SpotlightCard>
      
      <SpotlightCard className="p-6">
        <div className="flex items-center gap-3 mb-4 text-neutral-400">
          <AlertCircle className="w-5 h-5 text-amber-400" />
          <h3 className="text-xs font-bold uppercase tracking-widest">Unscheduled</h3>
        </div>
        <p className={`text-4xl font-light ${plan && plan.unscheduled_tasks.length > 0 ? 'text-amber-400' : 'text-white'}`}>
          {plan ? plan.unscheduled_tasks.length : '--'}
        </p>
      </SpotlightCard>
    </div>
  );
}
