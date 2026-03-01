"use client";

import Link from "next/link";
import Image from "next/image";
import { type ComponentType, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { IconCopy, IconEdit, IconMoreVertical, IconTrash } from "@/components/ui/icons";
import { deleteAgent, fetchAgents, fetchAgentAnalytics, type Agent, type AgentAnalytics } from "@/lib/api";
import { getMockUser, mockLoginWithGoogle, mockLogout } from "@/lib/mock-auth";

type AgentRow = {
  agent: Agent;
  analytics: AgentAnalytics;
};

export default function Home() {
  const router = useRouter();
  const [rows, setRows] = useState<AgentRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [authLoading, setAuthLoading] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(false);

  useEffect(() => {
    const user = getMockUser();
    setIsLoggedIn(!!user);
    setAuthLoading(false);
  }, []);

  useEffect(() => {
    if (authLoading || !isLoggedIn) {
      setIsLoading(false);
      return;
    }
    let isActive = true;
    const load = async () => {
      setIsLoading(true);
      try {
        const agents = await fetchAgents();
        const analyticsList = await Promise.all(
          agents.map(async (agent) => {
            try {
              return await fetchAgentAnalytics(agent.id);
            } catch {
              return { session_count: 0, user_count: 0, message_count: 0, estimated_tokens: 0, estimated_cost_usd: 0 };
            }
          }),
        );
        if (!isActive) return;
        setRows(agents.map((agent, index) => ({ agent, analytics: analyticsList[index] })));
        setError(null);
      } catch (err) {
        if (!isActive) return;
        setError(err instanceof Error ? err.message : "Failed to load agents.");
      } finally {
        if (isActive) setIsLoading(false);
      }
    };
    load();
    return () => {
      isActive = false;
    };
  }, [authLoading, isLoggedIn]);

  const copyCustomerChatLink = async (agentId: string) => {
    const link = `${window.location.origin}/chat/${agentId}`;
    await navigator.clipboard.writeText(link);
  };

  const handleDeleteAgent = async (agentId: string) => {
    setDeletingId(agentId);
    try {
      await deleteAgent(agentId);
      setRows((prev) => prev.filter((row) => row.agent.id !== agentId));
    } finally {
      setDeletingId(null);
      setOpenMenuId(null);
    }
  };

  const handleLogin = () => {
    mockLoginWithGoogle();
    setIsLoggedIn(true);
    setShowLoginModal(false);
  };

  const handleLogout = () => {
    mockLogout();
    setIsLoggedIn(false);
    setRows([]);
  };

  if (authLoading) {
    return <main className="relative min-h-screen overflow-hidden bg-white" />;
  }

  if (!isLoggedIn) {
    return (
      <main className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.96),rgba(255,255,255,0.82)_42%),linear-gradient(to_bottom,#ffffff,#f3f4f6)]" />
        <div className="pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-zinc-200/45 blur-3xl animate-soft" />
        <div className="pointer-events-none absolute right-0 top-40 h-80 w-80 rounded-full bg-slate-200/45 blur-3xl animate-float" />

        <div className="relative mx-auto min-h-screen max-w-6xl px-6 py-12 lg:py-16">
          <section className="grid items-center gap-8 lg:grid-cols-[1.3fr_0.7fr]">
            <div className="space-y-6">
              <h1 className="text-4xl font-bold leading-tight text-zinc-900 sm:text-4xl lg:text-5xl">
                AI Customer Assistant Builder
              </h1>
              <p className="max-w-4xl text-base text-zinc-600 sm:text-2xl">
                Empower your business with AI agents that understand your customers, respond instantly, and drive meaningful engagement, all without writing a single line of code.
              </p>
            </div>
            <div className="relative mx-auto w-full max-w-md">
              <Image
                src="/assistant.png"
                alt="AI assistant preview"
                width={700}
                height={700}
                className="h-auto w-[72%] object-contain"
                priority
              />
            </div>
          </section>

          <section className="py-10">
            <h2 className="text-xl font-semibold text-zinc-900 sm:text-2xl">Key Benefits</h2>
            <div className="mt-4 flex gap-4 overflow-x-auto pb-2">
              <FeatureCard
                title="Instant Setup"
                description="Launch your assistant fast and provide 24/7 customer support right away."
                icon={FeatureIconChat}
                tall
              />
              <FeatureCard
                title="Lower Cost"
                description="Run customer support at a fraction of traditional staffing cost."
                icon={FeatureIconLayers}
                tall
              />
              <FeatureCard
                title="Built-In Analytics"
                description="Track sessions, usage, and performance to improve results continuously."
                icon={FeatureIconChart}
                tall
              />
            </div>
          </section>

          <section className="mt-12 flex justify-center">
            <Button
              className="h-auto px-8 py-4 !text-2xl font-bold leading-tight shadow-lg shadow-zinc-300/70"
              onClick={() => setShowLoginModal(true)}
            >
              Create your assistant
            </Button>
          </section>
        </div>

        {showLoginModal ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
            <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-2xl">
              <h3 className="text-xl font-semibold text-zinc-900">Login Required</h3>
              <p className="mt-2 text-sm text-zinc-600">
                Please continue with Google to create and manage your agents.
              </p>
              <div className="mt-6 space-y-2">
                <Button
                  className="w-full justify-center gap-2"
                  onClick={handleLogin}
                >
                  <GoogleLogo />
                  Continue with Google
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setShowLoginModal(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </main>
    );
  }

  return (
    <main className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.96),rgba(255,255,255,0.82)_42%),linear-gradient(to_bottom,#ffffff,#f3f4f6)]" />
      <div className="pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-zinc-200/45 blur-3xl animate-soft" />
      <div className="pointer-events-none absolute right-0 top-40 h-80 w-80 rounded-full bg-slate-200/45 blur-3xl animate-float" />

      <div className="relative mx-auto min-h-screen max-w-6xl px-6 py-12 lg:py-16">
        <div className="flex justify-end">
          <Button variant="outline" onClick={handleLogout}>
            Logout
          </Button>
        </div>

        <section className="mt-6 grid gap-8 lg:grid-cols-[1.1fr]">
          <div className="space-y-5 animate-fade-up">
            <h1 className="text-4xl font-bold leading-tight text-zinc-900 sm:text-4xl lg:text-5xl">
              AI Customer Assistant Builder
            </h1>
            <p className="text-base text-zinc-600 sm:text-2xl">
              Empower your business with AI agents that understand your customers, respond instantly, and drive meaningful engagement, all without writing a single line of code.
            </p>
          </div>
        </section>

        <section className="mt-8">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-2xl font-semibold text-zinc-900">My Agents</h2>
            {!isLoading && rows.length > 0 ? (
              <Button asChild className="shrink-0 shadow-lg shadow-zinc-300/70">
                <Link href="/builder">Create Agent</Link>
              </Button>
            ) : null}
          </div>
          <div className="mt-4 space-y-4">
            {isLoading ? (
              <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-5 py-6 text-sm text-zinc-600">Loading agents...</div>
            ) : error ? (
              <div className="rounded-2xl border border-red-500/70 bg-red-100 px-5 py-6 text-sm text-red-700">Failed to load agents: {error}</div>
            ) : rows.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-zinc-300 bg-zinc-50 px-5 py-8 text-center">
                <p className="text-sm font-semibold text-zinc-900">No agents yet</p>
                <p className="mt-1 text-sm text-zinc-500">Create your first agent in the builder.</p>
                <div className="mt-4 flex justify-center">
                  <Button asChild className="shadow-lg shadow-zinc-300/70">
                    <Link href="/builder">Create Agent</Link>
                  </Button>
                </div>
              </div>
            ) : (
              rows.map(({ agent, analytics }) => (
                <div
                  key={agent.id}
                  className="relative rounded-2xl border border-zinc-200 bg-zinc-50 p-5 hover:border-zinc-300 hover:bg-white cursor-pointer"
                  onClick={() => router.push(`/agents/${agent.id}`)}
                >
                  <div className="absolute right-3 top-3 z-20 w-8">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenMenuId((prev) => (prev === agent.id ? null : agent.id));
                      }}
                      className="inline-flex h-8 w-8 items-center justify-center leading-none text-zinc-700 hover:text-zinc-900 focus:outline-none"
                      aria-label={`Open actions for ${agent.name}`}
                    >
                      <IconMoreVertical className="h-4 w-4 shrink-0" />
                    </button>
                    {openMenuId === agent.id ? (
                      <div className="absolute right-0 top-9 w-56 rounded-xl border border-zinc-200 bg-white p-1 shadow-lg">
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.stopPropagation();
                            await copyCustomerChatLink(agent.id);
                            setOpenMenuId(null);
                          }}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-800 hover:bg-zinc-100"
                        >
                          <IconCopy className="h-4 w-4" />
                          Copy customer chat link
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/agents/${agent.id}?tab=configuration`);
                          }}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-800 hover:bg-zinc-100"
                        >
                          <IconEdit className="h-4 w-4" />
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setPendingDeleteId(agent.id);
                            setOpenMenuId(null);
                          }}
                          disabled={deletingId === agent.id || pendingDeleteId === agent.id}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-700 hover:bg-red-100 disabled:opacity-60"
                        >
                          <IconTrash className="h-4 w-4" />
                          {deletingId === agent.id ? "Deleting..." : "Delete"}
                        </button>
                      </div>
                    ) : null}
                  </div>

                  <div className="pr-10">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <h3 className="text-lg font-semibold text-zinc-900">{agent.name}</h3>
                        <p className="mt-1 text-sm text-zinc-600">{agent.description}</p>
                      </div>
                      <div className="flex flex-nowrap items-start gap-4 text-xs">
                        <AnalyticsItem label="Sessions" value={analytics.session_count} />
                        <AnalyticsItem label="Users" value={analytics.user_count} />
                        <AnalyticsItem label="Messages" value={analytics.message_count} />
                        <AnalyticsItem label="Estimated tokens" value={analytics.estimated_tokens} />
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {pendingDeleteId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-zinc-900">Delete Agent?</h3>
            <p className="mt-2 text-sm text-zinc-600">This action cannot be undone.</p>
            <div className="mt-6 flex items-center justify-end gap-3">
              <Button variant="outline" onClick={() => setPendingDeleteId(null)}>
                Cancel
              </Button>
              <Button
                className="bg-red-600 text-white hover:bg-red-700"
                onClick={async () => {
                  await handleDeleteAgent(pendingDeleteId);
                  setPendingDeleteId(null);
                }}
                disabled={deletingId === pendingDeleteId}
              >
                {deletingId === pendingDeleteId ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}

function AnalyticsItem({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-sm text-zinc-500">{label}</p>
      <p className="text-base font-semibold text-zinc-900">{value.toLocaleString()}</p>
    </div>
  );
}

function FeatureCard({
  title,
  description,
  icon: Icon,
  tall,
}: {
  title: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
  tall?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl border border-zinc-200 bg-zinc-50 p-10 transition duration-200 hover:-translate-y-1 hover:shadow-xl hover:shadow-zinc-300/60 ${
        tall ? "min-h-[320px] min-w-[230px] sm:min-w-[250px] lg:min-w-0 lg:flex-1" : ""
      }`}
    >
      <div className="mb-4 mt-10 flex justify-center text-zinc-700">
        <Icon className="h-10 w-10" />
      </div>
      <h3 className="text-center text-lg font-semibold text-zinc-900">{title}</h3>
      <p className="mt-2 text-center text-sm leading-relaxed text-zinc-700">{description}</p>
    </div>
  );
}

function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4">
      <path
        fill="#EA4335"
        d="M12 10.2v3.9h5.5c-.2 1.2-1.4 3.5-5.5 3.5-3.3 0-6-2.8-6-6.2s2.7-6.2 6-6.2c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 2.7 14.7 1.8 12 1.8 6.9 1.8 2.8 6 2.8 11.2S6.9 20.6 12 20.6c6.9 0 8.6-4.8 8.6-7.3 0-.5 0-.8-.1-1.2H12z"
      />
      <path
        fill="#34A853"
        d="M3.7 7.3l3.2 2.3c.8-2.4 2.9-4 5.1-4 1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 2.7 14.7 1.8 12 1.8 8.3 1.8 5.2 3.9 3.7 7.3z"
      />
      <path
        fill="#4A90E2"
        d="M12 20.6c2.6 0 4.8-.9 6.4-2.4l-3-2.5c-.8.6-1.9 1-3.4 1-2.7 0-4.9-1.8-5.7-4.3l-3.2 2.5c1.5 3.1 4.7 5.7 8.9 5.7z"
      />
      <path
        fill="#FBBC05"
        d="M3.7 14.9l3.2-2.5c-.2-.6-.3-1.2-.3-1.8s.1-1.2.3-1.8L3.7 6.3C3.1 7.5 2.8 8.8 2.8 10.2s.3 2.7.9 4z"
      />
    </svg>
  );
}

function FeatureIconChat({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M4 6h16v10H8l-4 4V6z" />
    </svg>
  );
}

function FeatureIconLayers({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M12 3l9 5-9 5-9-5 9-5z" />
      <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M3 12l9 5 9-5" />
      <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M3 16l9 5 9-5" />
    </svg>
  );
}

function FeatureIconChart({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M4 20h16" />
      <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M7 16v-3M12 16V9M17 16V6" />
    </svg>
  );
}
