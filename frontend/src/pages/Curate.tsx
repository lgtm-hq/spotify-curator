import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { PlaylistPreview, type CurateProposal } from "../components/PlaylistPreview";
import { useBackgroundActivity } from "../contexts/backgroundActivity";
import { useCancellableMutation, isRequestCancelled } from "../hooks/useCancellableMutation";
import { useSpotifyUsage } from "../hooks/useSpotifyUsage";
import {
  clearCurateSession,
  loadCurateSession,
  saveCurateSession,
} from "../utils/pageSessionStorage";

interface ChatMessage {
  role: "assistant" | "user";
  content: string;
}

interface CurateSessionSnapshot {
  sessionId: string | null;
  messages: ChatMessage[];
  options: string[];
  input: string;
  done: boolean;
  proposal: CurateProposal | null;
}

function loadInitialCurateState(): CurateSessionSnapshot {
  return (
    loadCurateSession<CurateSessionSnapshot>() ?? {
      sessionId: null,
      messages: [],
      options: [],
      input: "",
      done: false,
      proposal: null,
    }
  );
}

type ErrorStage = "start" | "answer" | "build" | "save" | null;

function LoadingBubble({ label }: { label: string }) {
  return (
    <div className="max-w-xl rounded-2xl bg-zinc-800 px-4 py-3 text-zinc-100">
      <div className="flex items-center gap-3">
        <span className="inline-flex gap-1">
          <span className="h-2 w-2 animate-bounce rounded-full bg-emerald-400 [animation-delay:-0.3s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-emerald-400 [animation-delay:-0.15s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-emerald-400" />
        </span>
        <span className="text-sm text-zinc-400">{label}</span>
      </div>
    </div>
  );
}

function ErrorBanner({
  message,
  onRetry,
  retryLabel,
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
      <p className="text-sm text-red-300">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg border border-red-400/40 px-3 py-1.5 text-sm text-red-200 transition hover:bg-red-500/10"
        >
          {retryLabel ?? "Try again"}
        </button>
      )}
    </div>
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export function Curate() {
  const { rateLimited } = useSpotifyUsage();
  const { setCurateActivity } = useBackgroundActivity();
  const initialCurateState = useMemo(() => loadInitialCurateState(), []);
  const [sessionId, setSessionId] = useState<string | null>(initialCurateState.sessionId);
  const [messages, setMessages] = useState<ChatMessage[]>(initialCurateState.messages);
  const [options, setOptions] = useState<string[]>(initialCurateState.options);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [input, setInput] = useState(initialCurateState.input);
  const [done, setDone] = useState(initialCurateState.done);
  const [errorStage, setErrorStage] = useState<ErrorStage>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [proposal, setProposal] = useState<CurateProposal | null>(initialCurateState.proposal);
  const [refineOpen, setRefineOpen] = useState(false);
  const [refineInput, setRefineInput] = useState("");
  const pendingAnswerRef = useRef<string | null>(null);

  const resetInterview = () => {
    clearCurateSession();
    setSessionId(null);
    setMessages([]);
    setOptions([]);
    setSelectedOptions([]);
    setInput("");
    setDone(false);
    setErrorStage(null);
    setErrorText(null);
    setProposal(null);
    setRefineOpen(false);
    setRefineInput("");
    pendingAnswerRef.current = null;
  };

  const clearError = () => {
    setErrorStage(null);
    setErrorText(null);
  };

  const revertPendingAnswer = () => {
    const pendingAnswer = pendingAnswerRef.current;
    if (!pendingAnswer) return;
    setMessages((prev) =>
      prev.filter((msg) => !(msg.role === "user" && msg.content === pendingAnswer)),
    );
    pendingAnswerRef.current = null;
  };

  const start = useCancellableMutation((_variables, signal) => api.curateStart({ signal }), {
    onMutate: () => {
      clearError();
      resetInterview();
    },
    onSuccess: (data) => {
      setSessionId(data.session_id);
      setDone(Boolean(data.done));
      if (data.question) {
        setMessages([{ role: "assistant", content: data.question }]);
      }
      setOptions(data.options ?? []);
    },
    onError: (error) => {
      if (isRequestCancelled(error)) return;
      setErrorStage("start");
      setErrorText(errorMessage(error));
    },
  });

  const build = useCancellableMutation(
    ({ sessionId, feedback }: { sessionId: string; feedback?: string }, signal) =>
      api.curateBuild(sessionId, feedback, { signal }),
    {
      onMutate: () => clearError(),
      onSuccess: (data) => setProposal(data),
      onError: (error) => {
        if (isRequestCancelled(error)) return;
        setErrorStage("build");
        setErrorText(errorMessage(error));
      },
    },
  );

  const answer = useCancellableMutation(
    ({ sessionId, answer }: { sessionId: string; answer: string }, signal) =>
      api.curateAnswer(sessionId, answer, { signal }),
    {
      onMutate: () => clearError(),
      onSuccess: (data) => {
        pendingAnswerRef.current = null;
        setDone(Boolean(data.done));
        setSelectedOptions([]);
        if (data.question) {
          setMessages((prev) => [...prev, { role: "assistant", content: data.question ?? "" }]);
        }
        setOptions(data.options ?? []);
        if (data.done && sessionId) {
          build.mutate({ sessionId });
        }
      },
      onError: (error, variables) => {
        pendingAnswerRef.current = null;
        setMessages((prev) =>
          prev.filter((msg) => !(msg.role === "user" && msg.content === variables.answer)),
        );
        if (isRequestCancelled(error)) return;
        setErrorStage("answer");
        setErrorText(errorMessage(error));
      },
    },
  );

  const queryClient = useQueryClient();

  const save = useCancellableMutation(
    ({ sessionId, trackUris }: { sessionId: string; trackUris: string[] }, signal) =>
      api.curateSave(sessionId, trackUris, { signal }),
    {
      onMutate: () => clearError(),
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: ["playlists"] });
      },
      onError: (error) => {
        if (isRequestCancelled(error)) return;
        setErrorStage("save");
        setErrorText(errorMessage(error));
      },
    },
  );

  const isBusy =
    rateLimited || start.isPending || answer.isPending || build.isPending || save.isPending;

  const cancelBusy = () => {
    if (answer.isPending) {
      revertPendingAnswer();
      answer.cancel();
      return;
    }
    if (build.isPending) {
      build.cancel();
      return;
    }
    if (save.isPending) {
      save.cancel();
      return;
    }
    if (start.isPending) {
      start.cancel();
    }
  };

  useEffect(() => {
    setCurateActivity({
      busy: isBusy,
      hasResults: proposal !== null,
    });
  }, [proposal, isBusy, setCurateActivity]);

  useEffect(() => {
    saveCurateSession({
      sessionId,
      messages,
      options,
      input,
      done,
      proposal,
    } satisfies CurateSessionSnapshot);
  }, [sessionId, messages, options, input, done, proposal]);

  const pendingLabel = useMemo(() => {
    if (start.isPending) return "Starting interview…";
    if (answer.isPending) return "Thinking about your vibe…";
    if (build.isPending) return "Building your playlist…";
    if (save.isPending) return "Saving to Spotify…";
    return "";
  }, [start.isPending, answer.isPending, build.isPending, save.isPending]);

  const toggleOption = (option: string) => {
    setSelectedOptions((prev) =>
      prev.includes(option) ? prev.filter((item) => item !== option) : [...prev, option],
    );
  };

  const composeAnswer = () => {
    const parts = [...selectedOptions];
    const trimmed = input.trim();
    if (trimmed) parts.push(trimmed);
    return parts.join(", ");
  };

  const sendAnswer = () => {
    const text = composeAnswer();
    if (!sessionId || !text.trim() || isBusy) return;
    pendingAnswerRef.current = text;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSelectedOptions([]);
    answer.mutate({ sessionId, answer: text });
  };

  const retryBuild = () => {
    if (!sessionId) return;
    clearError();
    build.mutate({ sessionId });
  };

  const openRefine = () => {
    clearError();
    setRefineOpen(true);
    setRefineInput("");
  };

  const cancelRefine = () => {
    setRefineOpen(false);
    setRefineInput("");
  };

  const submitRefine = () => {
    if (!sessionId || build.isPending) return;
    const feedback = refineInput.trim();
    if (!feedback) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: feedback },
      {
        role: "assistant",
        content: "Got it — I'll rebuild the playlist with that in mind.",
      },
    ]);
    setRefineOpen(false);
    setRefineInput("");
    build.mutate({ sessionId, feedback });
  };

  const rebuildFromBrief = () => {
    if (!sessionId || build.isPending) return;
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "Rebuilding from your original brief with a fresh set of picks…",
      },
    ]);
    setRefineOpen(false);
    setRefineInput("");
    build.mutate({ sessionId });
  };

  const removeTrack = (trackId: string) => {
    setProposal((current) => {
      if (!current) return current;
      const tracks = current.tracks.filter((track) => track.id !== trackId);
      return {
        ...current,
        tracks,
        track_uris: tracks.map((track) => track.uri),
      };
    });
  };

  const canSend = Boolean(sessionId && !done && composeAnswer().trim() && !isBusy);
  const showChatLoading = isBusy && pendingLabel && !(proposal && build.isPending);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Mood Concierge</h2>
          <p className="text-zinc-400">
            Answer a few questions and we&apos;ll build a playlist for your vibe.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {isBusy && (
            <button
              type="button"
              onClick={cancelBusy}
              className="rounded-lg border border-emerald-400/40 px-4 py-2 text-sm text-emerald-200 hover:bg-emerald-500/10"
            >
              Cancel
            </button>
          )}
          {sessionId && (
            <button
              type="button"
              onClick={resetInterview}
              disabled={isBusy}
              className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-60"
            >
              New interview
            </button>
          )}
          {!sessionId && (
            <button
              type="button"
              onClick={() => start.mutate()}
              disabled={start.isPending || rateLimited}
              className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black transition hover:bg-emerald-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {start.isPending ? "Starting…" : "Start interview"}
            </button>
          )}
        </div>
      </div>

      <div className="min-h-[400px] space-y-4 rounded-xl border border-white/10 bg-white/5 p-6">
        {!sessionId && !start.isPending && messages.length === 0 && (
          <p className="text-center text-zinc-500">
            Click &ldquo;Start interview&rdquo; to begin your mood concierge session.
          </p>
        )}

        {messages.map((msg, idx) => (
          <div
            key={`${msg.role}-${idx}`}
            className={`max-w-xl rounded-2xl px-4 py-3 ${
              msg.role === "assistant"
                ? "bg-zinc-800 text-zinc-100"
                : "ml-auto bg-emerald-500/20 text-emerald-100"
            }`}
          >
            {msg.content}
          </div>
        ))}

        {showChatLoading && <LoadingBubble label={pendingLabel} />}

        {errorText && errorStage === "start" && (
          <ErrorBanner
            message={errorText}
            onRetry={() => start.mutate()}
            retryLabel="Restart interview"
          />
        )}

        {errorText && errorStage === "answer" && <ErrorBanner message={errorText} />}

        {errorText && errorStage === "build" && (
          <ErrorBanner message={errorText} onRetry={retryBuild} retryLabel="Retry playlist build" />
        )}

        {!done && options.length > 0 && !isBusy && (
          <div className="space-y-2">
            <p className="text-xs text-zinc-500">Select one or more, then send.</p>
            <div className="flex flex-wrap gap-2">
              {options.map((option) => {
                const selected = selectedOptions.includes(option);
                return (
                  <button
                    key={option}
                    type="button"
                    onClick={() => toggleOption(option)}
                    aria-pressed={selected}
                    className={`rounded-full border px-4 py-2 text-sm transition ${
                      selected
                        ? "border-emerald-400 bg-emerald-500/20 text-emerald-200"
                        : "border-emerald-500/30 text-emerald-300 hover:border-emerald-400/60 hover:bg-emerald-500/10"
                    }`}
                  >
                    {option}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {sessionId && !done && (
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              sendAnswer();
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Add your own answer (optional)…"
              disabled={isBusy}
              className="flex-1 rounded-lg border border-white/10 bg-black px-4 py-2 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!canSend}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-black transition hover:bg-emerald-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
            </button>
          </form>
        )}

        {done && !proposal && !build.isPending && errorStage !== "build" && (
          <p className="text-sm text-zinc-400">Interview complete — building your playlist…</p>
        )}
      </div>

      {proposal && (
        <div className="space-y-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6">
          {build.isPending && (
            <div className="rounded-lg border border-violet-500/20 bg-violet-500/5 px-4 py-3 text-sm text-violet-200">
              Rebuilding your playlist…
            </div>
          )}

          <div className={build.isPending ? "pointer-events-none opacity-60" : undefined}>
            <div>
              <h3 className="mb-2 text-xl font-semibold">{proposal.name}</h3>
              <p className="mb-2 text-zinc-300">{proposal.description}</p>
              <details className="rounded-lg border border-white/10 bg-black/20 px-4 py-3">
                <summary className="cursor-pointer text-sm text-zinc-400">Why these picks?</summary>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">{proposal.reasoning}</p>
              </details>
            </div>

            <PlaylistPreview tracks={proposal.tracks} onRemove={removeTrack} />
          </div>

          {errorText && errorStage === "save" && <ErrorBanner message={errorText} />}

          {refineOpen && !build.isPending && (
            <div className="space-y-3 rounded-lg border border-emerald-500/20 bg-black/20 p-4">
              <p className="text-sm text-zinc-300">
                What would you like to change? Your note becomes part of the conversation.
              </p>
              <textarea
                value={refineInput}
                onChange={(event) => setRefineInput(event.target.value)}
                placeholder="e.g. Full-band but softer, more 2000s pop-punk, keep at least 25 tracks…"
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-black px-4 py-3 text-sm disabled:opacity-60"
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={submitRefine}
                  disabled={!refineInput.trim() || rateLimited}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-black transition hover:bg-emerald-400 disabled:opacity-50"
                >
                  Apply feedback & rebuild
                </button>
                <button
                  type="button"
                  onClick={rebuildFromBrief}
                  disabled={rateLimited}
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5 disabled:opacity-50"
                >
                  Build again from brief
                </button>
                <button
                  type="button"
                  onClick={cancelRefine}
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-400 hover:bg-white/5"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() =>
                sessionId &&
                save.mutate({
                  sessionId,
                  trackUris: proposal.track_uris,
                })
              }
              disabled={
                save.isPending || proposal.tracks.length === 0 || rateLimited || build.isPending
              }
              className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black transition hover:bg-emerald-400 active:scale-[0.98] disabled:opacity-60"
            >
              {save.isPending ? "Saving…" : `Save ${proposal.tracks.length} tracks to Spotify`}
            </button>
            {!refineOpen && (
              <button
                type="button"
                onClick={openRefine}
                disabled={build.isPending || rateLimited}
                className="rounded-lg border border-white/10 px-4 py-2 transition hover:bg-white/5 disabled:opacity-60"
              >
                Refine
              </button>
            )}
          </div>
          {save.isSuccess && save.data && (
            <div className="space-y-3">
              <p className="text-emerald-400">
                Playlist saved!
                {save.data.name ? ` · ${save.data.name}` : ""}
              </p>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/playlists/${save.data.playlist_id}`}
                  className="rounded-lg border border-emerald-400/40 px-4 py-2 text-sm text-emerald-200 hover:bg-emerald-500/10"
                >
                  Open in app
                </Link>
                <a
                  href={`https://open.spotify.com/playlist/${save.data.playlist_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-zinc-300 hover:bg-white/5"
                >
                  Open in Spotify
                </a>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
