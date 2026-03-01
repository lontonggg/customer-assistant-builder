"use client";

import Link from "next/link";
import { useMemo, useState, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { FieldShell } from "@/components/ui/field-shell";
import { IconArrowLeft, IconCopy, IconTrash } from "@/components/ui/icons";
import {
  fetchAgent,
  fetchAgentAnalytics,
  fetchAgentAnalyticsTrend,
  fetchKnowledgeFiles,
  deleteKnowledgeFile,
  uploadKnowledge,
  updateAgent,
  deleteAgent,
  type Agent,
  type AgentAnalytics,
  type AgentAnalyticsTrendItem,
  type KnowledgeFile,
} from "@/lib/api";
import { isMockLoggedIn } from "@/lib/mock-auth";

const languageOptions = [
  { value: "en-US", label: "English" },
  { value: "id-ID", label: "Indonesian" },
  { value: "es-ES", label: "Spanish" },
  { value: "fr-FR", label: "French" },
  { value: "ms-MY", label: "Malay" },
  { value: "zh-CN", label: "Chinese" },
  { value: "hi-IN", label: "Indian" },
];
const businessTypes = ["Fashion", "Clinic"];
type EditableFaq = { question: string; answer: string };
type BusinessInfo = Record<string, string>;
type CatalogRow = Record<string, string>;
type DoctorRow = Record<string, string>;
const editableCatalogColumns = ["name", "short_desc", "price", "currency_code", "duration_mins"] as const;
const editableDoctorColumns = ["full_name", "title", "specialization", "qualifications", "bio", "languages"] as const;

type TabKey = "analytics" | "configuration";
const trendRangeOptions = [
  { value: "30m", label: "Last 30 minutes" },
  { value: "1h", label: "Last hour" },
  { value: "24h", label: "Last 24h" },
  { value: "3d", label: "Last 3d" },
  { value: "5d", label: "Last 5d" },
  { value: "7d", label: "Last week" },
  { value: "14d", label: "Last 14d" },
  { value: "30d", label: "Last 30d" },
];

export default function AgentAdminPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const agentId = Array.isArray(params.id) ? params.id[0] : params.id;

  const [tab, setTab] = useState<TabKey>("analytics");
  const [trendRange, setTrendRange] = useState("7d");
  const [agent, setAgent] = useState<Agent | null>(null);
  const [analytics, setAnalytics] = useState<AgentAnalytics | null>(null);
  const [trend, setTrend] = useState<AgentAnalyticsTrendItem[]>([]);
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instruction, setInstruction] = useState("");
  const [language, setLanguage] = useState("en-US");
  const [businessType, setBusinessType] = useState("Fashion");
  const [temperature, setTemperature] = useState(0.4);
  const [voiceGender, setVoiceGender] = useState("female");
  const [newFiles, setNewFiles] = useState<File[]>([]);
  const [businessInfo, setBusinessInfo] = useState<BusinessInfo>({});
  const [catalogRows, setCatalogRows] = useState<CatalogRow[]>([]);
  const [faqs, setFaqs] = useState<EditableFaq[]>([]);
  const [doctors, setDoctors] = useState<DoctorRow[]>([]);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    if (!isMockLoggedIn()) {
      router.replace("/");
      return;
    }
    setAuthReady(true);
  }, [router]);

  useEffect(() => {
    const requestedTab = searchParams.get("tab");
    if (requestedTab === "configuration" || requestedTab === "analytics") {
      setTab(requestedTab);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!authReady || !agentId) return;
    let isActive = true;

    const load = async () => {
      setIsLoading(true);
      try {
        const [agentData, analyticsData, trendData, filesData] = await Promise.all([
          fetchAgent(agentId),
          fetchAgentAnalytics(agentId),
          fetchAgentAnalyticsTrend(agentId, trendRange),
          fetchKnowledgeFiles(agentId),
        ]);
        if (!isActive) return;

        setAgent(agentData);
        setAnalytics(analyticsData);
        setTrend(trendData);
        setKnowledgeFiles(filesData);

        setName(agentData.name);
        setDescription(agentData.description);
        setInstruction(agentData.instruction);
        setLanguage(agentData.language || "en-US");
        setTemperature(typeof agentData.temperature === "number" ? agentData.temperature : 0.4);
        setBusinessType(agentData.business_type || "Fashion");
        setVoiceGender(agentData.voice_gender || "female");
        setBusinessInfo((agentData.business_info as BusinessInfo) || {});
        setCatalogRows((agentData.catalog_items as CatalogRow[]) || []);
        setFaqs((agentData.faqs as EditableFaq[]) || []);
        setDoctors(
          ((agentData.doctors as Record<string, unknown>[]) || []).map((row) => {
            const normalized: DoctorRow = {};
            editableDoctorColumns.forEach((column) => {
              const raw = row?.[column];
              normalized[column] = Array.isArray(raw) ? raw.join(", ") : String(raw ?? "");
            });
            return normalized;
          }),
        );
        setError(null);
      } catch (err) {
        if (!isActive) return;
        setError(err instanceof Error ? err.message : "Failed to load agent.");
      } finally {
        if (isActive) setIsLoading(false);
      }
    };

    load();
    return () => {
      isActive = false;
    };
  }, [agentId, trendRange, authReady]);

  const temperatureHint = useMemo(() => {
    if (temperature <= 0.3) return "Very focused: more consistent and predictable responses.";
    if (temperature >= 0.7) return "Explorative: more creative and varied responses.";
    return "Balanced: a mix of reliable structure and natural tone.";
  }, [temperature]);

  if (!authReady) {
    return <main className="min-h-screen bg-white" />;
  }

  const handleSave = async () => {
    if (!agentId) return;
    setIsSaving(true);
    setSaveMessage(null);
    setError(null);

    try {
      const updated = await updateAgent(agentId, {
        name: name.trim(),
        description: description.trim(),
        instruction: instruction.trim(),
        language,
        temperature,
        business_type: businessType,
        use_voice_to_voice: true,
        voice_gender: voiceGender,
        business_info: businessInfo,
        catalog_items: catalogRows,
        faqs,
        doctors,
      });

      if (newFiles.length > 0) {
        await uploadKnowledge(agentId, newFiles);
      }

      const [analyticsData, trendData, filesData] = await Promise.all([
        fetchAgentAnalytics(agentId),
        fetchAgentAnalyticsTrend(agentId, trendRange),
        fetchKnowledgeFiles(agentId),
      ]);

      setAgent(updated);
      setAnalytics(analyticsData);
      setTrend(trendData);
      setKnowledgeFiles(filesData);
      setNewFiles([]);
      setSaveMessage("Configuration updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update agent.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteKnowledge = async (fileId: string) => {
    if (!agentId) return;
    setError(null);
    try {
      await deleteKnowledgeFile(fileId);
      const filesData = await fetchKnowledgeFiles(agentId);
      setKnowledgeFiles(filesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete file.");
    }
  };

  const handleDelete = async () => {
    if (!agentId) return;
    setIsDeleting(true);
    try {
      await deleteAgent(agentId);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete agent");
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const handleCopyCustomerChatLink = async () => {
    if (!agent) return;
    const link = `${window.location.origin}/chat/${agent.id}`;
    await navigator.clipboard.writeText(link);
    setSaveMessage("Customer chat link copied.");
    setTimeout(() => setSaveMessage(null), 1600);
  };

  if (isLoading) {
    return (
      <main className="relative overflow-hidden">
        <div className="relative mx-auto min-h-screen max-w-6xl px-4 py-6 sm:px-6 sm:py-10 lg:py-16">
          <SectionCard title="Loading" subtitle="Fetching agent data...">
            <div className="py-8 text-sm text-zinc-600">Loading...</div>
          </SectionCard>
        </div>
      </main>
    );
  }

  if (error || !agent || !analytics) {
    return (
      <main className="relative overflow-hidden">
        <div className="relative mx-auto min-h-screen max-w-6xl px-4 py-6 sm:px-6 sm:py-10 lg:py-16">
          <SectionCard title="Agent not found" subtitle="Return to My Agents.">
            <div className="space-y-4">
              {error ? <p className="text-sm text-red-700">{error}</p> : null}
              <Button asChild>
                <Link href="/">Back to home</Link>
              </Button>
            </div>
          </SectionCard>
        </div>
      </main>
    );
  }

  return (
    <main className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.92),rgba(255,255,255,0.7)_42%),linear-gradient(to_bottom,#ffffff,#f3f4f6)]" />

      <div className="relative mx-auto min-h-screen max-w-6xl px-4 py-6 sm:px-6 sm:py-10 lg:py-16">
        <header className="mt-2 flex flex-col gap-3 animate-fade-up sm:gap-2">
          <div className="flex items-center gap-2">
            <Link href="/" className="text-zinc-700 hover:text-zinc-900 transition">
              <IconArrowLeft className="h-5 w-5" />
            </Link>
            <p className="text-xs uppercase tracking-[0.25em] text-zinc-700">Home</p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-zinc-900 sm:text-3xl lg:text-4xl">{agent.name}</h1>
              <p className="mt-1 text-zinc-600 text-sm sm:text-base">Configuration and analytics dashboard</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" onClick={handleCopyCustomerChatLink}>
                <IconCopy className="h-4 w-4" />
                Copy Customer Chat Link
              </Button>
              <Button asChild variant="outline">
                <Link href={`/chat/${agent.id}`}>Open Customer Chat</Link>
              </Button>
              <Button
                className="bg-red-600 text-white hover:bg-red-700"
                onClick={() => setShowDeleteConfirm(true)}
              >
                Delete
              </Button>
            </div>
          </div>
        </header>

        {showDeleteConfirm ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-2xl">
              <h3 className="text-lg font-semibold text-zinc-900">Delete Agent?</h3>
              <p className="mt-2 text-sm text-zinc-600">This action cannot be undone.</p>
              <div className="mt-6 flex items-center justify-end gap-3">
                <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
                  Cancel
                </Button>
                <Button className="bg-red-500 hover:bg-red-600" onClick={handleDelete} disabled={isDeleting}>
                  {isDeleting ? "Deleting..." : "Delete"}
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        <div className="mt-6 rounded-2xl border border-zinc-200 bg-white p-2 sm:mt-8 sm:p-3">
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setTab("analytics")}
              className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                tab === "analytics"
                  ? "bg-zinc-900 text-white"
                  : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
              }`}
            >
              Analytics
            </button>
            <button
              type="button"
              onClick={() => setTab("configuration")}
              className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                tab === "configuration"
                  ? "bg-zinc-900 text-white"
                  : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200"
              }`}
            >
              Configuration
            </button>
          </div>
        </div>

        {tab === "analytics" ? (
          <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <SectionCard title="Usage Trend" subtitle="Sessions, users, and token estimates over time.">
              <div className="mb-3">
                <FieldShell>
                  <select
                    value={trendRange}
                    onChange={(e) => setTrendRange(e.target.value)}
                    className="w-full bg-transparent text-zinc-900 focus:outline-none"
                  >
                    {trendRangeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </FieldShell>
              </div>
              <TrendChart data={trend} />
            </SectionCard>
            <SectionCard title="Totals" subtitle="Current cumulative metrics.">
              <div className="space-y-3">
                <AnalyticsItem label="Sessions created" value={analytics.session_count} />
                <AnalyticsItem label="Users" value={analytics.user_count} />
                <AnalyticsItem label="Messages" value={analytics.message_count} />
                <AnalyticsItem label="Estimated tokens" value={analytics.estimated_tokens} />
                <AnalyticsCurrencyItem label="Estimated Cost" value={analytics.estimated_cost_usd} />
              </div>
            </SectionCard>
          </div>
        ) : (
          <div className="mt-6 grid gap-6">
            <SectionCard title="Configuration" subtitle="Everything below can be edited.">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Agent name</Label>
                  <FieldShell>
                    <input value={name} onChange={(e) => setName(e.target.value)} className="w-full bg-transparent text-zinc-900 focus:outline-none" />
                  </FieldShell>
                </div>

                <div className="space-y-2">
                  <Label>Description</Label>
                  <FieldShell>
                    <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full resize-none bg-transparent text-zinc-900 focus:outline-none" />
                  </FieldShell>
                </div>

                <div className="space-y-2">
                  <Label>Instruction</Label>
                  <FieldShell>
                    <textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} rows={5} className="w-full resize-none bg-transparent text-zinc-900 focus:outline-none" />
                  </FieldShell>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Main language</Label>
                    <FieldShell>
                      <select value={language} onChange={(e) => setLanguage(e.target.value)} className="w-full bg-transparent text-zinc-900 focus:outline-none">
                        {languageOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </FieldShell>
                  </div>

                  <div className="space-y-2">
                    <Label>Business type</Label>
                    <FieldShell>
                      <select value={businessType} onChange={(e) => setBusinessType(e.target.value)} className="w-full bg-transparent text-zinc-900 focus:outline-none">
                        {businessTypes.map((type) => (
                          <option key={type} value={type}>{type}</option>
                        ))}
                      </select>
                    </FieldShell>
                  </div>

                  <div className="space-y-2">
                    <Label>Temperature</Label>
                    <FieldShell>
                      <input type="range" min={0} max={1} step={0.1} value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} className="w-full accent-zinc-700" />
                    </FieldShell>
                    <p className="text-xs text-zinc-600">{temperatureHint}</p>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Voice gender</Label>
                    <FieldShell>
                      <select value={voiceGender} onChange={(e) => setVoiceGender(e.target.value)} className="w-full bg-transparent text-zinc-900 focus:outline-none">
                        <option value="female">Female</option>
                        <option value="male">Male</option>
                      </select>
                    </FieldShell>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Current knowledge files</Label>
                  <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
                    {knowledgeFiles.length === 0 ? (
                      <p>No files uploaded yet.</p>
                    ) : (
                      <div className="space-y-2">
                        {knowledgeFiles.map((file) => (
                          <div key={file.id} className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-3 py-2">
                            <a
                              href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${file.download_url || ""}`}
                              target="_blank"
                              rel="noreferrer"
                              className="truncate pr-3 text-zinc-900 underline"
                            >
                              {file.file_name}
                            </a>
                            <div className="ml-3 flex shrink-0 items-center gap-2">
                              <span className="text-xs text-zinc-500">{new Date(file.created_at).toLocaleDateString()}</span>
                              <button
                                type="button"
                                onClick={() => handleDeleteKnowledge(file.id)}
                                className="rounded-md p-1 text-red-700 hover:bg-red-100"
                                aria-label={`Delete ${file.file_name}`}
                              >
                                <IconTrash className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Add / replace knowledge files</Label>
                  <FieldShell>
                    <input
                      type="file"
                      multiple
                      accept=".pdf,image/*"
                      onChange={(e) => setNewFiles(Array.from(e.target.files || []))}
                      className="w-full cursor-pointer bg-transparent text-sm text-zinc-900 file:mr-3 file:rounded-xl file:border-0 file:bg-zinc-100 file:px-3 file:py-2 file:text-zinc-700"
                    />
                  </FieldShell>
                  {newFiles.length > 0 ? (
                    <p className="text-xs text-zinc-600">{newFiles.length} file(s) selected.</p>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <Label>Business Info</Label>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {Object.entries(businessInfo).map(([key, value]) => (
                      <FieldShell key={key}>
                        <div className="space-y-1 w-full">
                          <p className="text-xs capitalize text-zinc-600">{key.replaceAll("_", " ")}</p>
                          <input
                            value={value}
                            onChange={(e) => setBusinessInfo((prev) => ({ ...prev, [key]: e.target.value }))}
                            className="w-full bg-transparent text-zinc-900 focus:outline-none"
                          />
                        </div>
                      </FieldShell>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>{businessType === "Clinic" ? "Services" : "Products"}</Label>
                  <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-zinc-50 p-3">
                    <table className="min-w-full border-collapse text-left text-xs">
                      <thead>
                        <tr>
                          {editableCatalogColumns
                            .filter((c) => c !== "duration_mins" || businessType === "Clinic")
                            .map((column) => (
                              <th key={column} className="border border-zinc-200 bg-white p-2 font-semibold text-zinc-800">
                                {column === "name"
                                  ? "Name"
                                  : column === "short_desc"
                                    ? "Short Description"
                                    : column === "price"
                                      ? "Price"
                                      : column === "currency_code"
                                        ? "Currency Code"
                                        : "Duration (Minutes)"}
                              </th>
                            ))}
                        </tr>
                      </thead>
                      <tbody>
                        {catalogRows.map((row, rowIndex) => (
                          <tr key={`catalog-row-${rowIndex}`}>
                            {editableCatalogColumns
                              .filter((c) => c !== "duration_mins" || businessType === "Clinic")
                              .map((column) => (
                                <td key={`${column}-${rowIndex}`} className="border border-zinc-200 p-2">
                                  <input
                                    value={row[column] ?? ""}
                                    onChange={(e) => {
                                      const raw = e.target.value;
                                      const value =
                                        column === "duration_mins"
                                          ? raw.replace(/\D/g, "")
                                          : column === "price"
                                            ? raw.replace(/[^0-9.]/g, "")
                                            : raw;
                                      setCatalogRows((prev) =>
                                        prev.map((item, i) => (i === rowIndex ? { ...item, [column]: value } : item)),
                                      );
                                    }}
                                    className="w-full min-w-[160px] rounded-md border border-zinc-200 bg-white px-2 py-1 text-zinc-900 focus:border-zinc-400 focus:outline-none"
                                  />
                                </td>
                              ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {businessType === "Clinic" ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Doctors</Label>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          setDoctors((prev) => [
                            ...prev,
                            Object.fromEntries(editableDoctorColumns.map((column) => [column, ""])),
                          ])
                        }
                      >
                        Add Doctor
                      </Button>
                    </div>
                    <div className="overflow-x-auto rounded-2xl border border-zinc-200 bg-zinc-50 p-3">
                      <table className="min-w-full border-collapse text-left text-xs">
                        <thead>
                          <tr>
                            {editableDoctorColumns.map((column) => (
                              <th key={column} className="border border-zinc-200 bg-white p-2 font-semibold text-zinc-800">
                                {column === "full_name"
                                  ? "Full Name"
                                  : column === "title"
                                    ? "Title"
                                    : column === "specialization"
                                      ? "Specialization"
                                      : column === "qualifications"
                                        ? "Qualifications"
                                        : column === "bio"
                                          ? "Bio"
                                          : "Languages"}
                              </th>
                            ))}
                            <th className="border border-zinc-200 bg-white p-2 font-semibold text-zinc-800">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {doctors.map((row, rowIndex) => (
                            <tr key={`doctor-row-${rowIndex}`}>
                              {editableDoctorColumns.map((column) => (
                                <td key={`${column}-${rowIndex}`} className="border border-zinc-200 p-2">
                                  <input
                                    value={row[column] ?? ""}
                                    onChange={(e) =>
                                      setDoctors((prev) =>
                                        prev.map((item, i) =>
                                          i === rowIndex ? { ...item, [column]: e.target.value } : item,
                                        ),
                                      )
                                    }
                                    className="w-full min-w-[160px] rounded-md border border-zinc-200 bg-white px-2 py-1 text-zinc-900 focus:border-zinc-400 focus:outline-none"
                                  />
                                </td>
                              ))}
                              <td className="border border-zinc-200 p-2">
                                <button
                                  type="button"
                                  onClick={() => setDoctors((prev) => prev.filter((_, i) => i !== rowIndex))}
                                  className="rounded-md p-1 text-red-700 hover:bg-red-100"
                                  aria-label={`Delete doctor ${rowIndex + 1}`}
                                >
                                  <IconTrash className="h-4 w-4" />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : null}

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>FAQ</Label>
                    <Button size="sm" variant="outline" onClick={() => setFaqs((prev) => [...prev, { question: "", answer: "" }])}>
                      Add FAQ
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {faqs.map((faq, index) => (
                      <div key={`faq-${index}`} className="rounded-2xl border border-zinc-200 bg-zinc-50 p-3">
                        <div className="flex items-center justify-between">
                          <p className="text-xs font-medium text-zinc-600">FAQ #{index + 1}</p>
                          <button
                            type="button"
                            onClick={() => setFaqs((prev) => prev.filter((_, i) => i !== index))}
                            className="rounded-md p-1 text-red-700 hover:bg-red-100"
                            aria-label={`Delete FAQ ${index + 1}`}
                          >
                            <IconTrash className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="space-y-2">
                          <FieldShell>
                            <div className="space-y-1 w-full">
                              <p className="text-xs font-medium text-zinc-600">Question</p>
                              <input
                                value={faq.question}
                                onChange={(e) =>
                                  setFaqs((prev) => prev.map((item, i) => (i === index ? { ...item, question: e.target.value } : item)))
                                }
                                placeholder="Question"
                                className="w-full bg-transparent text-zinc-900 focus:outline-none"
                              />
                            </div>
                          </FieldShell>
                          <FieldShell>
                            <div className="space-y-1 w-full">
                              <p className="text-xs font-medium text-zinc-600">Answer</p>
                              <textarea
                                value={faq.answer}
                                onChange={(e) =>
                                  setFaqs((prev) => prev.map((item, i) => (i === index ? { ...item, answer: e.target.value } : item)))
                                }
                                rows={3}
                                placeholder="Answer"
                                className="w-full resize-none bg-transparent text-zinc-900 focus:outline-none"
                              />
                            </div>
                          </FieldShell>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={handleSave} disabled={isSaving}>{isSaving ? "Saving..." : "Save changes"}</Button>
                  {saveMessage ? <span className="text-sm text-zinc-600">{saveMessage}</span> : null}
                </div>
                {error ? <p className="text-sm text-red-700">{error}</p> : null}
              </div>
            </SectionCard>
          </div>
        )}
      </div>
    </main>
  );
}

function AnalyticsItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-zinc-900">{value.toLocaleString()}</p>
    </div>
  );
}

function AnalyticsCurrencyItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-zinc-900">${value.toFixed(4)}</p>
    </div>
  );
}

function TrendChart({ data }: { data: AgentAnalyticsTrendItem[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [showSessions, setShowSessions] = useState(true);
  const [showUsers, setShowUsers] = useState(true);
  const [showTokens, setShowTokens] = useState(true);
  const [showCost, setShowCost] = useState(true);

  const width = 560;
  const height = 220;
  const paddingLeft = 44;
  const paddingRight = 16;
  const paddingTop = 18;
  const paddingBottom = 30;

  const metricDefs = [
    { key: "sessions", label: "Sessions", color: "#111827", enabled: showSessions, values: data.map((d) => d.sessions) },
    { key: "users", label: "Users", color: "#6b7280", enabled: showUsers, values: data.map((d) => d.users) },
    { key: "tokens", label: "Estimated Tokens", color: "#d97706", enabled: showTokens, values: data.map((d) => d.estimated_tokens) },
    { key: "cost", label: "Estimated Cost", color: "#dc2626", enabled: showCost, values: data.map((d) => d.estimated_cost_usd) },
  ] as const;

  const activeMetrics = metricDefs.filter((m) => m.enabled);
  const maxY = Math.max(1, ...activeMetrics.flatMap((m) => m.values));
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  const toPoints = (values: number[]) =>
    values
      .map((value, index) => {
        const x = paddingLeft + (index * chartWidth) / Math.max(1, values.length - 1);
        const y = paddingTop + (1 - value / maxY) * chartHeight;
        return `${x},${y}`;
      })
      .join(" ");

  const getX = (index: number) =>
    paddingLeft + (index * chartWidth) / Math.max(1, data.length - 1);
  const getY = (value: number) => paddingTop + (1 - value / maxY) * chartHeight;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3 text-xs text-zinc-700">
        <label className="inline-flex items-center gap-2">
          <input type="checkbox" checked={showSessions} onChange={(e) => setShowSessions(e.target.checked)} />
          Sessions
        </label>
        <label className="inline-flex items-center gap-2">
          <input type="checkbox" checked={showUsers} onChange={(e) => setShowUsers(e.target.checked)} />
          Users
        </label>
        <label className="inline-flex items-center gap-2">
          <input type="checkbox" checked={showTokens} onChange={(e) => setShowTokens(e.target.checked)} />
          Estimated Tokens
        </label>
        <label className="inline-flex items-center gap-2">
          <input type="checkbox" checked={showCost} onChange={(e) => setShowCost(e.target.checked)} />
          Estimated Cost
        </label>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-3">
        {data.length === 0 ? (
          <p className="text-sm text-zinc-500">No trend data yet.</p>
        ) : activeMetrics.length === 0 ? (
          <p className="text-sm text-zinc-500">Select at least one metric.</p>
        ) : (
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full overflow-visible">
            <rect x="0" y="0" width={width} height={height} fill="white" />
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
              const y = paddingTop + ratio * chartHeight;
              const tickValue = maxY * (1 - ratio);
              return (
                <g key={`grid-${ratio}`}>
                  <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke="#e5e7eb" strokeWidth="1" />
                  <text x={paddingLeft - 8} y={y + 3} textAnchor="end" fontSize="10" fill="#71717a">
                    {tickValue >= 1000 ? Math.round(tickValue).toLocaleString() : tickValue.toFixed(2).replace(/\.00$/, "")}
                  </text>
                </g>
              );
            })}

            <line x1={paddingLeft} y1={paddingTop} x2={paddingLeft} y2={height - paddingBottom} stroke="#a1a1aa" strokeWidth="1.2" />
            <line x1={paddingLeft} y1={height - paddingBottom} x2={width - paddingRight} y2={height - paddingBottom} stroke="#a1a1aa" strokeWidth="1.2" />

            {activeMetrics.map((metric) => (
              <polyline
                key={metric.key}
                fill="none"
                stroke={metric.color}
                strokeWidth="3"
                points={toPoints(metric.values)}
              />
            ))}

            {data.map((point, index) => {
              const x = getX(index);
              return (
                <g key={`point-${index}`}>
                  {activeMetrics.map((metric) => (
                    <circle
                      key={`${metric.key}-${index}`}
                      cx={x}
                      cy={getY(metric.values[index] ?? 0)}
                      r={hoveredIndex === index ? 4.5 : 3}
                      fill={metric.color}
                      onMouseEnter={() => setHoveredIndex(index)}
                      onMouseLeave={() => setHoveredIndex(null)}
                    />
                  ))}
                  {index % Math.ceil(data.length / 5) === 0 || index === data.length - 1 ? (
                    <text x={x} y={height - 8} textAnchor="middle" fontSize="10" fill="#71717a">
                      {point.label || point.date}
                    </text>
                  ) : null}
                </g>
              );
            })}

            {hoveredIndex !== null && data[hoveredIndex] ? (
              <g>
                {(() => {
                  const point = data[hoveredIndex];
                  const x = getX(hoveredIndex);
                  const y = getY(activeMetrics[0].values[hoveredIndex] ?? 0);
                  const tooltipWidth = 180;
                  const tooltipHeight = 78;
                  const tx = Math.max(8, Math.min(x + 10, width - tooltipWidth - 8));
                  const ty = Math.max(8, y - tooltipHeight - 10);
                  return (
                    <>
                      <rect x={tx} y={ty} width={tooltipWidth} height={tooltipHeight} rx={8} fill="#111827" opacity="0.95" />
                      <text x={tx + 8} y={ty + 14} fontSize="10" fill="#f4f4f5">
                        {point.label || point.date}
                      </text>
                      {showSessions ? (
                        <text x={tx + 8} y={ty + 30} fontSize="10" fill="#f4f4f5">Sessions: {point.sessions}</text>
                      ) : null}
                      {showUsers ? (
                        <text x={tx + 8} y={ty + 44} fontSize="10" fill="#f4f4f5">Users: {point.users}</text>
                      ) : null}
                      {showTokens ? (
                        <text x={tx + 8} y={ty + 58} fontSize="10" fill="#f4f4f5">Estimated Tokens: {point.estimated_tokens}</text>
                      ) : null}
                      {showCost ? (
                        <text x={tx + 8} y={ty + 72} fontSize="10" fill="#f4f4f5">Estimated Cost: ${point.estimated_cost_usd.toFixed(4)}</text>
                      ) : null}
                    </>
                  );
                })()}
              </g>
            ) : null}
          </svg>
        )}
      </div>
    </div>
  );
}
