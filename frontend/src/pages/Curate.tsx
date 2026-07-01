import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";

interface ChatMessage {
  role: "assistant" | "user";
  content: string;
}

export function Curate() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [options, setOptions] = useState<string[]>([]);
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
    onSuccess: (data) => {
      setSessionId(data.session_id);
      setDone(Boolean(data.done));
      if (data.question) {
        setMessages([{ role: "assistant", content: data.question }]);
      }
      setOptions(data.options ?? []);
    },
  });

  const answer = useMutation({
    mutationFn: ({ sessionId, answer }: { sessionId: string; answer: string }) =>
      api.curateAnswer(sessionId, answer),
    onSuccess: (data) => {
      setDone(Boolean(data.done));
      if (data.question) {
        setMessages((prev) => [...prev, { role: "assistant", content: data.question ?? "" }]);
      }
      setOptions(data.options ?? []);
      if (data.done && sessionId) {
        build.mutate({ sessionId });
      }
    },
  });

  const build = useMutation({
    mutationFn: ({ sessionId, feedback }: { sessionId: string; feedback?: string }) =>
      api.curateBuild(sessionId, feedback),
    onSuccess: (data) => setProposal(data),
  });

  const save = useMutation({
    mutationFn: (sessionId: string) => api.curateSave(sessionId),
  });

  const sendAnswer = (text: string) => {
    if (!sessionId || !text.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    answer.mutate({ sessionId, answer: text });
  };

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
            className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black"
          >
            Start interview
          </button>
        )}
      </div>

      <div className="min-h-[400px] space-y-4 rounded-xl border border-white/10 bg-white/5 p-6">
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

        {!done && options.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {options.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => sendAnswer(option)}
                className="rounded-full border border-emerald-500/30 px-4 py-2 text-sm text-emerald-300 hover:bg-emerald-500/10"
              >
                {option}
              </button>
            ))}
          </div>
        )}

        {sessionId && !done && (
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              sendAnswer(input);
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your answer..."
              className="flex-1 rounded-lg border border-white/10 bg-black px-4 py-2"
            />
            <button type="submit" className="rounded-lg bg-emerald-500 px-4 py-2 text-black">
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
              className="rounded-lg bg-emerald-500 px-4 py-2 font-medium text-black"
            >
              Save to Spotify
            </button>
            <button
              type="button"
              onClick={() =>
                sessionId && build.mutate({ sessionId, feedback: "more upbeat, less pop" })
              }
              className="rounded-lg border border-white/10 px-4 py-2"
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
