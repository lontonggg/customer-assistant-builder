"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  createSession,
  fetchMessages,
  sendMessage,
  type Agent,
  type Message,
  type Session,
} from "@/lib/api";

interface ChatPanelProps {
  agent: Agent;
}

export function ChatPanel({ agent }: ChatPanelProps) {
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoadingSession, setIsLoadingSession] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  useEffect(() => {
    let active = true;

    const initSession = async () => {
      setIsLoadingSession(true);
      setError(null);
      try {
        const newSession = await createSession(agent.id, `Chat with ${agent.name}`);
        if (!active) return;
        setSession(newSession);
        const history = await fetchMessages(newSession.id);
        if (!active) return;
        setMessages(history);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to start chat session.");
      } finally {
        if (active) setIsLoadingSession(false);
      }
    };

    initSession();

    return () => {
      active = false;
    };
  }, [agent.id, agent.name]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || !draft.trim() || isSending) return;

    setIsSending(true);
    setError(null);
    try {
      const updated = await sendMessage(session.id, draft.trim());
      setMessages(updated);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
        <span className="text-sm text-zinc-600">
          {session ? `Session: ${session.id.slice(0, 8)}...` : "Starting session..."}
        </span>
        <span className="text-xs text-zinc-500">Model: {agent.model}</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {isLoadingSession ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-zinc-500">Preparing chat...</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <h3 className="text-lg font-semibold text-zinc-900">Chat with {agent.name}</h3>
            <p className="mt-2 max-w-sm text-sm text-zinc-500">
              Send your first message to start chatting with your agent.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    message.role === "user" ? "bg-zinc-100 text-zinc-900" : "bg-zinc-100 text-zinc-900"
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  <p className="mt-1 text-[10px] text-zinc-500">
                    {new Date(message.created_at).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
        {isSending ? (
          <p className="mt-3 text-xs text-zinc-500">Agent is thinking...</p>
        ) : null}
        <div ref={endRef} />
      </div>

      {error ? (
        <div className="border-t border-red-500/70 bg-red-100 px-4 py-3">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="border-t border-zinc-200 p-4">
        <div className="flex gap-3">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={!session || isLoadingSession || isSending}
            placeholder="Type your message..."
            className="flex-1 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-900 placeholder:text-zinc-900/40 focus:border-zinc-400 focus:outline-none"
          />
          <Button type="submit" disabled={!draft.trim() || !session || isLoadingSession || isSending}>
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}
