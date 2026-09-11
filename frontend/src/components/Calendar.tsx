import React, { useEffect, useState } from 'react';
import { PlanResponse, ScheduleBlock } from '../types';
import { AnimatedList } from './ui/AnimatedList';

export const formatTime = (minutes: number) => {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
};

interface CalendarProps {
  plan: PlanResponse | null;
  onToggleComplete?: (taskId: number) => void;
}

export default function Calendar({ plan, onToggleComplete }: CalendarProps) {
  const daysOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const [currentTime, setCurrentTime] = useState<{ day: string, minutes: number } | null>(null);

  useEffect(() => {
    // Update current time indicator every minute
    const updateTime = () => {
      const now = new Date();
      const day = now.toLocaleDateString('en-US', { weekday: 'long' });
      const minutes = now.getHours() * 60 + now.getMinutes();
      setCurrentTime({ day, minutes });
    };
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!plan) {
    return (
      <div className="flex flex-col items-center justify-center h-96 border border-subtle rounded-2xl bg-surface/50 text-muted backdrop-blur-md">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
        <p className="font-medium text-lg text-primary">No Schedule Generated</p>
        <p className="text-sm mt-1">Use the Planner to optimize your week.</p>
      </div>
    );
  }

  // Group blocks by day
  const groupedBlocks: Record<string, ScheduleBlock[]> = {};
  plan.scheduled_blocks.forEach(b => {
    if (!groupedBlocks[b.day]) groupedBlocks[b.day] = [];
    groupedBlocks[b.day].push(b);
  });

  return (
    <div className="bg-surface rounded-2xl p-6 border border-subtle h-full overflow-hidden flex flex-col">
      <div className="mb-6 flex justify-between items-end shrink-0">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Weekly Schedule</h2>
          <p className="text-muted text-sm mt-1">Your optimized time blocks</p>
        </div>
      </div>
      
      {/* Scrollable container for mobile */}
      <div className="flex-1 overflow-x-auto overflow-y-auto custom-scrollbar">
        <div className="flex flex-col lg:grid lg:grid-cols-7 gap-4 lg:gap-2 min-w-[300px] lg:min-w-0">
          {daysOrder.map(day => {
            const blocks = groupedBlocks[day] || [];
            const isToday = currentTime?.day === day;
            
            return (
              <div key={day} className={`flex flex-col rounded-xl transition-all duration-300 ${isToday ? 'bg-accent-brand/5 border-accent-brand/20' : 'bg-surface-hover/30 border-subtle/50'} border pb-4`}>
                <div className={`text-center py-2 text-xs font-bold uppercase tracking-widest rounded-t-xl border-b ${isToday ? 'text-accent-brand border-accent-brand/20 bg-accent-brand/10' : 'text-muted border-subtle bg-white/5'}`}>
                  {day.substring(0, 3)}
                </div>
                
                <div className="flex-1 p-2 relative min-h-[400px]">
                  {/* Current Time Indicator Line */}
                  {isToday && currentTime && (
                    <div 
                      className="absolute left-0 right-0 h-px bg-red-500 z-20 shadow-[0_0_8px_rgba(239,68,68,0.8)] pointer-events-none"
                      style={{ 
                        top: '10px' // Positioning logic can be expanded if using absolute time scale
                      }}
                    >
                      <div className="absolute -top-3 -left-1 text-[10px] bg-red-600 text-white px-1.5 py-0.5 rounded-full font-bold">
                        {formatTime(currentTime.minutes)}
                      </div>
                    </div>
                  )}
                  
                  <AnimatedList className="space-y-2">
                    {blocks.map((block, i) => {
                      const isPast = isToday && currentTime && (block.end_time < currentTime.minutes);
                      const isTask = !!block.task_id;
                      
                      return (
                        <div 
                          key={block.task_id ? `task-${block.task_id}-${block.start_time}` : `fixed-${i}`} 
                          className={`group p-3 rounded-xl border transition-colors flex flex-col ${isPast ? 'opacity-50' : ''} ${isTask ? 'bg-accent-brand/10 border-accent-brand/20 hover:border-accent-brand/40' : 'bg-white/5 border-subtle hover:bg-white/10'}`}
                        >
                          <div className="flex justify-between items-center mb-1">
                            <div className="text-[10px] font-mono text-muted bg-black/20 px-1.5 py-0.5 rounded">
                              {formatTime(block.start_time)} - {formatTime(block.end_time)}
                            </div>
                          </div>
                          
                          <div className={`font-semibold text-sm leading-tight mt-1.5 flex items-start gap-2 ${isTask ? 'text-white' : 'text-primary/80'}`}>
                            {isTask && onToggleComplete && (
                              <button 
                                onClick={() => onToggleComplete(block.task_id as number)}
                                className="mt-0.5 shrink-0 w-4 h-4 rounded border border-accent-brand/50 hover:bg-accent-brand/20 flex items-center justify-center transition-colors"
                                title="Mark as complete"
                              >
                              </button>
                            )}
                            <span className="line-clamp-2">{block.task_title}</span>
                          </div>
                          
                          <div className="flex justify-between items-end mt-auto pt-3">
                            <div className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${isTask ? 'bg-accent-brand/20 text-accent-brand' : 'bg-white/10 text-muted'}`}>
                              {block.duration_minutes}m
                            </div>
                            
                            {block.explanation && (
                               <div className="w-4 h-4 rounded-full bg-white/10 flex items-center justify-center text-muted cursor-help" title={block.explanation}>
                                 <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                               </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </AnimatedList>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  );
}
