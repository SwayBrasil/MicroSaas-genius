// frontend/src/api.ts
import axios from "axios";

// Descobre a base da API:
// - Se tiver VITE_API_BASE_URL no build, usa ela
// - Se estiver rodando em localhost, usa http://localhost:8000
// - Se estiver em produção (domínio), usa "/api" (vai passar pelo Caddy)
const isLocalhost =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1";

export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL ||
  (isLocalhost ? "http://localhost:8000" : "/api");

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
  timeout: 20000,
  withCredentials: false,
});

// ---- Auth header (Bearer) ----
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers = config.headers || {};
    (config.headers as any).Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      // Se quiser, limpe o token aqui.
      // localStorage.removeItem("token");
    }
    return Promise.reject(err);
  }
);

// ==================== Tipos ====================
export type Thread = {
  id: number | string;
  title?: string;
  origin?: string | null;
  lead_score?: number | null;
  lead_level?: "frio" | "morno" | "quente" | null;
  lead_stage?: string | null;  // Estágio atual: "frio", "aquecimento", "aquecido", "quente", etc.
  metadata?: any;
  contact_name?: string | null;  // Nome do contato associado à thread
  last_message?: string | null;  // Preview da última mensagem
  last_message_at?: string | null;  // Data da última mensagem
  created_at?: string | null;  // Data de criação da thread
  // Novos campos de lead/contato
  funnel_id?: number | string | null;  // ID do funil
  stage_id?: number | string | null;  // ID da etapa no funil
  product_id?: number | string | null;  // ID do produto/plano principal
  source?: string | null;  // Origem: "Eduzz compra", "Eduzz abandono", "The Members", "WhatsApp orgânico", etc.
  tags?: string[];  // Lista de tags (strings simples)
  // temperature e score já existem acima (lead_level e lead_score)
};

export type Message = {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  is_human?: boolean;
};

export type LoginResponse = { token: string };
export type MeResponse = { id: number; email: string };

export type MessagesByDay = {
  date: string;
  user: number;
  assistant: number;
};

export type StatsResponse = {
  threads: number;
  user_messages: number;
  assistant_messages: number;
  total_messages: number;
  last_activity: string | null;
  messages_by_day?: MessagesByDay[];
  avg_assistant_response_ms?: number | null;
  lead_levels?: { quente: number; morno: number; frio: number; desconhecido?: number };
  messages_by_hour?: number[]; // 24 posições (0-23)
  threads_growth?: { date: string; count: number }[];
  origin_distribution?: { origin: string; count: number }[];
  response_rate?: number; // porcentagem
};

export type ProfileDTO = {
  id: string | number;
  email: string;
  name?: string;
  plan?: string;
  created_at?: string | null;
  last_activity_at?: string | null;
};

export type UsageDTO = {
  threads_total: number;
  messages_total: number;
  user_sent: number;
  assistant_sent: number;
};

export type TaskStatus = "open" | "done";
export type Task = {
  id: number | string;
  title: string;
  status: TaskStatus;
  due_date?: string | null;
  notes?: string | null;
};

// ==================== Auth ====================
export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>("/auth/login", { email, password });
  localStorage.setItem("token", data.token);
  return data;
}

export function logout() {
  localStorage.removeItem("token");
}

// ==================== Threads ====================
export async function createThread(title: string = "Nova conversa"): Promise<Thread> {
  const { data } = await api.post<Thread>("/threads", { title });
  return data;
}

export async function listThreads(): Promise<Thread[]> {
  const { data } = await api.get<Thread[]>("/threads");
  return data;
}

export async function deleteThread(threadId: number | string): Promise<void> {
  await api.delete(`/threads/${threadId}`);
}

export async function updateThread(
  threadId: number | string,
  body: Partial<{ 
    origin: string; 
    lead_score: number; 
    lead_level: "frio" | "morno" | "quente";
    funnel_id?: number | string | null;
    stage_id?: number | string | null;
    product_id?: number | string | null;
    source?: string | null;
    tags?: string[];
    metadata?: any;
  }>
): Promise<Thread> {
  const { data } = await api.patch<Thread>(`/threads/${threadId}`, body);
  return data;
}

// ==================== Messages ====================
export async function postMessage(threadId: number, content: string): Promise<Message> {
  const { data } = await api.post<Message>(`/threads/${threadId}/messages`, { content });
  return data;
}

export async function getMessages(threadId: number): Promise<Message[]> {
  const { data } = await api.get<Message[]>(`/threads/${threadId}/messages`);
  return data;
}

// ==================== Stats/Profile ====================
export async function getStats(): Promise<StatsResponse> {
  const { data } = await api.get<StatsResponse>("/stats");
  return data;
}

export async function getMe(): Promise<MeResponse> {
  const { data } = await api.get<MeResponse>("/me");
  return data;
}

export async function getProfile(): Promise<ProfileDTO> {
  try {
    const { data } = await api.get<any>("/me");
    return {
      id: data.id,
      email: data.email ?? "dev@local.com",
      name: data.name ?? "Usuário",
      plan: data.plan ?? "Trial",
      created_at: data.created_at ?? null,
      last_activity_at: data.last_activity_at ?? null,
    };
  } catch {
    return {
      id: "-",
      email: "dev@local.com",
      name: "Usuário",
      plan: "Trial",
      created_at: null,
      last_activity_at: null,
    };
  }
}

export async function getUsage(): Promise<UsageDTO> {
  try {
    const s = await getStats();
    return {
      threads_total: s.threads ?? 0,
      messages_total: s.total_messages ?? 0,
      user_sent: s.user_messages ?? 0,
      assistant_sent: s.assistant_messages ?? 0,
    };
  } catch {
    return { threads_total: 0, messages_total: 0, user_sent: 0, assistant_sent: 0 };
  }
}

// ==================== Takeover/Human Reply ====================
export async function setTakeover(
  threadId: number,
  active: boolean
): Promise<{ ok: boolean; human_takeover: boolean }> {
  // Backend espera { active: boolean }
  const { data } = await api.post<{ ok: boolean; human_takeover: boolean }>(
    `/threads/${threadId}/takeover`,
    { active }
  );
  return data;
}

export async function postHumanReply(
  threadId: number,
  content: string
): Promise<{ ok: boolean; message_id: number }> {
  // Backend usa human-reply (com hífen)
  const { data } = await api.post<{ ok: boolean; message_id: number }>(
    `/threads/${threadId}/human-reply`,
    { content }
  );
  return data;
}

// ==================== Tasks (CRUD) ====================
export async function listTasks(): Promise<Task[]> {
  const { data } = await api.get<Task[]>("/tasks");
  return data;
}

export async function createTask(task: Partial<Task>): Promise<Task> {
  const { data } = await api.post<Task>("/tasks", task);
  return data;
}

export async function updateTask(id: number | string, patch: Partial<Task>): Promise<Task> {
  const { data } = await api.patch<Task>(`/tasks/${id}`, patch);
  return data;
}

export async function deleteTask(id: number | string): Promise<void> {
  await api.delete(`/tasks/${id}`);
}

// ==================== SSE Helper ====================
export function sseUrlForThread(threadId: number | string) {
  const token = localStorage.getItem("token") || "";
  return `${API_BASE}/threads/${threadId}/stream?token=${encodeURIComponent(token)}`;
}

// ==================== CRM / Contacts ====================
export type Contact = {
  id: number;
  thread_id: number;
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  total_orders: number;
  total_spent: number; // em centavos
  average_ticket?: number | null; // em centavos
  most_bought_products?: any;
  last_interaction_at?: string | null;
  created_at: string;
  updated_at: string;
  tags: ContactTag[];
  notes: ContactNote[];
  reminders: ContactReminder[];
};

export type ContactTag = {
  id: number;
  tag: string;
  created_at: string;
};

export type ContactNote = {
  id: number;
  content: string;
  created_at: string;
  user_id: number;
};

export type ContactReminder = {
  id: number;
  message: string;
  due_date: string;
  completed: boolean;
  created_at: string;
};

export async function getContactByThread(threadId: number): Promise<Contact> {
  const { data } = await api.get<Contact>(`/contacts/thread/${threadId}`);
  return data;
}

export async function getContact(contactId: number): Promise<Contact> {
  const { data } = await api.get<Contact>(`/contacts/${contactId}`);
  return data;
}

export async function listContacts(): Promise<Contact[]> {
  const { data } = await api.get<Contact[]>("/contacts");
  return data;
}

export async function updateContact(contactId: number, patch: Partial<Contact>): Promise<Contact> {
  const { data } = await api.patch<Contact>(`/contacts/${contactId}`, patch);
  return data;
}

export async function addContactTag(contactId: number, tag: string): Promise<ContactTag> {
  const { data } = await api.post<ContactTag>(`/contacts/${contactId}/tags`, { tag });
  return data;
}

export async function removeContactTag(contactId: number, tagId: number): Promise<void> {
  await api.delete(`/contacts/${contactId}/tags/${tagId}`);
}

export async function addContactNote(contactId: number, content: string): Promise<ContactNote> {
  const { data } = await api.post<ContactNote>(`/contacts/${contactId}/notes`, { content });
  return data;
}

export async function deleteContactNote(contactId: number, noteId: number): Promise<void> {
  await api.delete(`/contacts/${contactId}/notes/${noteId}`);
}

export async function createContactReminder(
  contactId: number,
  message: string,
  dueDate: string
): Promise<ContactReminder> {
  const { data } = await api.post<ContactReminder>(`/contacts/${contactId}/reminders`, {
    message,
    due_date: dueDate,
  });
  return data;
}

export async function updateContactReminder(
  contactId: number,
  reminderId: number,
  completed: boolean
): Promise<ContactReminder> {
  const { data } = await api.patch<ContactReminder>(
    `/contacts/${contactId}/reminders/${reminderId}?completed=${completed}`,
    {}
  );
  return data;
}

// ==================== Billing / The Members ====================
export type Product = {
  id: number;
  external_product_id: string;
  title: string;
  type?: string;
  status?: string;
  source?: string;  // "eduzz", "themembers", "manual"
};

export type SubscriptionStatus = {
  has_subscription: boolean;
  is_active: boolean;
  subscription_id?: number;
  product_title?: string;
  status?: string;
  expires_at?: string;
  themembers_user_id?: string;
};

export type Subscription = {
  id: number;
  status: string;
  product_title?: string;
  started_at?: string;
  expires_at?: string;
  source?: string;
  themembers_user_id?: string;
};

export async function listProducts(source?: string): Promise<Product[]> {
  const params = source ? { source } : {};
  const { data } = await api.get<Product[]>("/billing/products", { params });
  return data;
}

export async function getContactSubscriptionStatus(contactId: number): Promise<SubscriptionStatus> {
  const { data } = await api.get<SubscriptionStatus>(`/billing/contacts/${contactId}/subscription-status`);
  return data;
}

export async function getContactSubscriptions(contactId: number): Promise<Subscription[]> {
  const { data } = await api.get<Subscription[]>(`/billing/contacts/${contactId}/subscriptions`);
  return data;
}

// ==================== Analytics ====================
export type AnalyticsSummary = {
  total_threads: number;
  total_contacts: number;
  total_sales: number;
  total_revenue: number;  // em centavos
  sales_with_conversation: number;
  sales_without_conversation: number;
  total_subscriptions: number;
  active_subscriptions: number;
};

export type SalesByDay = {
  date: string;
  qtd_vendas: number;
  valor_total: number;  // em centavos
};

export type ContactSales = {
  contact_id: number;
  contact_name: string;
  contact_email: string;
  sales: Array<{
    id: number;
    source: string;
    event: string;
    order_id: string | null;
    value: number | null;
    created_at: string;
    themembers_user_id: string | null;
  }>;
  subscriptions: Array<{
    id: number;
    status: string;
    product_title: string | null;
    started_at: string | null;
    expires_at: string | null;
    source: string | null;
    themembers_user_id: string | null;
  }>;
  total_sales: number;
  total_revenue: number;
  total_subscriptions: number;
  active_subscriptions: number;
};

export type Conversions = {
  period_days: number;
  threads_created: number;
  sales_total: number;
  sales_with_conversation: number;
  sales_without_conversation: number;
  conversion_rate: number;
  threads_by_origin: Array<{ origin: string; count: number }>;
  sales_by_origin: Array<{ origin: string; count: number }>;
};

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  const { data } = await api.get<AnalyticsSummary>("/analytics/summary");
  return data;
}

export async function getSalesByDay(days: number = 30): Promise<SalesByDay[]> {
  const { data } = await api.get<SalesByDay[]>(`/analytics/sales-by-day?days=${days}`);
  return data;
}

export async function getContactSales(contactId: number): Promise<ContactSales> {
  const { data } = await api.get<ContactSales>(`/analytics/contacts/${contactId}/sales`);
  return data;
}

export async function getConversions(days: number = 30): Promise<Conversions> {
  const { data } = await api.get<Conversions>(`/analytics/conversions?days=${days}`);
  return data;
}

export default api;
