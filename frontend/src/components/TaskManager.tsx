import React, { useState } from 'react';
import { Task } from '../types';
import { SpotlightCard } from './ui/SpotlightCard';
import { CheckCircle2, Circle, Clock, CalendarIcon } from 'lucide-react';
import { AnimatedList } from './ui/AnimatedList';

interface TaskManagerProps {
  tasks: Task[];
  onToggleComplete: (taskId: number, currentStatus: boolean) => void;
}

export default function TaskManager({ tasks, onToggleComplete }: TaskManagerProps) {
  const [activeTab, setActiveTab] = useState<'active' | 'completed'>('active');

  // Defensive array checks
  const safeTasks = Array.isArray(tasks) ? tasks : [];
  const activeTasks = safeTasks.filter(t => !t.completed);
  const completedTasks = safeTasks.filter(t => t.completed);
  
  const displayedTasks = activeTab === 'active' ? activeTasks : completedTasks;

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 1: return 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]';
      case 2: return 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.4)]';
      case 3: return 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.3)]';
      case 4: return 'bg-blue-400';
      default: return 'bg-neutral-600';
    }
  };

  return (
    <div className="bg-surface rounded-2xl p-6 border border-subtle h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Tasks</h2>
          <p className="text-muted text-sm mt-1">{activeTasks.length} remaining</p>
        </div>
        <div className="flex gap-1 bg-white/5 rounded-xl p-1">
          <button
            onClick={() => setActiveTab('active')}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${
              activeTab === 'active'
                ? 'bg-accent-brand text-white shadow-md'
                : 'text-muted hover:text-white'
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setActiveTab('completed')}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-2 ${
              activeTab === 'completed'
                ? 'bg-white/10 text-white shadow-md'
                : 'text-muted hover:text-white'
            }`}
          >
            Completed
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 min-h-[300px]">
        {displayedTasks.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center opacity-60 space-y-4 pt-10">
            <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-white/30" />
            </div>
            <p className="text-muted font-medium text-sm">
              {activeTab === 'active' 
                ? "You have no active tasks. Ask the planner to add some!" 
                : "No tasks completed yet. Keep going!"}
            </p>
          </div>
        ) : (
          <AnimatedList className="space-y-3">
            {displayedTasks.map(task => (
              <SpotlightCard 
                key={task.id} 
                className={`p-4 transition-all ${
                  task.completed 
                    ? 'opacity-60 bg-white/5 border-subtle' 
                    : 'bg-surface-hover hover:bg-white/5 cursor-pointer border border-subtle hover:border-white/20'
                }`}
              >
                <div className="flex gap-4 items-start">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleComplete(task.id, task.completed);
                    }}
                    className={`shrink-0 mt-0.5 rounded-full transition-colors ${
                      task.completed ? 'text-emerald-400' : 'text-muted hover:text-accent-brand'
                    }`}
                  >
                    {task.completed ? <CheckCircle2 className="w-6 h-6" /> : <Circle className="w-6 h-6" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <h3 className={`font-medium truncate ${task.completed ? 'line-through text-muted' : 'text-white'}`}>
                      {task.title}
                    </h3>
                    <div className="flex flex-wrap items-center gap-3 mt-2 text-xs font-medium">
                      <div className={`flex items-center gap-1.5 ${task.completed ? 'text-muted' : 'text-accent-brand bg-accent-brand/10'} px-2 py-0.5 rounded-full`}>
                        <Clock className="w-3 h-3" />
                        {task.estimated_minutes}m
                      </div>
                      
                      {!task.completed && (
                        <div className="flex items-center gap-1.5 bg-white/5 px-2 py-0.5 rounded-full text-muted border border-white/5">
                          <div className={`w-2 h-2 rounded-full ${getPriorityColor(task.priority)}`} />
                          <span>P{task.priority}</span>
                        </div>
                      )}
                      
                      {task.deadline && (
                        <div className="flex items-center gap-1.5 text-muted bg-white/5 px-2 py-0.5 rounded-full">
                          <CalendarIcon className="w-3 h-3" />
                          <span>{new Date(task.deadline).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </SpotlightCard>
            ))}
          </AnimatedList>
        )}
      </div>
    </div>
  );
}
