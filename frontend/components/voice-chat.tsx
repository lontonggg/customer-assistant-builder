"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { IconMic, IconSpinner } from "@/components/ui/icons";
import { getVoiceWebSocketUrl, type Agent } from "@/lib/api";

interface VoiceChatProps {
  agent: Agent;
}

interface Transcript {
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

export function VoiceChat({ agent }: VoiceChatProps) {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolume] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom when new transcript arrives
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  const playAudioQueue = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

    isPlayingRef.current = true;
    setIsSpeaking(true);

    while (audioQueueRef.current.length > 0) {
      const audioData = audioQueueRef.current.shift();
      if (!audioData) continue;

      try {
        if (!audioContextRef.current) {
          audioContextRef.current = new AudioContext({ sampleRate: 24000 });
        }

        // PCM 16-bit to Float32
        const int16Array = new Int16Array(audioData);
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
          float32Array[i] = int16Array[i] / 32768;
        }

        const audioBuffer = audioContextRef.current.createBuffer(
          1,
          float32Array.length,
          24000
        );
        audioBuffer.getChannelData(0).set(float32Array);

        const source = audioContextRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContextRef.current.destination);

        await new Promise<void>((resolve) => {
          source.onended = () => resolve();
          source.start();
        });
      } catch (e) {
        console.error("Audio playback error:", e);
      }
    }

    isPlayingRef.current = false;
    setIsSpeaking(false);
  }, []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      mediaStreamRef.current = stream;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: 16000 });
      }

      const source = audioContextRef.current.createMediaStreamSource(stream);
      const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      // Analyser for volume visualization
      const analyser = audioContextRef.current.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      processor.onaudioprocess = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

        // Get volume
        analyser.getByteFrequencyData(dataArray);
        const avg = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setVolume(avg / 255);

        // Convert to PCM16 and send
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          pcm16[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
        }

        // Send as base64 encoded audio
        const base64 = btoa(
          String.fromCharCode(...new Uint8Array(pcm16.buffer))
        );
        wsRef.current.send(
          JSON.stringify({
            type: "audio",
            data: base64,
          })
        );
      };

      source.connect(processor);
      processor.connect(audioContextRef.current.destination);

      setIsListening(true);
    } catch (e) {
      console.error("Microphone access error:", e);
      setError("Could not access microphone. Please allow microphone access.");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // Signal end of turn
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end_turn" }));
    }

    setIsListening(false);
    setVolume(0);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    setStatus("connecting");
    setError(null);
    setTranscripts([]);

    const ws = new WebSocket(getVoiceWebSocketUrl(agent.id));
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "connected":
            setStatus("connected");
            setTranscripts((prev) => [
              ...prev,
              {
                role: "assistant",
                text: `Connected to ${data.agent_name}. Voice: ${data.voice}. Click and hold the microphone to talk!`,
                timestamp: new Date(),
              },
            ]);
            break;

          case "audio":
            // Decode base64 audio and queue for playback
            const binaryString = atob(data.data);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }
            audioQueueRef.current.push(bytes.buffer);
            playAudioQueue();
            break;

          case "transcript":
            setTranscripts((prev) => [
              ...prev,
              {
                role: data.role,
                text: data.text,
                timestamp: new Date(),
              },
            ]);
            break;

          case "turn_complete":
            // Agent finished speaking
            break;

          case "error":
            setError(data.message);
            setStatus("error");
            break;
        }
      } catch (e) {
        console.error("Message parse error:", e);
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
      setStatus("error");
    };

    ws.onclose = () => {
      setStatus("disconnected");
      stopRecording();
    };
  }, [agent.id, playAudioQueue, stopRecording]);

  const disconnect = useCallback(() => {
    stopRecording();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus("disconnected");
  }, [stopRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, [disconnect]);

  const getStatusColor = () => {
    switch (status) {
      case "connected":
        return "bg-emerald-500";
      case "connecting":
        return "bg-yellow-500 animate-pulse";
      case "error":
        return "bg-red-500";
      default:
        return "bg-gray-500";
    }
  };

  const getStatusText = () => {
    switch (status) {
      case "connected":
        return "Connected";
      case "connecting":
        return "Connecting...";
      case "error":
        return "Error";
      default:
        return "Disconnected";
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Status bar */}
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className={`h-2.5 w-2.5 rounded-full ${getStatusColor()}`} />
          <span className="text-sm text-white/70">{getStatusText()}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/50">
            Voice: {agent.voice_gender === "male" ? "Male" : "Female"}
          </span>
        </div>
      </div>

      {/* Transcripts */}
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {transcripts.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20">
              <IconMic className="h-8 w-8 text-emerald-300" />
            </div>
            <h3 className="text-lg font-semibold text-white">
              Voice Chat with {agent.name}
            </h3>
            <p className="mt-2 max-w-sm text-sm text-white/60">
              {status === "disconnected"
                ? 'Click "Start Voice Session" to begin talking with your AI agent.'
                : "Hold the microphone button to speak."}
            </p>
          </div>
        ) : (
          transcripts.map((transcript, index) => (
            <div
              key={index}
              className={`flex ${
                transcript.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  transcript.role === "user"
                    ? "bg-emerald-500/20 text-white"
                    : "bg-white/10 text-white"
                }`}
              >
                <p className="text-sm">{transcript.text}</p>
                <p className="mt-1 text-[10px] text-white/50">
                  {transcript.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={transcriptEndRef} />
      </div>

      {/* Error display */}
      {error && (
        <div className="border-t border-red-400/30 bg-red-500/10 px-4 py-3">
          <p className="text-sm text-red-200">{error}</p>
        </div>
      )}

      {/* Controls */}
      <div className="border-t border-white/10 p-4">
        {status === "disconnected" ? (
          <Button
            className="w-full bg-linear-to-r from-[#26D07C] to-emerald-300 text-[#02231C]"
            onClick={connect}
          >
            <IconMic className="mr-2 h-5 w-5" />
            Start Voice Session
          </Button>
        ) : status === "connecting" ? (
          <Button className="w-full" disabled>
            <IconSpinner className="mr-2 h-5 w-5 animate-spin" />
            Connecting...
          </Button>
        ) : (
          <div className="flex items-center gap-3">
            {/* Microphone button */}
            <button
              type="button"
              className={`relative flex h-14 w-14 items-center justify-center rounded-full transition-all ${
                isListening
                  ? "bg-red-500 scale-110"
                  : "bg-emerald-500 hover:bg-emerald-400"
              }`}
              onMouseDown={startRecording}
              onMouseUp={stopRecording}
              onMouseLeave={stopRecording}
              onTouchStart={startRecording}
              onTouchEnd={stopRecording}
              disabled={isSpeaking}
            >
              {/* Volume indicator ring */}
              {isListening && (
                <div
                  className="absolute inset-0 rounded-full border-4 border-white/30"
                  style={{
                    transform: `scale(${1 + volume * 0.5})`,
                    opacity: volume,
                  }}
                />
              )}
              <IconMic className="h-6 w-6 text-white" />
            </button>

            <div className="flex-1">
              <p className="text-sm font-medium text-white">
                {isListening
                  ? "Listening..."
                  : isSpeaking
                  ? "Agent is speaking..."
                  : "Hold to speak"}
              </p>
              <p className="text-xs text-white/60">
                {isListening
                  ? "Release to send"
                  : isSpeaking
                  ? "Wait for response"
                  : "Press and hold microphone"}
              </p>
            </div>

            {/* Disconnect button */}
            <Button variant="outline" onClick={disconnect}>
              End
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
