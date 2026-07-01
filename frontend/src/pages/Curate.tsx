import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../api/client";

interface ChatMessage {
  role: "assistant" | "user";
  content: string;
}

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

export function Curate() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [options, setOptions] = useState<string[]>([]);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [done, setDone] = useState(false);
  const [proposal, setProposal] = useState<{
    name: string;
    description: string;
    track_uris: string[];
    reasoning: string;
  } | null>(null);

  const start = useMutation({
    mutationFn: api.curateStart,
    onMutate: () => {
      setMessages([]);
      setOptions([]);
      setSelectedOptions([]);
      setInput("");
      setDone(false);
      setProposal(null);
    },
    onSuccess: (data) => {
      setSessionId(data.session_id);
      setDone(Boolean(data.done));
      if (data.question) {
        setMessages([{ role: "assistant", content: data.question }]);
      }
      setOptions(data.options ?? []);
    },
  });

  const build = useMutation({
    mutationFn: ({ sessionId, feedback }: { sessionId: string; feedback?: string }) =>
      api.curateBuild(sessionId, feedback),
    onSuccess: (data) => setProposal(data),
  });

  const answer = useMutation({
    mutationFn: ({ sessionId, answer }: { sessionId: string; answer: string }) =>
      api.curateAnswer(sessionId, answer),
    onSuccess: (data) => {
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
  });

  const save = useMutation({
    mutationFn: (sessionId: string) => api.curateSave(sessionId),
  });

  const isBusy = start.isPending || answer.isPending || build.isPending;

  const pendingLabel = useMemo(() => {
    if (start.isPending) return "Starting interview…";
    if (answer.isPending) return "Thinking about your vibe…";
    if (build.isPending) return "Building your playlist…";
    return "";
  }, [start.isPending, answer.isPending, build.isPending]);

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
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSelectedOptions([]);
    answer.mutate({ sessionId, answer: text });
  };

  const canSend = Boolean(sessionId && !done && composeAnswer().trim() && !isBusy);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Mood Concierge</h2>
          <p className="text-zinc-400">
            Answer a few questions and we&apos;ll build a playlist for your vibe.
          </p>
        </div>
        {!sessionId && (
          <button
            type="button"
            onClick={() => start.mutate()}
            disabled={start.isPending}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black transition hover:bg-emerald-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {start.isPending ? "Starting…" : "Start interview"}
          </button>
        )}
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

        {isBusy && pendingLabel && <LoadingBubble label={pendingLabel} />}

        {(start.isError || answer.isError || build.isError) && (
          <p className="text-sm text-red-400">
            Something went wrong. Please try again.
          </p>
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
      </div>

      {proposal && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6">
          <h3 className="mb-2 text-xl font-semibold">{proposal.name}</h3>
          <p className="mb-2 text-zinc-300">{proposal.description}</p>
          <p className="mb-4 text-sm text-zinc-400">{proposal.reasoning}</p>
          <p className="mb-4 text-sm">{proposal.track_uris.length} tracks selected</p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => sessionId && save.mutate(sessionId)}
              disabled={save.isPending}
              className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black transition hover:bg-emerald-400 active:scale-[0.98] disabled:opacity-60"
            >
              {save.isPending ? "Saving…" : "Save to Spotify"}
            </button>
            <button
              type="button"
              onClick={() =>
                sessionId && build.mutate({ sessionId, feedback: "more upbeat, less pop" })
              }
              disabled={build.isPending}
              className="rounded-lg border border-white/10 px-4 py-2 transition hover:bg-white/5 disabled:opacity-60"
            >
              Refine
            </button>
          </div>
          {save.isSuccess && <p className="mt-3 text-emerald-400">Playlist saved!</p>}
        </div>
      )}
    </div>
  );
}
