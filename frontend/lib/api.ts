export type Agent = {
  id: string;
  name: string;
  description: string;
  instruction: string;
  voice_gender?: string;
  voice_name?: string;
  language: string;
  model: string;
  temperature?: number;
  business_type?: string;
  use_voice_to_voice?: boolean;
  business_info?: Record<string, string>;
  catalog_items?: Array<Record<string, string>>;
  faqs?: Array<{ question: string; answer: string }>;
  doctors?: Array<Record<string, string>>;
  knowledge_count?: number;
  created_at: string;
};

export type Session = {
  id: string;
  agent_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type KnowledgeFile = {
  id: string;
  agent_id: string;
  file_name: string;
  file_type: string;
  created_at: string;
  download_url?: string;
};

export type ProcessedKnowledge = {
  business_info: Record<string, string>;
  catalog_items: Array<Record<string, string>>;
  faqs: Array<{ question: string; answer: string }>;
  doctors: Array<Record<string, string>>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<T>;
}

export async function fetchAgents(): Promise<Agent[]> {
  const response = await fetch(`${API_BASE}/agents`, { cache: "no-store" });
  const data = await parseJson<{ agents: Agent[] }>(response);
  return data.agents;
}

export async function fetchAgent(agentId: string): Promise<Agent> {
  const response = await fetch(`${API_BASE}/agents/${agentId}`, {
    cache: "no-store",
  });
  const data = await parseJson<{ agent: Agent }>(response);
  return data.agent;
}

export async function createAgent(payload: {
  name: string;
  description: string;
  instruction?: string;
  model?: string;
  temperature?: number;
  language?: string;
  business_type?: string;
  use_voice_to_voice?: boolean;
  voice_gender?: string;
  business_info?: Record<string, string>;
  catalog_items?: Array<Record<string, string>>;
  faqs?: Array<{ question: string; answer: string }>;
  doctors?: Array<Record<string, string>>;
}): Promise<Agent> {
  const response = await fetch(`${API_BASE}/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await parseJson<{ agent: Agent }>(response);
  return data.agent;
}

export async function uploadKnowledge(
  agentId: string,
  files: File[],
): Promise<void> {
  if (!files.length) return;
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE}/agents/${agentId}/knowledge`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
}

export async function processKnowledge(
  files: File[],
  businessType: string,
): Promise<ProcessedKnowledge> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("business_type", businessType);
  const response = await fetch(`${API_BASE}/knowledge/process`, {
    method: "POST",
    body: formData,
  });
  return parseJson<ProcessedKnowledge>(response);
}

export async function deleteKnowledgeFile(fileId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/knowledge/files/${fileId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
}

export async function deleteAgent(agentId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/agents/${agentId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
}

export type AgentAnalytics = {
  session_count: number;
  user_count: number;
  message_count: number;
  estimated_tokens: number;
  estimated_cost_usd: number;
};

export type AgentAnalyticsTrendItem = {
  label: string;
  date: string;
  sessions: number;
  users: number;
  messages: number;
  estimated_tokens: number;
  estimated_cost_usd: number;
};

export async function updateAgent(
  agentId: string,
  payload: {
    name: string;
    description: string;
    instruction: string;
    language: string;
    temperature: number;
    business_type: string;
    use_voice_to_voice: boolean;
    voice_gender: string;
    business_info?: Record<string, string>;
    catalog_items?: Array<Record<string, string>>;
    faqs?: Array<{ question: string; answer: string }>;
    doctors?: Array<Record<string, string>>;
  },
): Promise<Agent> {
  const response = await fetch(`${API_BASE}/agents/${agentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await parseJson<{ agent: Agent }>(response);
  return data.agent;
}

export async function fetchAgentAnalytics(
  agentId: string,
): Promise<AgentAnalytics> {
  const response = await fetch(`${API_BASE}/agents/${agentId}/analytics`, {
    cache: "no-store",
  });
  const data = await parseJson<{ analytics: AgentAnalytics }>(response);
  return data.analytics;
}

export async function fetchAgentAnalyticsTrend(
  agentId: string,
  range = "7d",
): Promise<AgentAnalyticsTrendItem[]> {
  const response = await fetch(
    `${API_BASE}/agents/${agentId}/analytics/trend?range=${encodeURIComponent(range)}`,
    { cache: "no-store" },
  );
  const data = await parseJson<{ trend: AgentAnalyticsTrendItem[] }>(response);
  return data.trend;
}

export async function fetchKnowledgeFiles(
  agentId: string,
): Promise<KnowledgeFile[]> {
  const response = await fetch(`${API_BASE}/agents/${agentId}/knowledge`, {
    cache: "no-store",
  });
  const data = await parseJson<{ files: KnowledgeFile[] }>(response);
  return data.files;
}

export async function fetchSessions(agentId: string): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/agents/${agentId}/sessions`, {
    cache: "no-store",
  });
  const data = await parseJson<{ sessions: Session[] }>(response);
  return data.sessions;
}

export async function createSession(
  agentId: string,
  title?: string,
): Promise<Session> {
  const response = await fetch(`${API_BASE}/agents/${agentId}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  const data = await parseJson<{ session: Session }>(response);
  return data.session;
}

export async function fetchMessages(sessionId: string): Promise<Message[]> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
    cache: "no-store",
  });
  const data = await parseJson<{ messages: Message[] }>(response);
  return data.messages;
}

export async function sendMessage(
  sessionId: string,
  content: string,
): Promise<Message[]> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  const data = await parseJson<{ messages: Message[] }>(response);
  return data.messages;
}

export async function transcribeAudio(file: File): Promise<string> {
  const formData = new FormData();
  formData.append("audio", file);
  const response = await fetch(`${API_BASE}/audio/transcribe`, {
    method: "POST",
    body: formData,
  });
  const data = await parseJson<{ text: string }>(response);
  return data.text;
}

export async function synthesizeSpeech(
  text: string,
  voiceGender = "female",
): Promise<string> {
  const response = await fetch(`${API_BASE}/audio/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice_gender: voiceGender }),
  });
  if (!response.ok) {
    const t = await response.text();
    throw new Error(t || response.statusText);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
