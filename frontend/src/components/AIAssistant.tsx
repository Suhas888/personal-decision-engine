import React, { useState } from 'react';
import { Bot, Send, Sparkles, Check, X, ArrowRight, Terminal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import CommandPreview from './CommandPreview';
import {
  previewCommands,
  executeCommands,
  executeWithConfirmation,
  CommandApiError,
  type CommandPreviewResponse,
} from '../api/commandsApi';

// ---- Types ----
type CommandMode =
  | 'idle'
  | 'loading'
  | 'preview'
  | 'clarification'
  | 'unsupported'
  | 'confirming'
  | 'success'
  | 'error';

interface CommandState {
  mode: CommandMode;
  preview: CommandPreviewResponse | null;
  clarificationText: string;
  successMessage: string;
  errorMessage: string;
}

const INITIAL_CMD_STATE: CommandState = {
  mode: 'idle',
  preview: null,
  clarificationText: '',
  successMessage: '',
  errorMessage: '',
};

interface AIAssistantProps {
  llmInput: string;
  setLlmInput: (val: string) => void;
  handleLlmSubmit: () => void;
  llmLoading: boolean;
  llmLoadingStep?: string | null;
  llmResponse: Record<string, unknown> | null;
  setLlmResponse: (val: Record<string, unknown> | null) => void;
  handleApproveAndSave: () => void;
  replanInput: string;
  setReplanInput: (val: string) => void;
  handleReplanSubmit: () => void;
  replanLoading: boolean;
  replanLoadingStep?: string | null;
  replanParsed: Record<string, unknown> | null;
  setReplanParsed: (val: Record<string, unknown> | null) => void;
  handleReplanApply: () => void;
  hasPlan: boolean;
  onCommandExecuted?: () => void;
}

type Tab = 'assistant' | 'command';

export default function AIAssistant(props: AIAssistantProps) {
  const [activeTab, setActiveTab] = useState<Tab>('assistant');
  const [commandInput, setCommandInput] = useState('');
  const [cmdState, setCmdState] = useState<CommandState>(INITIAL_CMD_STATE);

  const handleCommandPreview = async () => {
    const text = commandInput.trim();
    if (!text) return;

    setCmdState({ ...INITIAL_CMD_STATE, mode: 'loading' });

    try {
      const result = await previewCommands(text);
      setCommandInput('');

      if (!result.commands || result.commands.length === 0) {
        setCmdState({
          ...INITIAL_CMD_STATE,
          mode: 'unsupported',
          errorMessage: 'No command could be interpreted from your input.',
        });
        return;
      }

      setCmdState({ ...INITIAL_CMD_STATE, mode: 'preview', preview: result });
    } catch (err) {
      if (err instanceof CommandApiError) {
        if (err.statusCode === 422) {
          setCmdState({
            ...INITIAL_CMD_STATE,
            mode: 'clarification',
            clarificationText: err.message,
          });
        } else if (err.statusCode === 429) {
          setCmdState({
            ...INITIAL_CMD_STATE,
            mode: 'error',
            errorMessage: 'Rate limit reached. Please wait a moment and try again.',
          });
        } else if (err.statusCode >= 500) {
          setCmdState({
            ...INITIAL_CMD_STATE,
            mode: 'error',
            errorMessage: 'Backend error. Please check that the server is running.',
          });
        } else {
          setCmdState({
            ...INITIAL_CMD_STATE,
            mode: 'error',
            errorMessage: err.message,
          });
        }
      } else {
        setCmdState({
          ...INITIAL_CMD_STATE,
          mode: 'error',
          errorMessage: 'Network error — could not reach the server.',
        });
      }
    }
  };

  const handleCommandConfirm = async () => {
    if (!cmdState.preview) return;
    setCmdState((s) => ({ ...s, mode: 'confirming' }));

    try {
      let results;
      if (cmdState.preview.requires_confirmation && cmdState.preview.confirmation_id) {
        results = await executeWithConfirmation(cmdState.preview.confirmation_id);
      } else {
        results = await executeCommands(cmdState.preview.commands);
      }

      const total = results.results.reduce((s, r) => s + (r.affected_count ?? 0), 0);
      const opLabel = results.results
        .map((r) => `${r.operation.toLowerCase()} ${r.affected_count} ${r.target_type.toLowerCase()}(s)`)
        .join(', ');

      setCmdState({
        ...INITIAL_CMD_STATE,
        mode: 'success',
        successMessage: total > 0 ? `Done: ${opLabel}.` : 'Command executed.',
      });

      props.onCommandExecuted?.();
    } catch (err) {
      const msg =
        err instanceof CommandApiError
          ? err.message
          : 'Execution failed. Please try again.';
      setCmdState({ ...INITIAL_CMD_STATE, mode: 'error', errorMessage: msg });
    }
  };

  const handleCommandDismiss = () => {
    setCmdState(INITIAL_CMD_STATE);
  };

  const commandInputBusy = cmdState.mode === 'loading' || cmdState.mode === 'confirming';

  return (
    <div className="flex flex-col h-full bg-surface rounded-2xl border border-subtle shadow-2xl overflow-hidden relative">
      {/* Background flare effect */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[120%] h-32 bg-accent-brand/10 blur-[60px] pointer-events-none rounded-[100%]" />
      
      {/* Header */}
      <div className="p-4 border-b border-subtle flex items-center gap-3 relative z-10">
        <div className="p-2 bg-accent-brand/10 rounded-lg shrink-0">
          <Sparkles className="w-4 h-4 text-accent-brand" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-bold text-white tracking-wide truncate">Command Center</h2>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-1 bg-white/5 rounded-xl p-1 shrink-0">
          <button
            onClick={() => setActiveTab('assistant')}
            className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
              activeTab === 'assistant'
                ? 'bg-accent-brand text-white'
                : 'text-muted hover:text-white'
            }`}
          >
            Plan
          </button>
          <button
            onClick={() => setActiveTab('command')}
            className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1 ${
              activeTab === 'command'
                ? 'bg-accent-brand text-white'
                : 'text-muted hover:text-white'
            }`}
          >
            <Terminal className="w-2.5 h-2.5" />
            Terminal
          </button>
        </div>
      </div>

      {/* ---- PLAN TAB ---- */}
      {activeTab === 'assistant' && (
        <>
          <div className="flex-1 p-5 overflow-y-auto space-y-4 custom-scrollbar relative z-10">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-surface-hover border border-subtle rounded-xl p-4 text-sm text-primary shadow-sm"
            >
              {props.hasPlan
                ? "Your week is planned. Ready to adjust? Examples: 'Move GATE to Tuesday', 'Add a 1 hour workout today'."
                : "Awaiting input. What are your main goals for this week?"}
            </motion.div>

            <AnimatePresence>
              {props.llmResponse && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="bg-accent-brand/5 border border-accent-brand/20 rounded-xl p-5 text-sm text-primary shadow-sm w-full"
                >
                  {props.llmResponse.clarification_needed ? (
                    <div className="text-amber-400 font-medium flex items-start gap-3">
                      <Bot className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
                      <span className="leading-relaxed">{props.llmResponse.clarification_question as string}</span>
                    </div>
                  ) : (
                    <div>
                      <div className="font-semibold text-accent-brand mb-4 flex items-center gap-2">
                        <Check className="w-4 h-4" />
                        Parsed Interpretation
                      </div>
                      <ul className="space-y-2 mb-6">
                        {Array.isArray(props.llmResponse.tasks) &&
                          props.llmResponse.tasks.map((t: Record<string, unknown>, i: number) => (
                            <li
                              key={`t-${i}`}
                              className="flex justify-between items-center bg-surface p-3 rounded-xl border border-subtle"
                            >
                              <span className="text-white font-medium text-xs">{t.title as string}</span>
                              <span className="text-[10px] text-accent-brand font-mono bg-accent-brand/10 px-2 py-1 rounded-md">
                                {t.estimated_minutes as number}m (P{t.priority as number})
                              </span>
                            </li>
                          ))}
                      </ul>
                      <div className="flex gap-2">
                        <button
                          onClick={props.handleApproveAndSave}
                          className="flex-1 py-2.5 bg-accent-brand hover:bg-accent-brand-hover text-white rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2"
                        >
                          Approve & Save <ArrowRight className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => props.setLlmResponse(null)}
                          className="p-2.5 bg-surface hover:bg-surface-hover border border-subtle text-muted rounded-xl transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </motion.div>
              )}

              {props.replanParsed && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5 text-sm text-primary shadow-sm w-full"
                >
                  {props.replanParsed.clarification_needed ? (
                    <div className="text-amber-400 font-medium flex items-start gap-3">
                      <Bot className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
                      <span className="leading-relaxed">{props.replanParsed.clarification_question as string}</span>
                    </div>
                  ) : (
                    <div>
                      <div className="font-semibold text-amber-400 mb-3 flex items-center gap-2">
                        <Check className="w-4 h-4" />
                        Proposed Adjustment
                      </div>
                      <div className="mb-5 text-primary bg-surface p-3.5 rounded-xl border border-subtle">
                        <p className="font-medium text-xs leading-relaxed">
                          {props.replanParsed.human_readable_summary as string}
                        </p>
                        <div className="text-[10px] text-amber-500 mt-3 font-mono uppercase tracking-wider flex items-center gap-2">
                          <span className="px-1.5 py-0.5 bg-amber-500/10 rounded">
                            {props.replanParsed.action as string}
                          </span>
                          <ArrowRight className="w-3 h-3" />
                          <span className="truncate max-w-[150px]">
                            {(props.replanParsed.target_name as string) || 'N/A'}
                          </span>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={props.handleReplanApply}
                          className="flex-1 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-bold transition-all"
                        >
                          Apply & Re-Optimize
                        </button>
                        <button
                          onClick={() => props.setReplanParsed(null)}
                          className="p-2.5 bg-surface hover:bg-surface-hover border border-subtle text-muted rounded-xl transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Plan tab input */}
          <div className="p-4 border-t border-subtle bg-surface z-10 shrink-0">
            <div className="relative">
              <input
                type="text"
                value={props.hasPlan ? props.replanInput : props.llmInput}
                onChange={(e) =>
                  props.hasPlan ? props.setReplanInput(e.target.value) : props.setLlmInput(e.target.value)
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (props.hasPlan) {
                      props.handleReplanSubmit();
                    } else {
                      props.handleLlmSubmit();
                    }
                  }
                }}
                placeholder={props.hasPlan ? 'e.g. Move workout to 6pm...' : 'e.g. Add math homework, takes 2 hours...'}
                className="w-full bg-black/40 border border-subtle rounded-xl pl-4 pr-12 py-3.5 text-sm focus:outline-none focus:border-accent-brand/50 transition-all placeholder:text-muted text-white shadow-inner"
                disabled={props.llmLoading || props.replanLoading}
              />
              <button
                onClick={props.hasPlan ? props.handleReplanSubmit : props.handleLlmSubmit}
                disabled={
                  props.llmLoading ||
                  props.replanLoading ||
                  (!props.llmInput && !props.replanInput)
                }
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-accent-brand hover:bg-accent-brand-hover rounded-lg text-white transition-all disabled:opacity-0"
              >
                {props.llmLoading || props.replanLoading ? (
                  <div className="flex items-center gap-2 px-1">
                    <svg
                      className="animate-spin h-4 w-4"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                  </div>
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </>
      )}

      {/* ---- COMMAND TAB ---- */}
      {activeTab === 'command' && (
        <>
          <div className="flex-1 p-5 overflow-y-auto space-y-4 custom-scrollbar relative z-10">
            {cmdState.mode === 'idle' && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-surface-hover border border-subtle rounded-xl p-4 text-sm text-primary shadow-sm"
              >
                <p className="text-xs leading-relaxed font-medium">
                  Execute direct system commands:
                </p>
                <ul className="mt-2 space-y-2 text-[11px] text-muted list-disc list-inside">
                  <li>Delete all completed tasks</li>
                  <li>Mark Homework 1 as completed</li>
                  <li>Delete task &quot;Math revision&quot;</li>
                </ul>
              </motion.div>
            )}

            {cmdState.mode !== 'idle' && (
              <CommandPreview
                mode={cmdState.mode}
                preview={cmdState.preview}
                clarificationText={cmdState.clarificationText}
                successMessage={cmdState.successMessage}
                errorMessage={cmdState.errorMessage}
                onConfirm={handleCommandConfirm}
                onDismiss={handleCommandDismiss}
              />
            )}
          </div>

          <div className="p-4 border-t border-subtle bg-surface z-10 shrink-0">
            <div className="relative">
              <input
                type="text"
                value={commandInput}
                onChange={(e) => setCommandInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCommandPreview();
                }}
                placeholder="e.g. Delete all completed tasks…"
                className="w-full bg-black/40 border border-subtle rounded-xl pl-4 pr-12 py-3.5 text-sm focus:outline-none focus:border-accent-brand/50 transition-all placeholder:text-muted text-white font-mono shadow-inner"
                disabled={commandInputBusy}
              />
              <button
                onClick={handleCommandPreview}
                disabled={commandInputBusy || !commandInput.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-accent-brand hover:bg-accent-brand-hover rounded-lg text-white transition-all disabled:opacity-0"
              >
                {commandInputBusy ? (
                  <svg
                    className="animate-spin h-4 w-4"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                ) : (
                  <Terminal className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
