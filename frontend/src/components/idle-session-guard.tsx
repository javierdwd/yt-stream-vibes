"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const IDLE_MS = 3 * 60 * 1000;
/** Time to answer the “still there?” prompt before disconnect. */
const PROMPT_MS = 10_000;

const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "wheel",
  "pointerdown",
] as const;

type Phase = "watching" | "prompt" | "disconnected";

type Props = {
  sessionId: string | null;
  onIdleDisconnect: () => Promise<void>;
  onReconnect: () => void;
};

export function IdleSessionGuard({
  sessionId,
  onIdleDisconnect,
  onReconnect,
}: Props) {
  const [phase, setPhase] = useState<Phase>("watching");
  const phaseRef = useRef<Phase>("watching");
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const promptTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selfDisconnectRef = useRef(false);

  const setPhaseSafe = useCallback((next: Phase) => {
    phaseRef.current = next;
    setPhase(next);
  }, []);

  const clearTimers = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
    if (promptTimerRef.current) {
      clearTimeout(promptTimerRef.current);
      promptTimerRef.current = null;
    }
  }, []);

  const armIdle = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    idleTimerRef.current = setTimeout(() => {
      if (phaseRef.current !== "watching") return;
      setPhaseSafe("prompt");
    }, IDLE_MS);
  }, [setPhaseSafe]);

  const confirmPresence = useCallback(() => {
    clearTimers();
    setPhaseSafe("watching");
    armIdle();
  }, [armIdle, clearTimers, setPhaseSafe]);

  const dismissDisconnected = useCallback(() => {
    setPhaseSafe("watching");
  }, [setPhaseSafe]);

  // Session lifecycle: active → watch; user clear → drop prompt; keep disconnected banner.
  useEffect(() => {
    if (sessionId) {
      selfDisconnectRef.current = false;
      clearTimers();
      setPhaseSafe("watching");
      armIdle();
      return;
    }
    clearTimers();
    if (!selfDisconnectRef.current && phaseRef.current !== "disconnected") {
      setPhaseSafe("watching");
    }
  }, [sessionId, armIdle, clearTimers, setPhaseSafe]);

  // Activity resets idle only while actively watching a live session.
  useEffect(() => {
    if (!sessionId || phase !== "watching") return;

    const onActivity = () => armIdle();
    for (const ev of ACTIVITY_EVENTS) {
      window.addEventListener(ev, onActivity, { passive: true });
    }
    return () => {
      for (const ev of ACTIVITY_EVENTS) {
        window.removeEventListener(ev, onActivity);
      }
    };
  }, [sessionId, phase, armIdle]);

  // Prompt window → disconnect + stop processing.
  useEffect(() => {
    if (phase !== "prompt" || !sessionId) return;

    promptTimerRef.current = setTimeout(() => {
      void (async () => {
        selfDisconnectRef.current = true;
        setPhaseSafe("disconnected");
        clearTimers();
        try {
          await onIdleDisconnect();
        } catch {
          // Session may already be gone; UI still shows disconnected.
        }
      })();
    }, PROMPT_MS);

    return () => {
      if (promptTimerRef.current) {
        clearTimeout(promptTimerRef.current);
        promptTimerRef.current = null;
      }
    };
  }, [phase, sessionId, onIdleDisconnect, clearTimers, setPhaseSafe]);

  useEffect(() => () => clearTimers(), [clearTimers]);

  if (phase === "prompt") {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 p-4 backdrop-blur-[2px]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="idle-prompt-title"
      >
        <div className="w-full max-w-sm border border-border bg-surface p-5 shadow-none">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            Presence check
          </p>
          <h2
            id="idle-prompt-title"
            className="mt-2 text-lg font-semibold tracking-tight text-fg"
          >
            Still there?
          </h2>
          <p className="mt-2 text-sm text-muted">
            No activity detected. Confirm within{" "}
            <span className="font-mono text-fg">{PROMPT_MS / 1000}s</span> or
            this session stops processing.
          </p>
          <button
            type="button"
            autoFocus
            onClick={confirmPresence}
            className="mt-5 w-full border border-accent bg-transparent px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-accent transition-colors duration-200 hover:bg-accent/10"
          >
            I&apos;m here
          </button>
        </div>
      </div>
    );
  }

  if (phase === "disconnected") {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-bg/80 p-4 backdrop-blur-[2px]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="idle-disconnected-title"
      >
        <div className="w-full max-w-sm border border-border bg-surface p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-live">
            Session ended
          </p>
          <h2
            id="idle-disconnected-title"
            className="mt-2 text-lg font-semibold tracking-tight text-fg"
          >
            Disconnected for inactivity
          </h2>
          <p className="mt-2 text-sm text-muted">
            Live chat ingest and classification stopped. Start again when you are
            back.
          </p>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              autoFocus
              onClick={() => {
                dismissDisconnected();
                onReconnect();
              }}
              className="flex-1 border border-accent px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-accent transition-colors duration-200 hover:bg-accent/10"
            >
              Reconnect
            </button>
            <button
              type="button"
              onClick={dismissDisconnected}
              className="flex-1 border border-border px-3 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-muted transition-colors duration-200 hover:border-fg hover:text-fg"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
