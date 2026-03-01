"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { IconMic, IconStop, IconWave } from "@/components/ui/icons";
import { MarkdownMessage } from "@/components/markdown-message";
import {
  createSession,
  fetchAgent,
  fetchMessages,
  fetchSessions,
  sendMessage,
  transcribeAudio,
  type Agent,
  type Message,
  type Session,
} from "@/lib/api";
import { isMockLoggedIn } from "@/lib/mock-auth";

export default function EndUserChatPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = Array.isArray(params.id) ? params.id[0] : params.id;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isDictating, setIsDictating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMultilineInput, setIsMultilineInput] = useState(false);
  const [pendingMessageId, setPendingMessageId] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) || null,
    [sessions, activeSessionId],
  );

  useEffect(() => {
    if (!isMockLoggedIn()) {
      router.replace("/");
      return;
    }
    setAuthReady(true);
  }, [router]);

  useEffect(() => {
    if (!authReady || !agentId) return;
    let active = true;

    const init = async () => {
      setLoading(true);
      try {
        const [agentData, sessionData] = await Promise.all([
          fetchAgent(agentId),
          fetchSessions(agentId),
        ]);
        if (!active) return;

        setAgent(agentData);
        setSessions(sessionData);

        if (sessionData.length > 0) {
          setActiveSessionId(sessionData[0].id);
          const initialMessages = await fetchMessages(sessionData[0].id);
          if (!active) return;
          setMessages(initialMessages);
        } else {
          const first = await createSession(agentId, "New session");
          if (!active) return;
          setSessions([first]);
          setActiveSessionId(first.id);
          setMessages([]);
        }
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load chat.");
      } finally {
        if (active) setLoading(false);
      }
    };

    init();
    return () => {
      active = false;
    };
  }, [agentId, authReady]);

  const selectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    const data = await fetchMessages(sessionId);
    setMessages(data);
  };

  const createNewSession = async () => {
    if (!agentId) return;
    const session = await createSession(agentId, `Session ${sessions.length + 1}`);
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setMessages([]);
  };

  const submit = async () => {
    if (!activeSessionId || !draft.trim() || sending) return;
    const userText = draft.trim();
    const optimisticId = `pending-${Date.now()}`;
    const optimisticMessage: Message = {
      id: optimisticId,
      session_id: activeSessionId,
      role: "user",
      content: userText,
      created_at: new Date().toISOString(),
    };

    setSending(true);
    setPendingMessageId(optimisticId);
    setError(null);
    setDraft("");
    setMessages((prev) => [...prev, optimisticMessage]);
    try {
      const data = await sendMessage(activeSessionId, userText);
      setMessages(data);
      setPendingMessageId(null);
      const updated = await fetchSessions(agentId as string);
      setSessions(updated);
    } catch (err) {
      setPendingMessageId(null);
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      setDraft(userText);
      setError(err instanceof Error ? err.message : "Failed to send message.");
    } finally {
      setSending(false);
    }
  };

  const startDictation = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
        const file = new File([audioBlob], "dictation.webm", { type: "audio/webm" });
        try {
          const text = await transcribeAudio(file);
          if (text.trim()) {
            setDraft((prev) => (prev ? `${prev}\n${text}` : text));
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Voice-to-text failed.");
        } finally {
          setIsDictating(false);
        }
      };

      recorder.start();
      setIsDictating(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Microphone access failed.");
    }
  };

  const stopDictation = () => {
    mediaRecorderRef.current?.stop();
  };

  const handleDraftChange = (value: string) => {
    setDraft(value);
    const lineCount = value.split("\n").length;
    const byWrapHeight = textareaRef.current
      ? textareaRef.current.scrollHeight > 60
      : false;
    setIsMultilineInput(lineCount > 1 || byWrapHeight);
  };

  if (!authReady) {
    return <main className="h-[calc(100dvh-3.5rem)] overflow-hidden bg-white" />;
  }

  if (loading) {
    return <main className="h-[calc(100dvh-3.5rem)] overflow-hidden bg-white px-6 py-8 text-zinc-900">Loading chat...</main>;
  }

  if (error || !agent) {
    return (
      <main className="h-[calc(100dvh-3.5rem)] overflow-hidden bg-white px-6 py-8 text-zinc-900">
        <p className="text-red-700">{error || "Agent not found."}</p>
      </main>
    );
  }

  return (
    <main className="h-[calc(100dvh-3.5rem)] overflow-hidden bg-white text-zinc-900">
      <div className="mx-auto flex h-full max-w-7xl overflow-hidden border-x border-zinc-200">
        {sidebarOpen ? (
          <aside className="hidden h-full w-80 border-r border-zinc-200 bg-zinc-50 md:flex md:flex-col">
            <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
              <h2 className="text-sm font-semibold">Sessions</h2>
              <Button size="sm" variant="outline" onClick={() => setSidebarOpen(false)}>
                Hide
              </Button>
            </div>
            <div className="p-3">
              <Button className="w-full" onClick={createNewSession}>
                New Session
              </Button>
            </div>
            <div className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                    session.id === activeSessionId
                      ? "border-zinc-900 bg-zinc-900 text-white"
                      : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100"
                  }`}
                  onClick={() => selectSession(session.id)}
                >
                  <p className="font-medium">{session.title}</p>
                  <p className="text-xs opacity-70">{new Date(session.updated_at).toLocaleString()}</p>
                </button>
              ))}
            </div>
          </aside>
        ) : (
          <div className="hidden border-r border-zinc-200 p-3 md:block">
            <Button size="sm" variant="outline" onClick={() => setSidebarOpen(true)}>
              Show Sessions
            </Button>
          </div>
        )}

        {sidebarOpen ? (
          <div className="fixed inset-0 z-40 md:hidden">
            <button
              type="button"
              aria-label="Close sessions"
              className="absolute inset-0 bg-black/40"
              onClick={() => setSidebarOpen(false)}
            />
            <aside className="absolute inset-0 flex flex-col bg-zinc-50">
              <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
                <h2 className="text-base font-semibold">Sessions</h2>
                <Button size="sm" variant="outline" onClick={() => setSidebarOpen(false)}>
                  Close
                </Button>
              </div>
              <div className="p-3">
                <Button className="w-full" onClick={createNewSession}>
                  New Session
                </Button>
              </div>
              <div className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                      session.id === activeSessionId
                        ? "border-zinc-900 bg-zinc-900 text-white"
                        : "border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-100"
                    }`}
                    onClick={() => {
                      selectSession(session.id);
                      setSidebarOpen(false);
                    }}
                  >
                    <p className="font-medium">{session.title}</p>
                    <p className="text-xs opacity-70">{new Date(session.updated_at).toLocaleString()}</p>
                  </button>
                ))}
              </div>
            </aside>
          </div>
        ) : null}

        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-5 py-4">
            <div className="min-w-0">
              <h1 className="text-lg font-semibold">{agent.name}</h1>
              <p className="text-xs text-zinc-500">{activeSession?.title || "Session"}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="md:hidden"
                onClick={() => setSidebarOpen(true)}
              >
                Sessions
              </Button>
            </div>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto bg-white px-5 py-4">
            {messages.length === 0 ? (
              <p className="text-sm text-zinc-500">Start a conversation.</p>
            ) : (
              <>
                {messages.map((message) => (
                  <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                        message.role === "user"
                          ? "bg-zinc-900 text-white"
                          : "bg-zinc-100 text-zinc-900"
                      }`}
                    >
                      {message.role === "assistant" ? (
                        <MarkdownMessage content={message.content} />
                      ) : (
                        <p className="whitespace-pre-wrap">{message.content}</p>
                      )}
                    </div>
                  </div>
                ))}
                {sending && pendingMessageId ? (
                  <div className="flex justify-start">
                    <div className="inline-flex items-center gap-2 rounded-2xl bg-zinc-100 px-4 py-3 text-sm text-zinc-700">
                      <span className="inline-flex gap-1">
                        <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:-0.2s]" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500 [animation-delay:-0.1s]" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-zinc-500" />
                      </span>
                      Agent is typing...
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </div>

          {error ? (
            <div className="border-t border-red-500/70 bg-red-100 px-5 py-3 text-sm text-red-700">{error}</div>
          ) : null}

          <div className="border-t border-zinc-200 bg-white px-5 py-4">
            <div className={`flex gap-2 ${isMultilineInput ? "items-end" : "items-center"}`}>
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => handleDraftChange(e.target.value)}
                placeholder="Type your message..."
                className="min-h-[52px] flex-1 rounded-xl border border-zinc-200 px-4 py-3 text-sm focus:border-zinc-400 focus:outline-none"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    e.stopPropagation();
                    submit();
                  }
                }}
              />
              <Button
                type="button"
                variant={isDictating ? "primary" : "outline"}
                onClick={isDictating ? stopDictation : startDictation}
                disabled={sending}
                title={isDictating ? "Stop dictation" : "Start voice-to-text"}
                className={`h-16 w-16 rounded-full p-0 ${isDictating ? "text-white" : "text-zinc-900"}`}
              >
                {isDictating ? (
                  <IconStop className="h-10 w-10" />
                ) : (
                  <IconMic className="h-10 w-10" />
                )}
              </Button>
              <Button
                asChild
                type="button"
                variant="outline"
                title="Open speech-to-speech"
                className="h-16 w-16 rounded-full p-0 text-zinc-900"
              >
                <Link href={`/chat/${agent.id}/voice`} aria-label="Open speech-to-speech">
                  <IconWave className="h-10 w-10" />
                </Link>
              </Button>
            </div>
            <p className="mt-2 text-xs text-zinc-500">Press Enter to send. Press Shift+Enter for a new line.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
