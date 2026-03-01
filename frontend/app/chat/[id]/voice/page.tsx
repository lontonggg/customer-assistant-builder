"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { IconMic, IconStop } from "@/components/ui/icons";
import {
  createSession,
  fetchAgent,
  fetchSessions,
  sendMessage,
  synthesizeSpeech,
  transcribeAudio,
  type Agent,
  type Session,
} from "@/lib/api";
import { isMockLoggedIn } from "@/lib/mock-auth";

type VoicePhase = "idle" | "greeting" | "listening" | "thinking" | "speaking";

export default function VoiceInterfacePage() {
  const params = useParams();
  const router = useRouter();
  const agentId = Array.isArray(params.id) ? params.id[0] : params.id;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<VoicePhase>("idle");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const stopRef = useRef(false);
  const runningRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!isMockLoggedIn()) {
      router.replace("/");
      return;
    }
    setAuthReady(true);
  }, [router]);

  useEffect(() => {
    if (!authReady || !agentId) return;
    const init = async () => {
      const agentData = await fetchAgent(agentId);
      setAgent(agentData);
      const sessions = await fetchSessions(agentId);
      let target: Session;
      if (sessions.length > 0) {
        target = sessions[0];
      } else {
        target = await createSession(agentId, "Voice session");
      }
      setActiveSessionId(target.id);
    };
    init().catch((e) => setError(e instanceof Error ? e.message : "Failed to init voice mode."));
  }, [agentId, authReady]);

  const speak = useCallback(async (text: string, voiceGender: string) => {
    if (!text.trim() || stopRef.current) return;
    const audioUrl = await synthesizeSpeech(text, voiceGender);
    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    await audio.play();
    await new Promise<void>((resolve) => {
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
    });
    URL.revokeObjectURL(audioUrl);
  }, []);

  const listenAndTranscribe = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    const chunks: BlobPart[] = [];

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };

    const done = new Promise<string>((resolve, reject) => {
      recorder.onstop = async () => {
        try {
          stream.getTracks().forEach((t) => t.stop());
          const blob = new Blob(chunks, { type: "audio/webm" });
          const file = new File([blob], "voice.webm", { type: "audio/webm" });
          const text = await transcribeAudio(file);
          resolve(text.trim());
        } catch (err) {
          reject(err);
        }
      };
    });

    recorder.start();
    await new Promise((r) => setTimeout(r, 6000));
    if (recorder.state === "recording") recorder.stop();
    return done;
  }, []);

  const stopVoiceSession = useCallback(() => {
    stopRef.current = true;
    runningRef.current = false;
    setIsRunning(false);
    setPhase("idle");
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
  }, []);

  const startVoiceSession = useCallback(async () => {
    if (!activeSessionId || !agent || runningRef.current) return;
    stopRef.current = false;
    runningRef.current = true;
    setIsRunning(true);
    setError(null);

    try {
      setPhase("greeting");
      const greetMessages = await sendMessage(
        activeSessionId,
        "Start this call with one short friendly greeting and ask what the user needs."
      );
      const greetText =
        [...greetMessages].reverse().find((m) => m.role === "assistant")?.content ||
        `Hi! I'm ${agent.name}. How can I help you today?`;
      setPhase("speaking");
      await speak(greetText, agent.voice_gender || "female");

      while (!stopRef.current) {
        setPhase("listening");
        const userText = await listenAndTranscribe();
        if (stopRef.current) break;
        if (!userText) continue;

        setPhase("thinking");
        const messages = await sendMessage(activeSessionId, userText);
        const assistantText = [...messages].reverse().find((m) => m.role === "assistant")?.content || "";
        if (!assistantText) continue;

        setPhase("speaking");
        await speak(assistantText, agent.voice_gender || "female");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Speech-to-speech failed.");
    } finally {
      runningRef.current = false;
      setIsRunning(false);
      setPhase("idle");
    }
  }, [activeSessionId, agent, listenAndTranscribe, speak]);

  useEffect(() => {
    if (!authReady || !activeSessionId || !agent) return;
    startVoiceSession().catch((e) =>
      setError(e instanceof Error ? e.message : "Failed to start voice session.")
    );
    return () => {
      stopVoiceSession();
    };
  }, [activeSessionId, agent, startVoiceSession, stopVoiceSession, authReady]);

  if (!authReady) {
    return <main className="min-h-screen bg-white" />;
  }

  const statusLabel =
    phase === "listening"
      ? "Listening..."
      : phase === "thinking"
        ? "Thinking..."
        : phase === "speaking"
          ? "Speaking..."
          : phase === "greeting"
            ? "Starting..."
            : "Idle";

  const phaseTone =
    phase === "listening"
      ? "bg-emerald-400/20 border-emerald-300 text-emerald-700"
      : phase === "speaking"
        ? "bg-amber-300/20 border-amber-300 text-amber-700"
        : "bg-zinc-100 border-zinc-200 text-zinc-700";

  return (
    <main className="min-h-screen bg-white px-4 py-6 text-zinc-900 sm:px-6 sm:py-8">
      <div className="mx-auto max-w-3xl rounded-3xl border border-zinc-200 bg-zinc-50 p-5 sm:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-semibold sm:text-xl">Speech-to-Speech {agent ? `- ${agent.name}` : ""}</h1>
          <Button asChild variant="outline" size="sm">
            <Link href={`/chat/${agentId}`}>Back to Text Interface</Link>
          </Button>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 text-center">
          <p className="text-sm text-zinc-500">Live status</p>
          <div className="mt-4 flex justify-center">
            <div
              className={`relative h-24 w-24 rounded-full border ${phaseTone} ${
                phase === "listening" || phase === "speaking" ? "animate-pulse" : ""
              }`}
            >
              <div className="absolute inset-0 flex items-center justify-center">
                {phase === "speaking" ? (
                  <IconStop className="h-10 w-10" />
                ) : (
                  <IconMic className="h-10 w-10" />
                )}
              </div>
            </div>
          </div>
          <p className="mt-4 text-2xl font-semibold">{statusLabel}</p>

          <div className="mt-6 flex justify-center">
            {isRunning ? (
              <Button
                className="h-14 w-14 rounded-full p-0"
                onClick={stopVoiceSession}
                title="Stop speech-to-speech"
              >
                <IconStop className="h-8 w-8" />
              </Button>
            ) : (
              <Button
                variant="outline"
                className="h-14 w-14 rounded-full p-0"
                onClick={startVoiceSession}
                disabled={!activeSessionId}
                title="Start speech-to-speech"
              >
                <IconMic className="h-8 w-8" />
              </Button>
            )}
          </div>
          <p className="mt-3 text-xs text-zinc-500">
            Agent greets first, then continuously listens and replies. No need to re-enable microphone every turn.
          </p>
          {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
        </div>
      </div>
    </main>
  );
}
