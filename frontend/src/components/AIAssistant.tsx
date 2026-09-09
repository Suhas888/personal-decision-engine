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

// ---- Props (unchanged from the existing contract) ----
interface AIAssistantProps {
  llmInput: string;
  setLlmInput: (val: string) => void;
  handleLlmSubmit: () => void;
  llmLoading: boolean;
  llmResponse: Record<string, unknown> | null;
  setLlmResponse: (val: Record<string, unknown> | null) => void;
  handleApproveAndSave: () => void;
  replanInput: string;
  setReplanInput: (val: string) => void;
  handleReplanSubmit: () => void;
  replanLoading: boolean;
  replanParsed: Record<string, unknown> | null;
  setReplanParsed: (val: Record<string, unknown> | null) => void;
  handleReplanApply: () => void;
  hasPlan: boolean;
  /** Called after a command executes successfully so the parent can refresh data. */
  onCommandExecuted?: () => void;
}

// ---- Tab type ----
type Tab = 'assistant' | 'command';

export default function AIAssistant(props: AIAssistantProps) {
  const [activeTab, setActiveTab] = useState<Tab>('assistant');
  const [commandInput, setCommandInput] = useState('');
  const [cmdState, setCmdState] = useState<CommandState>(INITIAL_CMD_STATE);

  // ---- Command pipeline handlers ----

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
          // Validation failure or clarification
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
        // Destructive: use the server-stored token — never re-send the commands
        results = await executeWithConfirmation(cmdState.preview.confirmation_id);
      } else {
        // Safe: send the validated command list
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

      // Refresh parent data (plan, tasks, metrics)
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
    <div className="flex flex-col h-full bg-neutral-900/60 rounded-3xl border border-white/10 shadow-2xl overflow-hidden backdrop-blur-xl">
      {/* Header */}
      <div className="p-5 border-b border-white/5 flex items-center gap-3">
        <div className="p-2 bg-indigo-500/10 rounded-lg">
          <Bot className="w-5 h-5 text-indigo-400" />
        </div>
        <div className="flex-1">
          <h2 className="text-sm font-bold text-white tracking-wide">Assistant</h2>
          <p className="text-[10px] text-neutral-500 uppercase tracking-widest font-semibold mt-0.5">
            Decision Engine Core
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-1 bg-black/40 rounded-xl p-1">
          <button
            onClick={() => setActiveTab('assistant')}
            className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
              activeTab === 'assistant'
                ? 'bg-indigo-600 text-white'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            Plan
          </button>
          <button
            onClick={() => setActiveTab('command')}
            className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1 ${
              activeTab === 'command'
                ? 'bg-indigo-600 text-white'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            <Terminal className="w-2.5 h-2.5" />
            Command
          </button>
        </div>
      </div>

      {/* ---- PLAN TAB (original behaviour, untouched) ---- */}
      {activeTab === 'assistant' && (
        <>
          <div className="flex-1 p-5 overflow-y-auto space-y-4 custom-scrollbar">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="self-start w-fit max-w-[85%] bg-neutral-800 border border-neutral-700/50 rounded-2xl rounded-tl-sm p-4 text-sm text-neutral-300 shadow-sm"
            >
              {props.hasPlan
                ? "Your week is planned! Need to adjust something? E.g., 'Move GATE to Tuesday' or 'Class was cancelled'."
                : "Good morning! Let's build your week. What are your main goals?"}
            </motion.div>

            <AnimatePresence>
              {props.llmResponse && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="self-start w-full bg-indigo-950/30 border border-indigo-500/20 rounded-2xl rounded-tl-sm p-5 text-sm text-neutral-300 shadow-sm"
                >
                  {props.llmResponse.clarification_needed ? (
                    <div className="text-yellow-400/90 font-medium flex items-start gap-3">
                      <Sparkles className="w-4 h-4 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{props.llmResponse.clarification_question as string}</span>
                    </div>
                  ) : (
                    <div>
                      <div className="font-semibold text-indigo-300 mb-4 flex items-center gap-2">
                        <Check className="w-4 h-4" />
                        Structured Interpretation
                      </div>
                      <ul className="space-y-2 mb-6">
                        {Array.isArray(props.llmResponse.tasks) &&
                          props.llmResponse.tasks.map((t: Record<string, unknown>, i: number) => (
                            <li
                              key={`t-${i}`}
                              className="flex justify-between items-center bg-black/40 p-2.5 rounded-xl border border-white/5"
                            >
                              <span className="text-indigo-50 font-medium text-xs">{t.title as string}</span>
                              <span className="text-[10px] text-indigo-300 font-mono bg-indigo-900/40 px-2 py-1 rounded-md">
                                {t.estimated_minutes as number}m (P{t.priority as number})
                              </span>
                            </li>
                          ))}
                      </ul>
                      <div className="flex gap-2">
                        <button
                          onClick={props.handleApproveAndSave}
                          className="flex-1 py-2.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2"
                        >
                          Approve <ArrowRight className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => props.setLlmResponse(null)}
                          className="p-2.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-400 rounded-xl transition-colors"
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
                  className="self-start w-full bg-amber-950/20 border border-amber-500/20 rounded-2xl rounded-tl-sm p-5 text-sm text-neutral-300 shadow-sm"
                >
                  {props.replanParsed.clarification_needed ? (
                    <div className="text-amber-400/90 font-medium flex items-start gap-3">
                      <Sparkles className="w-4 h-4 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{props.replanParsed.clarification_question as string}</span>
                    </div>
                  ) : (
                    <div>
                      <div className="font-semibold text-amber-400 mb-3 flex items-center gap-2">
                        <Check className="w-4 h-4" />
                        Proposed Change
                      </div>
                      <div className="mb-5 text-neutral-200 bg-black/40 p-3.5 rounded-xl border border-white/5">
                        <p className="font-medium text-xs leading-relaxed">
                          {props.replanParsed.human_readable_summary as string}
                        </p>
                        <div className="text-[10px] text-amber-500/70 mt-3 font-mono uppercase tracking-wider flex items-center gap-2">
                          <span className="px-1.5 py-0.5 bg-amber-500/10 rounded">
                            {props.replanParsed.action as string}
                          </span>
                          <ArrowRight className="w-3 h-3" />
                          {(props.replanParsed.target_name as string) || 'N/A'}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={props.handleReplanApply}
                          className="flex-1 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-bold transition-all"
                        >
                          Re-Optimize Schedule
                        </button>
                        <button
                          onClick={() => props.setReplanParsed(null)}
                          className="p-2.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-400 rounded-xl transition-colors"
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
          <div className="p-5 pt-2 border-t border-white/5 bg-neutral-900/50">
            <div className="relative">
              <input
                type="text"
                value={props.hasPlan ? props.replanInput : props.llmInput}
                onChange={(e) =>
                  props.hasPlan ? props.setReplanInput(e.target.value) : props.setLlmInput(e.target.value)
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    props.hasPlan ? props.handleReplanSubmit() : props.handleLlmSubmit();
                  }
                }}
                placeholder={props.hasPlan ? 'Adjust schedule…' : 'Message assistant…'}
                className="w-full bg-black/60 border border-white/10 rounded-2xl pl-4 pr-12 py-3.5 text-sm focus:outline-none focus:border-indigo-500/50 transition-all placeholder:text-neutral-600"
                disabled={props.llmLoading || props.replanLoading}
              />
              <button
                onClick={props.hasPlan ? props.handleReplanSubmit : props.handleLlmSubmit}
                disabled={
                  props.llmLoading ||
                  props.replanLoading ||
                  (!props.llmInput && !props.replanInput)
                }
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-white transition-all disabled:opacity-0"
              >
                {props.llmLoading || props.replanLoading ? (
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
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </>
      )}

      {/* ---- COMMAND TAB (Stage 7B-H) ---- */}
      {activeTab === 'command' && (
        <>
          <div className="flex-1 p-5 overflow-y-auto space-y-4 custom-scrollbar">
            {/* Intro message (only when idle / after dismiss) */}
            {cmdState.mode === 'idle' && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-neutral-800 border border-neutral-700/50 rounded-2xl rounded-tl-sm p-4 text-sm text-neutral-300"
              >
                <p className="text-xs leading-relaxed">
                  Type a natural-language command, e.g.
                </p>
                <ul className="mt-2 space-y-1 text-[11px] text-neutral-400 list-disc list-inside">
                  <li>Delete all completed tasks</li>
                  <li>Delete all GATE tasks</li>
                  <li>Mark Homework 1 as completed</li>
                  <li>Delete task "Math revision"</li>
                </ul>
              </motion.div>
            )}

            {/* Command preview / state display */}
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

          {/* Command tab input */}
          <div className="p-5 pt-2 border-t border-white/5 bg-neutral-900/50">
            <div className="relative">
              <input
                type="text"
                value={commandInput}
                onChange={(e) => setCommandInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCommandPreview();
                }}
                placeholder="e.g. Delete all completed tasks…"
                className="w-full bg-black/60 border border-white/10 rounded-2xl pl-4 pr-12 py-3.5 text-sm focus:outline-none focus:border-indigo-500/50 transition-all placeholder:text-neutral-600"
                disabled={commandInputBusy}
              />
              <button
                onClick={handleCommandPreview}
                disabled={commandInputBusy || !commandInput.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-white transition-all disabled:opacity-0"
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
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
            <p className="text-[10px] text-neutral-600 mt-2 text-center">
              Destructive operations require confirmation before execution.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
