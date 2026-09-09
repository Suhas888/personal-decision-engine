import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  X,
  AlertTriangle,
  Loader2,
  Trash2,
  Edit2,
  Plus,
  BookOpen,
  Shield,
  HelpCircle,
  CheckCircle2,
} from "lucide-react";
import type {
  CommandPreviewResponse,
  ParsedCommand,
} from "../api/commandsApi";
import {
  friendlyOperation,
  friendlyTarget,
  friendlyScope,
  isDestructive,
} from "../api/commandsApi";

interface CommandPreviewProps {
  /** Current state mode */
  mode:
    | "idle"
    | "loading"
    | "preview"
    | "clarification"
    | "unsupported"
    | "confirming"
    | "success"
    | "error";
  preview: CommandPreviewResponse | null;
  clarificationText?: string;
  successMessage?: string;
  errorMessage?: string;
  onConfirm: () => void;
  onDismiss: () => void;
}

function OperationIcon({ op }: { op: string }) {
  if (op === "DELETE") return <Trash2 className="w-3.5 h-3.5 text-red-400" />;
  if (op === "UPDATE") return <Edit2 className="w-3.5 h-3.5 text-amber-400" />;
  if (op === "CREATE") return <Plus className="w-3.5 h-3.5 text-emerald-400" />;
  return <BookOpen className="w-3.5 h-3.5 text-blue-400" />;
}

function CommandPill({ cmd }: { cmd: ParsedCommand }) {
  const destructive = isDestructive(cmd);
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-xs ${
        destructive
          ? "bg-red-950/30 border-red-500/20 text-red-200"
          : "bg-neutral-800/60 border-white/5 text-neutral-300"
      }`}
    >
      <OperationIcon op={cmd.operation} />
      <span className="font-semibold">
        {friendlyOperation(cmd.operation)}
      </span>
      <span className="text-neutral-400">
        {friendlyScope(cmd.scope)} {friendlyTarget(cmd.target_type)}
      </span>
      {cmd.filters.length > 0 && (
        <span className="text-neutral-500 truncate max-w-[120px]">
          {cmd.filters.map((f) => `${f.field}=${f.value}`).join(", ")}
        </span>
      )}
    </div>
  );
}

export default function CommandPreview({
  mode,
  preview,
  clarificationText,
  successMessage,
  errorMessage,
  onConfirm,
  onDismiss,
}: CommandPreviewProps) {
  return (
    <AnimatePresence mode="wait">
      {/* Loading */}
      {mode === "loading" && (
        <motion.div
          key="loading"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="flex items-center gap-2 text-xs text-neutral-400 px-1"
        >
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Interpreting command…
        </motion.div>
      )}

      {/* Clarification needed */}
      {mode === "clarification" && clarificationText && (
        <motion.div
          key="clarification"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="bg-amber-950/20 border border-amber-500/20 rounded-2xl p-4 text-sm"
        >
          <div className="flex items-start gap-2 text-amber-300 mb-3">
            <HelpCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="font-semibold text-xs uppercase tracking-wider">Clarification needed</span>
          </div>
          <p className="text-neutral-300 text-xs leading-relaxed">{clarificationText}</p>
          <button
            onClick={onDismiss}
            className="mt-3 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Dismiss
          </button>
        </motion.div>
      )}

      {/* Unsupported */}
      {mode === "unsupported" && (
        <motion.div
          key="unsupported"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="bg-neutral-800/60 border border-white/5 rounded-2xl p-4 text-sm"
        >
          <div className="flex items-start gap-2 text-neutral-400 mb-2">
            <HelpCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="font-semibold text-xs uppercase tracking-wider">Not understood</span>
          </div>
          <p className="text-neutral-400 text-xs leading-relaxed">
            {errorMessage ?? "That command isn't supported yet. Try rephrasing."}
          </p>
          <button
            onClick={onDismiss}
            className="mt-3 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Dismiss
          </button>
        </motion.div>
      )}

      {/* Error */}
      {mode === "error" && (
        <motion.div
          key="error"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="bg-red-950/20 border border-red-500/20 rounded-2xl p-4 text-sm"
        >
          <div className="flex items-start gap-2 text-red-400 mb-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="font-semibold text-xs uppercase tracking-wider">Error</span>
          </div>
          <p className="text-red-300/80 text-xs leading-relaxed">{errorMessage}</p>
          <button
            onClick={onDismiss}
            className="mt-3 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Dismiss
          </button>
        </motion.div>
      )}

      {/* Preview: safe (no confirmation needed) */}
      {mode === "preview" && preview && !preview.requires_confirmation && (
        <motion.div
          key="preview-safe"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="bg-indigo-950/20 border border-indigo-500/20 rounded-2xl p-4 text-sm space-y-3"
        >
          <div className="flex items-center gap-2 text-indigo-300">
            <Check className="w-4 h-4" />
            <span className="font-semibold text-xs uppercase tracking-wider">Command Interpreted</span>
          </div>
          <p className="text-neutral-300 text-xs">{preview.summary}</p>
          <div className="space-y-1.5">
            {preview.commands.map((cmd, i) => (
              <CommandPill key={i} cmd={cmd} />
            ))}
          </div>
          {preview.affected_count > 0 && (
            <p className="text-xs text-neutral-500">
              {preview.affected_count} item(s) will be affected.
            </p>
          )}
          <div className="flex gap-2 pt-1">
            <button
              onClick={onConfirm}
              className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition-all"
            >
              Execute
            </button>
            <button
              onClick={onDismiss}
              className="p-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-400 rounded-xl transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}

      {/* Preview: destructive (requires explicit confirmation) */}
      {mode === "preview" && preview && preview.requires_confirmation && (
        <motion.div
          key="preview-destructive"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="bg-red-950/20 border border-red-500/30 rounded-2xl p-4 text-sm space-y-3"
        >
          <div className="flex items-center gap-2 text-red-400">
            <Shield className="w-4 h-4" />
            <span className="font-semibold text-xs uppercase tracking-wider">Confirmation Required</span>
          </div>
          <p className="text-neutral-300 text-xs">{preview.summary}</p>
          <div className="space-y-1.5">
            {preview.commands.map((cmd, i) => (
              <CommandPill key={i} cmd={cmd} />
            ))}
          </div>
          {preview.affected_count > 0 && (
            <p className="text-xs text-red-400/80 font-medium">
              ⚠ This will permanently affect {preview.affected_count} item(s).
            </p>
          )}
          {preview.expires_at && (
            <p className="text-xs text-neutral-600">
              Confirmation expires at {new Date(preview.expires_at).toLocaleTimeString()}
            </p>
          )}
          <div className="flex gap-2 pt-1">
            <button
              onClick={onConfirm}
              className="flex-1 py-2 bg-red-700 hover:bg-red-600 text-white rounded-xl text-xs font-bold transition-all"
            >
              Yes, proceed
            </button>
            <button
              onClick={onDismiss}
              className="p-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-400 rounded-xl transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      )}

      {/* Confirming (executing) */}
      {mode === "confirming" && (
        <motion.div
          key="confirming"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="flex items-center gap-2 text-xs text-neutral-400 px-1"
        >
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Executing…
        </motion.div>
      )}

      {/* Success */}
      {mode === "success" && (
        <motion.div
          key="success"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="bg-emerald-950/20 border border-emerald-500/20 rounded-2xl p-4 text-sm"
        >
          <div className="flex items-center gap-2 text-emerald-400 mb-2">
            <CheckCircle2 className="w-4 h-4" />
            <span className="font-semibold text-xs uppercase tracking-wider">Done</span>
          </div>
          <p className="text-neutral-300 text-xs">{successMessage ?? "Command executed successfully."}</p>
          <button
            onClick={onDismiss}
            className="mt-3 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            Dismiss
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
