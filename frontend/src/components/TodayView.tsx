import React from 'react';
import { PlanResponse, Task, ScheduleBlock } from '../types';
import { CheckCircle2, Circle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface TodayViewProps {
  plan: PlanResponse | null;
  tasks: Task[];
  onToggleComplete: (taskId: number) => void;
}

export default function TodayView({ plan, tasks, onToggleComplete }: TodayViewProps) {
  // Determine "today" in local timezone
  const todayStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD format in local time usually

  // Extract blocks matching today
  const todayBlocks = plan?.scheduled_blocks.filter(b => b.date === todayStr) || [];
  
  // Sort by start time
  const sortedBlocks = [...todayBlocks].sort((a, b) => a.start_time - b.start_time);

  const formatTime = (minutes: number) => {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    return `${h12}:${m.toString().padStart(2, '0')} ${ampm}`;
  };

  const getTaskForBlock = (block: ScheduleBlock) => {
    if (!block.task_id) return null;
    return tasks.find(t => t.id === block.task_id);
  };

  if (!plan) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center bg-surface border border-subtle rounded-2xl">
        <h3 className="text-xl font-medium text-white mb-2">No active plan</h3>
        <p className="text-muted text-sm max-w-sm">
          Use the AI Planner or click &quot;Plan My Week&quot; to generate an optimized schedule for your tasks.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full bg-surface border border-subtle rounded-2xl p-6 overflow-y-auto custom-scrollbar">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Today</h2>
          <p className="text-muted text-sm mt-1">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="text-right">
          <span className="text-xs font-semibold text-accent-brand bg-accent-brand/10 px-3 py-1 rounded-full uppercase tracking-wider">
            {sortedBlocks.length} Items Scheduled
          </span>
        </div>
      </header>

      {sortedBlocks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
            <CheckCircle2 className="w-8 h-8 text-white/20" />
          </div>
          <h3 className="text-lg font-medium text-white mb-1">You&apos;re all clear!</h3>
          <p className="text-muted text-sm">Nothing scheduled for today. Take a break or plan more tasks.</p>
        </div>
      ) : (
        <div className="space-y-4 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-white/10 before:to-transparent">
          <AnimatePresence>
            {sortedBlocks.map((block, i) => {
              const task = getTaskForBlock(block);
              const isCompleted = task?.completed || false;
              const isFixedEvent = !block.task_id;

              return (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  key={`${block.task_id || 'event'}-${block.start_time}-${i}`} 
                  className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active"
                >
                  {/* Timeline dot */}
                  <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-surface bg-white/5 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 relative z-10">
                    {isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : isFixedEvent ? (
                      <div className="w-2 h-2 rounded-full bg-blue-400" />
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-accent-brand" />
                    )}
                  </div>

                  {/* Content Card */}
                  <div className={`w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-xl border transition-colors ${
                    isCompleted 
                      ? 'bg-white/5 border-white/5 opacity-60' 
                      : isFixedEvent 
                        ? 'bg-blue-500/10 border-blue-500/20' 
                        : 'bg-surface-hover border-subtle hover:border-white/20'
                  }`}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="text-xs font-semibold text-muted mb-1 font-mono tracking-tight">
                          {formatTime(block.start_time)} - {formatTime(block.end_time)}
                        </div>
                        <h4 className={`text-base font-medium ${isCompleted ? 'text-white/50 line-through' : 'text-primary'}`}>
                          {block.task_title}
                        </h4>
                        {!isFixedEvent && !isCompleted && (
                          <p className="text-xs text-muted mt-2 line-clamp-1">{block.explanation}</p>
                        )}
                      </div>
                      
                      {/* Actions */}
                      {!isFixedEvent && task && (
                        <button
                          onClick={() => onToggleComplete(task.id)}
                          className="shrink-0 text-muted hover:text-white transition-colors"
                          aria-label={isCompleted ? "Mark incomplete" : "Mark complete"}
                        >
                          {isCompleted ? (
                            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                          ) : (
                            <Circle className="w-6 h-6" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
