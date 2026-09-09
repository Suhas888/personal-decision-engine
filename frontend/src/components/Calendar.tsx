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
}

export default function Calendar({ plan }: CalendarProps) {
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
      <div className="flex flex-col items-center justify-center h-96 border-2 border-dashed border-neutral-700/50 rounded-2xl bg-neutral-900/30 text-neutral-500 backdrop-blur-md">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
        <p className="font-medium text-lg">No Schedule Generated</p>
        <p className="text-sm mt-1">Use the AI Assistant to plan your week.</p>
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
    <div className="bg-neutral-900/40 rounded-3xl p-6 border border-white/5 backdrop-blur-xl shadow-2xl overflow-hidden">
      <div className="mb-6 flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold bg-gradient-to-r from-white to-neutral-400 bg-clip-text text-transparent">Weekly Schedule</h2>
          <p className="text-neutral-400 text-sm mt-1">Your optimized time blocks</p>
        </div>
      </div>
      
      {/* CSS Grid for Desktop Calendar */}
      <div className="grid grid-cols-1 lg:grid-cols-7 gap-4 lg:gap-2">
        {daysOrder.map(day => {
          const blocks = groupedBlocks[day] || [];
          const isToday = currentTime?.day === day;
          
          return (
            <div key={day} className={`flex flex-col rounded-2xl transition-all duration-300 ${isToday ? 'bg-blue-900/10 border-blue-500/30' : 'bg-neutral-800/30 border-transparent'} border pb-4`}>
              <div className={`text-center py-3 text-sm font-bold uppercase tracking-widest rounded-t-2xl border-b ${isToday ? 'text-blue-400 border-blue-500/30 bg-blue-500/10' : 'text-neutral-500 border-neutral-700/50 bg-neutral-800/50'}`}>
                {day.substring(0, 3)}
              </div>
              
              <div className="flex-1 p-2 relative min-h-[400px]">
                {/* Current Time Indicator Line */}
                {isToday && currentTime && (
                  <div 
                    className="absolute left-0 right-0 h-px bg-red-500 z-20 shadow-[0_0_8px_rgba(239,68,68,0.8)] pointer-events-none"
                    style={{ 
                      top: '10px' 
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
                        className={`group p-3 rounded-xl border transition-colors ${isPast ? 'opacity-40 grayscale' : ''} ${isTask ? 'bg-gradient-to-br from-indigo-900/20 to-blue-900/10 border-indigo-500/20 hover:border-indigo-500/40' : 'bg-neutral-800/40 border-neutral-700/50 hover:bg-neutral-800/60'}`}
                      >
                        <div className="flex justify-between items-center mb-1">
                          <div className="text-[10px] font-mono text-neutral-400 bg-black/40 px-1.5 py-0.5 rounded">
                            {formatTime(block.start_time)} - {formatTime(block.end_time)}
                          </div>
                        </div>
                        
                        <div className={`font-semibold leading-tight mt-1.5 ${isTask ? 'text-indigo-100' : 'text-neutral-300'}`}>
                          {block.task_title}
                        </div>
                        
                        <div className="flex justify-between items-end mt-3">
                          <div className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${isTask ? 'bg-indigo-500/10 text-indigo-300' : 'bg-neutral-800 text-neutral-400'}`}>
                            {block.duration_minutes}m
                          </div>
                          
                          {block.explanation && (
                             <div className="w-4 h-4 rounded-full bg-neutral-700/50 flex items-center justify-center text-neutral-400 cursor-help" title={block.explanation}>
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
  );
}
