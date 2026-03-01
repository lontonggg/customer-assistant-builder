"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { SectionCard } from "@/components/ui/section-card";
import { Label } from "@/components/ui/label";
import { FieldShell } from "@/components/ui/field-shell";
import { Button } from "@/components/ui/button";
import { createAgent, processKnowledge, uploadKnowledge } from "@/lib/api";
import { Stepper } from "@/components/stepper";
import { IconEye, IconSpinner, IconTrash } from "@/components/ui/icons";
import { isMockLoggedIn } from "@/lib/mock-auth";

const languages = [
  { label: "English", value: "en-US" },
  { label: "Indonesian", value: "id-ID" },
  { label: "Spanish", value: "es-ES" },
  { label: "French", value: "fr-FR" },
  { label: "Malay", value: "ms-MY" },
  { label: "Chinese", value: "zh-CN" },
  { label: "Indian", value: "hi-IN" },
];
const businessTypes = ["Fashion", "Clinic"];
const steps = ["Setup", "Knowledge base", "Review"];

type EditableFaq = {
  question: string;
  answer: string;
};

type CatalogRow = Record<string, string>;
type BusinessInfo = Record<string, string>;
type DoctorRow = Record<string, string>;

type CatalogColumnRule = {
  key: string;
  label: string;
  valueType: "string" | "int" | "numeric";
  clinicOnly?: boolean;
};

const CATALOG_EDITABLE_RULES: CatalogColumnRule[] = [
  { key: "name", label: "Name", valueType: "string" },
  { key: "short_desc", label: "Short Description", valueType: "string" },
  { key: "price", label: "Price", valueType: "numeric" },
  { key: "currency_code", label: "Currency Code", valueType: "string" },
  { key: "duration_mins", label: "Duration (Minutes)", valueType: "int", clinicOnly: true },
];

const getEditableCatalogRules = (businessType: string) =>
  CATALOG_EDITABLE_RULES.filter((rule) => !rule.clinicOnly || businessType === "Clinic");

const DOCTOR_EDITABLE_RULES = [
  { key: "full_name", label: "Full Name" },
  { key: "title", label: "Title" },
  { key: "specialization", label: "Specialization" },
  { key: "qualifications", label: "Qualifications" },
  { key: "bio", label: "Bio" },
  { key: "languages", label: "Languages" },
] as const;

const normalizeNumericInput = (value: string) => {
  const raw = value.replace(/[^0-9.]/g, "");
  const dotIndex = raw.indexOf(".");
  if (dotIndex === -1) return raw;
  const left = raw.slice(0, dotIndex + 1);
  const right = raw.slice(dotIndex + 1).replace(/\./g, "");
  return `${left}${right}`;
};

export default function BuilderPage() {
  const router = useRouter();
  const [authReady, setAuthReady] = useState(false);
  const [step, setStep] = useState(0);
  const [agentName, setAgentName] = useState("");
  const [language, setLanguage] = useState("en-US");
  const [businessType, setBusinessType] = useState("");
  const [description, setDescription] = useState("");
  const [instruction, setInstruction] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [temperature, setTemperature] = useState(0.4);
  const [voiceGender, setVoiceGender] = useState("female");
  const [businessInfo, setBusinessInfo] = useState<BusinessInfo>({});
  const [ocrFaqs, setOcrFaqs] = useState<EditableFaq[]>([]);
  const [catalogColumns, setCatalogColumns] = useState<string[]>([]);
  const [catalogRows, setCatalogRows] = useState<CatalogRow[]>([]);
  const [doctorColumns, setDoctorColumns] = useState<string[]>([]);
  const [doctorRows, setDoctorRows] = useState<DoctorRow[]>([]);
  const [isKnowledgeProcessed, setIsKnowledgeProcessed] = useState(false);
  const [isProcessingKnowledge, setIsProcessingKnowledge] = useState(false);
  const [processingStartedAt, setProcessingStartedAt] = useState<number | null>(null);
  const [processingSeconds, setProcessingSeconds] = useState(0);
  const [lastProcessedSeconds, setLastProcessedSeconds] = useState<number | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [creatingStartedAt, setCreatingStartedAt] = useState<number | null>(null);
  const [creatingSeconds, setCreatingSeconds] = useState(0);
  const [createError, setCreateError] = useState<string | null>(null);

  const tempProfile = useMemo(() => {
    if (temperature <= 0.3) {
      return {
        label: "Very Focused",
        hint: "More consistent, concise, and predictable responses.",
      };
    }
    if (temperature >= 0.7) {
      return {
        label: "Explorative",
        hint: "More varied and creative responses with freer expression.",
      };
    }
    return {
      label: "Balanced",
      hint: "A mix of reliable structure and natural tone.",
    };
  }, [temperature]);

  const requiredFilled = () => {
    if (step === 0) return agentName.trim() && businessType.trim();
    if (step === 1) return isKnowledgeProcessed;
    return true;
  };

  const goNext = () => {
    if (!requiredFilled()) {
      setShowErrors(true);
      return;
    }
    setShowErrors(false);
    setStep((prev) => Math.min(prev + 1, steps.length - 1));
  };

  const goBack = () => {
    if (step === 0) {
      router.push("/");
      return;
    }
    setShowErrors(false);
    setStep((prev) => Math.max(prev - 1, 0));
  };

  const handleCreateAgent = async () => {
    if (!requiredFilled()) {
      setShowErrors(true);
      return;
    }

    setShowErrors(false);
    setIsCreating(true);
    setCreatingStartedAt(Date.now());
    setCreatingSeconds(0);
    setCreateError(null);

    try {
      const agent = await createAgent({
        name: agentName.trim(),
        description: description.trim() || "Text-based AI chatbot",
        instruction: instruction.trim(),
        model: "mistral-small",
        temperature,
        business_type: businessType,
        use_voice_to_voice: true,
        voice_gender: voiceGender,
        language,
        business_info: businessInfo,
        catalog_items: catalogRows,
        faqs: ocrFaqs,
        doctors: doctorRows,
      });

      await uploadKnowledge(agent.id, files);
      router.push(`/agents/${agent.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create chatbot.";
      setCreateError(message);
    } finally {
      setIsCreating(false);
      setCreatingStartedAt(null);
      setCreatingSeconds(0);
    }
  };

  const removeSelectedFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSelectFiles = (selected: FileList | null) => {
    if (!selected) return;
    const incoming = Array.from(selected);
    if (!incoming.length) return;
    setFiles((prev) => [...prev, ...incoming]);
    setIsKnowledgeProcessed(false);
  };

  useEffect(() => {
    if (!isMockLoggedIn()) {
      router.replace("/");
      return;
    }
    setAuthReady(true);
  }, [router]);

  useEffect(() => {
    setIsKnowledgeProcessed(false);
    setBusinessInfo({});
    setOcrFaqs([]);
    setCatalogColumns([]);
    setCatalogRows([]);
    setDoctorColumns([]);
    setDoctorRows([]);
  }, [businessType]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [step]);

  const processKnowledgeBase = async () => {
    if (!files.length) {
      setCreateError("Please upload at least one PDF or image file before processing.");
      return;
    }
    setShowErrors(false);
    const startTime = Date.now();
    setIsProcessingKnowledge(true);
    setProcessingStartedAt(startTime);
    setProcessingSeconds(0);
    setLastProcessedSeconds(null);
    setCreateError(null);
    try {
      const processed = await processKnowledge(files, businessType || "Fashion");
      const editableRules = getEditableCatalogRules(businessType);
      const cols = editableRules.map((rule) => rule.key);
      const doctorCols = DOCTOR_EDITABLE_RULES.map((rule) => rule.key);
      setBusinessInfo((processed.business_info || {}) as BusinessInfo);
      setOcrFaqs((processed.faqs || []).map((item) => ({ question: item.question || "", answer: item.answer || "" })));
      setCatalogColumns(cols);
      setCatalogRows(
        (processed.catalog_items || []).map((row) => {
          const normalized: CatalogRow = {};
          cols.forEach((col) => {
            normalized[col] = String(row[col] ?? "");
          });
          return normalized;
        }),
      );
      setDoctorColumns(doctorCols);
      setDoctorRows(
        (processed.doctors || []).map((row) => {
          const normalized: DoctorRow = {};
          doctorCols.forEach((col) => {
            const raw = row[col];
            normalized[col] = Array.isArray(raw) ? raw.join(", ") : String(raw ?? "");
          });
          return normalized;
        }),
      );
      setIsKnowledgeProcessed(true);
      const elapsed = Math.max(0, Math.floor((Date.now() - startTime) / 1000));
      setLastProcessedSeconds(elapsed);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Knowledge processing failed.";
      setCreateError(message);
    } finally {
      setIsProcessingKnowledge(false);
      setProcessingStartedAt(null);
      setProcessingSeconds(0);
    }
  };

  useEffect(() => {
    if (!isProcessingKnowledge || !processingStartedAt) return;
    const t = setInterval(() => {
      setProcessingSeconds(Math.max(0, Math.floor((Date.now() - processingStartedAt) / 1000)));
    }, 200);
    return () => clearInterval(t);
  }, [isProcessingKnowledge, processingStartedAt]);

  useEffect(() => {
    if (!isCreating || !creatingStartedAt) return;
    const t = setInterval(() => {
      setCreatingSeconds(Math.max(0, Math.floor((Date.now() - creatingStartedAt) / 1000)));
    }, 200);
    return () => clearInterval(t);
  }, [isCreating, creatingStartedAt]);

  if (!authReady) {
    return <main className="min-h-screen bg-white" />;
  }

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.92),rgba(255,255,255,0.7)_42%),linear-gradient(to_bottom,#ffffff,#f3f4f6)]" />

      <div className="relative mx-auto min-h-screen max-w-6xl px-6 py-12 lg:py-16">
        <header className="mt-2 flex w-full flex-col gap-2 animate-fade-up">
          <h1 className="text-3xl font-semibold text-zinc-900 sm:text-4xl lg:text-4xl">
            Build your chatbot step by step.
          </h1>
          <p className="text-zinc-600 text-base sm:text-lg">
            Upload knowledge, define instructions, set model behavior, then generate.
          </p>
        </header>

        <div className="mt-8 w-full space-y-6">
          <SectionCard
            title={`${String(step + 1).padStart(2, "0")} - ${steps[step]}`}
            subtitle="Complete this step and continue."
            className="animate-fade-up"
            titleClassName="text-lg font-semibold tracking-[0.15em] text-zinc-900"
          >
            <div className="mb-6">
              <Stepper steps={steps} current={step} />
            </div>

            {step === 0 && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>
                    Chatbot name <span className="text-red-600">*</span>
                  </Label>
                  <FieldShell className={showErrors && !agentName ? "border-red-500/80" : undefined}>
                    <input
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                      className="w-full bg-transparent text-lg font-semibold text-zinc-900 placeholder:text-zinc-500 focus:outline-none"
                      placeholder="Ex: Customer Support Bot"
                    />
                  </FieldShell>
                  {showErrors && !agentName ? (
                    <p className="text-xs text-red-700">Chatbot name is required.</p>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <Label>
                    Business type <span className="text-red-600">*</span>
                  </Label>
                  <FieldShell className={showErrors && !businessType ? "border-red-500/80" : undefined}>
                    <select
                      value={businessType}
                      onChange={(e) => setBusinessType(e.target.value)}
                      className="w-full bg-transparent text-zinc-900 focus:outline-none"
                    >
                      <option value="" className="bg-white text-zinc-500">
                        Select business type
                      </option>
                      {businessTypes.map((type) => (
                        <option key={type} value={type} className="bg-white">
                          {type}
                        </option>
                      ))}
                    </select>
                  </FieldShell>
                  {showErrors && !businessType ? (
                    <p className="text-xs text-red-700">Business type is required.</p>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <Label>Description</Label>
                  <FieldShell>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={3}
                      className="w-full resize-none bg-transparent text-zinc-900 placeholder:text-zinc-500 focus:outline-none"
                      placeholder="Briefly describe the chatbot purpose."
                    />
                  </FieldShell>
                </div>

                <div className="space-y-2">
                  <Label>Main language</Label>
                  <FieldShell>
                    <select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="w-full bg-transparent text-zinc-900 focus:outline-none"
                    >
                      {languages.map((lang) => (
                        <option key={lang.value} value={lang.value} className="bg-white">
                          {lang.label}
                        </option>
                      ))}
                    </select>
                  </FieldShell>
                </div>

                <div className="space-y-2">
                  <Label>Preferred assistant voice</Label>
                  <FieldShell>
                    <select
                      value={voiceGender}
                      onChange={(e) => setVoiceGender(e.target.value)}
                      className="w-full bg-transparent text-zinc-900 focus:outline-none"
                    >
                      <option value="female" className="bg-white">Female Voice</option>
                      <option value="male" className="bg-white">Male Voice</option>
                    </select>
                  </FieldShell>
                </div>

                <div className="space-y-2">
                  <Label>Response style</Label>
                  <div className="rounded-2xl border border-zinc-200 bg-white px-4 py-4">
                    <div className="text-sm text-zinc-700">
                      <p className="font-semibold text-zinc-900">{tempProfile.label}</p>
                      <p className="mt-1">{tempProfile.hint}</p>
                    </div>
                    <div className="mt-4 flex items-center gap-3 text-xs text-zinc-500">
                      <span>Stable</span>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.1}
                        value={temperature}
                        onChange={(e) => setTemperature(Number(e.target.value))}
                        className="w-full accent-zinc-300"
                      />
                      <span>Creative</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Knowledge files (PDF / Images)</Label>
                  <FieldShell>
                    <input
                      type="file"
                      multiple
                      accept=".pdf,image/*"
                      onChange={(e) => {
                        handleSelectFiles(e.target.files);
                        e.currentTarget.value = "";
                      }}
                      className="w-full cursor-pointer bg-transparent text-sm text-zinc-900 file:mr-3 file:rounded-xl file:border-0 file:bg-zinc-100 file:px-3 file:py-2 file:text-zinc-700"
                    />
                  </FieldShell>
                  {files.length ? (
                    <div className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-xs text-zinc-600">
                      <p className="mb-2">{files.length} file(s) selected</p>
                      <div className="space-y-2">
                        {files.map((file, index) => (
                          <div key={`${file.name}-${index}`} className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2">
                            <a
                              href={URL.createObjectURL(file)}
                              target="_blank"
                              rel="noreferrer"
                              className="truncate pr-2 text-zinc-900 underline"
                            >
                              {file.name}
                            </a>
                            <div className="ml-3 flex shrink-0 items-center gap-1">
                              <button
                                type="button"
                                onClick={() => window.open(URL.createObjectURL(file), "_blank", "noopener,noreferrer")}
                                className="rounded-md p-1 text-zinc-700 hover:bg-zinc-100"
                                aria-label={`Preview ${file.name}`}
                              >
                                <IconEye className="h-4 w-4" />
                              </button>
                              <button
                                type="button"
                                onClick={() => removeSelectedFile(index)}
                                className="rounded-md p-1 text-red-700 hover:bg-red-100"
                                aria-label={`Remove ${file.name}`}
                              >
                                <IconTrash className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <Label>Additional context / instruction</Label>
                  <FieldShell>
                    <textarea
                      value={instruction}
                      onChange={(e) => {
                        setInstruction(e.target.value);
                        setIsKnowledgeProcessed(false);
                      }}
                      rows={4}
                      className="w-full resize-none bg-transparent text-zinc-900 placeholder:text-zinc-500 focus:outline-none"
                      placeholder="Example: Keep answers polite and concise, and rely on uploaded files whenever relevant."
                    />
                  </FieldShell>
                </div>

                <div className="flex flex-col justify-center gap-4">
                  <Button onClick={processKnowledgeBase} disabled={isProcessingKnowledge}>
                    {isProcessingKnowledge ? (
                      <span className="inline-flex items-center gap-2">
                        <IconSpinner className="h-4 w-4 animate-spin" />
                        Processing for {processingSeconds}s...
                      </span>
                    ) : (
                      "Process knowledge base"
                    )}
                  </Button>
                  {createError ? <p className="text-xs text-red-700">{createError}</p> : null}
                  {!isKnowledgeProcessed ? (
                    <p className="text-xs text-zinc-600">
                      Process the uploaded files first to generate editable FAQ and catalog data.
                    </p>
                  ) : (
                    <p className="text-xs text-emerald-700">
                      Successfully processed in {lastProcessedSeconds ?? 0}s. You can review and edit below.
                    </p>
                  )}
                </div>

                {isKnowledgeProcessed ? (
                  <>
                    <div className="rounded-2xl border border-zinc-200 bg-white p-4">
                      <p className="text-sm font-semibold text-zinc-900">OCR Review</p>
                      <p className="mt-1 text-xs text-zinc-600">
                        Review and edit the extracted data before continuing.
                      </p>
                    </div>

                    <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                      <p className="text-sm font-semibold text-zinc-900">Business Info</p>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {Object.entries(businessInfo).map(([key, value]) => (
                          <div key={key} className="space-y-1">
                            <p className="text-xs font-medium capitalize text-zinc-600">{key.replaceAll("_", " ")}</p>
                            <input
                              value={value}
                              onChange={(e) =>
                                setBusinessInfo((prev) => ({ ...prev, [key]: e.target.value }))
                              }
                              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-zinc-400 focus:outline-none"
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                      <p className="text-sm font-semibold text-zinc-900">{businessType === "Clinic" ? "Services" : "Products"}</p>
                      <div className="overflow-x-auto">
                        <table className="min-w-full border-collapse text-left text-xs">
                          <thead>
                            <tr>
                              {catalogColumns.map((column, colIndex) => (
                                <th key={`header-${colIndex}`} className="border border-zinc-200 bg-zinc-50 p-2 align-top">
                                  <span className="block px-2 py-1 font-semibold text-zinc-900">
                                    {getEditableCatalogRules(businessType).find((rule) => rule.key === column)?.label || column}
                                  </span>
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {catalogRows.map((row, rowIndex) => (
                              <tr key={`row-${rowIndex}`}>
                                {catalogColumns.map((column, colIndex) => (
                                  <td key={`cell-${rowIndex}-${colIndex}`} className="border border-zinc-200 p-2 align-top">
                                    <input
                                      value={row[column] ?? ""}
                                      onChange={(e) => {
                                        const rawValue = e.target.value;
                                        const rule = getEditableCatalogRules(businessType).find(
                                          (item) => item.key === column,
                                        );
                                        const value =
                                          rule?.valueType === "int"
                                            ? rawValue.replace(/\D/g, "")
                                            : rule?.valueType === "numeric"
                                              ? normalizeNumericInput(rawValue)
                                              : rawValue;
                                        setCatalogRows((prev) =>
                                          prev.map((r, i) => (i === rowIndex ? { ...r, [column]: value } : r)),
                                        );
                                      }}
                                      className="w-full min-w-[180px] rounded-md border border-zinc-200 bg-white px-2 py-1 text-zinc-900 focus:border-zinc-400 focus:outline-none"
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
                      <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-zinc-900">Doctors</p>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              setDoctorRows((prev) => [
                                ...prev,
                                Object.fromEntries(doctorColumns.map((col) => [col, ""])),
                              ])
                            }
                          >
                            Add Doctor
                          </Button>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="min-w-full border-collapse text-left text-xs">
                            <thead>
                              <tr>
                                {doctorColumns.map((column, colIndex) => (
                                  <th key={`doctor-header-${colIndex}`} className="border border-zinc-200 bg-zinc-50 p-2 align-top">
                                    <span className="block px-2 py-1 font-semibold text-zinc-900">
                                      {DOCTOR_EDITABLE_RULES.find((rule) => rule.key === column)?.label || column}
                                    </span>
                                  </th>
                                ))}
                                <th className="border border-zinc-200 bg-zinc-50 p-2 align-top">
                                  <span className="block px-2 py-1 font-semibold text-zinc-900">Action</span>
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {doctorRows.map((row, rowIndex) => (
                                <tr key={`doctor-row-${rowIndex}`}>
                                  {doctorColumns.map((column, colIndex) => (
                                    <td key={`doctor-cell-${rowIndex}-${colIndex}`} className="border border-zinc-200 p-2 align-top">
                                      <input
                                        value={row[column] ?? ""}
                                        onChange={(e) => {
                                          const value = e.target.value;
                                          setDoctorRows((prev) =>
                                            prev.map((r, i) => (i === rowIndex ? { ...r, [column]: value } : r)),
                                          );
                                        }}
                                        className="w-full min-w-[180px] rounded-md border border-zinc-200 bg-white px-2 py-1 text-zinc-900 focus:border-zinc-400 focus:outline-none"
                                      />
                                    </td>
                                  ))}
                                  <td className="border border-zinc-200 p-2 align-top">
                                    <button
                                      type="button"
                                      onClick={() => setDoctorRows((prev) => prev.filter((_, i) => i !== rowIndex))}
                                      className="rounded-md p-1 text-red-700 hover:bg-red-100"
                                      aria-label={`Delete doctor row ${rowIndex + 1}`}
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

                    <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-zinc-900">FAQ List</p>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setOcrFaqs((prev) => [...prev, { question: "", answer: "" }])}
                        >
                          Add FAQ
                        </Button>
                      </div>
                      {ocrFaqs.map((item, index) => (
                        <div key={`faq-${index}`} className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-medium text-zinc-600">FAQ #{index + 1}</p>
                            <button
                              type="button"
                              onClick={() => setOcrFaqs((prev) => prev.filter((_, i) => i !== index))}
                              className="rounded-md p-1 text-red-700 hover:bg-red-100"
                              aria-label={`Delete FAQ ${index + 1}`}
                            >
                              <IconTrash className="h-4 w-4" />
                            </button>
                          </div>
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-zinc-600">Question</p>
                            <input
                              value={item.question}
                              onChange={(e) =>
                                setOcrFaqs((prev) =>
                                  prev.map((faq, i) => (i === index ? { ...faq, question: e.target.value } : faq)),
                                )
                              }
                              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-zinc-400 focus:outline-none"
                            />
                          </div>
                          <div className="space-y-1">
                            <p className="text-xs font-medium text-zinc-600">Answer</p>
                            <textarea
                              value={item.answer}
                              rows={3}
                              onChange={(e) =>
                                setOcrFaqs((prev) =>
                                  prev.map((faq, i) => (i === index ? { ...faq, answer: e.target.value } : faq)),
                                )
                              }
                              className="w-full resize-y rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-zinc-400 focus:outline-none"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : null}
              </div>
            )}

            {step === 2 && (
              <div className="space-y-3 text-sm text-zinc-700">
                <SummaryRow label="Chatbot name" value={agentName || "Not set"} />
                <SummaryRow label="Description" value={description || "Not set"} multiline />
                <SummaryRow label="Business type" value={businessType || "Not set"} />
                <SummaryRow
                  label="Language"
                  value={languages.find((lang) => lang.value === language)?.label || language || "Not set"}
                />
                <SummaryRow label="Preferred voice" value={voiceGender === "male" ? "Male Voice" : "Female Voice"} />
                <SummaryRow label="Instruction" value={instruction || "Not set"} multiline />
                <SummaryRow
                  label="Knowledge files"
                  value={files.length ? files.map((f) => f.name).join(", ") : "No files uploaded"}
                  multiline
                />
                <SummaryRow label="Response style" value={`${tempProfile.label} - ${tempProfile.hint}`} multiline />

                <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                  <p className="text-sm font-semibold text-zinc-900">Business Info</p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {Object.entries(businessInfo).map(([key, value]) => (
                      <div key={`review-business-${key}`} className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                        <p className="text-xs font-medium capitalize text-zinc-600">{key.replaceAll("_", " ")}</p>
                        <p className="mt-1 text-sm text-zinc-900 whitespace-pre-wrap">{value || "-"}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                  <p className="text-sm font-semibold text-zinc-900">{businessType === "Clinic" ? "Services" : "Products"}</p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full border-collapse text-left text-xs">
                      <thead>
                        <tr>
                          {catalogColumns.map((column, colIndex) => (
                            <th key={`review-header-${colIndex}`} className="border border-zinc-200 bg-zinc-50 p-2 align-top">
                              <span className="block px-2 py-1 font-semibold text-zinc-900">
                                {getEditableCatalogRules(businessType).find((rule) => rule.key === column)?.label || column}
                              </span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {catalogRows.map((row, rowIndex) => (
                          <tr key={`review-row-${rowIndex}`}>
                            {catalogColumns.map((column, colIndex) => (
                              <td key={`review-cell-${rowIndex}-${colIndex}`} className="border border-zinc-200 p-2 align-top">
                                <span className="block min-w-[180px] px-1 py-0.5 text-zinc-900 whitespace-pre-wrap">
                                  {row[column] || "-"}
                                </span>
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {businessType === "Clinic" ? (
                  <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                    <p className="text-sm font-semibold text-zinc-900">Doctors</p>
                    {doctorRows.length === 0 ? (
                      <p className="text-xs text-zinc-600">No doctors.</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full border-collapse text-left text-xs">
                          <thead>
                            <tr>
                              {doctorColumns.map((column, colIndex) => (
                                <th key={`review-doctor-header-${colIndex}`} className="border border-zinc-200 bg-zinc-50 p-2 align-top">
                                  <span className="block px-2 py-1 font-semibold text-zinc-900">
                                    {DOCTOR_EDITABLE_RULES.find((rule) => rule.key === column)?.label || column}
                                  </span>
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {doctorRows.map((row, rowIndex) => (
                              <tr key={`review-doctor-row-${rowIndex}`}>
                                {doctorColumns.map((column, colIndex) => (
                                  <td key={`review-doctor-cell-${rowIndex}-${colIndex}`} className="border border-zinc-200 p-2 align-top">
                                    <span className="block min-w-[180px] px-1 py-0.5 text-zinc-900 whitespace-pre-wrap">
                                      {row[column] || "-"}
                                    </span>
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ) : null}

                <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4">
                  <p className="text-sm font-semibold text-zinc-900">FAQ List</p>
                  {ocrFaqs.length === 0 ? (
                    <p className="text-xs text-zinc-600">No FAQ items.</p>
                  ) : (
                    ocrFaqs.map((item, index) => (
                      <div key={`review-faq-${index}`} className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-2">
                        <p className="text-xs font-medium text-zinc-600">FAQ #{index + 1}</p>
                        <div>
                          <p className="text-xs font-medium text-zinc-600">Question</p>
                          <p className="mt-1 text-sm text-zinc-900 whitespace-pre-wrap">{item.question || "-"}</p>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-zinc-600">Answer</p>
                          <p className="mt-1 text-sm text-zinc-900 whitespace-pre-wrap">{item.answer || "-"}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="pt-2 text-center">
                  {createError ? <p className="mb-2 text-xs text-red-700">{createError}</p> : null}
                  <Button
                    className="min-w-[320px] py-4 text-lg font-semibold shadow-lg shadow-zinc-300/90"
                    onClick={handleCreateAgent}
                    disabled={isCreating}
                  >
                    {isCreating ? (
                      <span className="inline-flex items-center gap-2">
                        <IconSpinner className="h-5 w-5 animate-spin" />
                        Processing for {creatingSeconds}s...
                      </span>
                    ) : (
                      "Generate Chatbot"
                    )}
                  </Button>
                </div>
              </div>
            )}
          </SectionCard>

          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={goBack}>
              Back
            </Button>
            {step < steps.length - 1 ? (
              <Button onClick={goNext} disabled={step === 1 && !isKnowledgeProcessed}>
                Next step
              </Button>
            ) : (
              <div />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  multiline,
}: {
  label: string;
  value: string;
  multiline?: boolean;
}) {
  return (
    <div className="space-y-1 rounded-2xl border border-zinc-200 bg-white px-3 py-2">
      <span className="text-xs font-medium text-zinc-600">{label}</span>
      {multiline ? (
        <div className="max-h-32 overflow-y-auto whitespace-pre-line text-zinc-900">{value}</div>
      ) : (
        <div className="text-sm font-semibold text-zinc-900">{value}</div>
      )}
    </div>
  );
}
