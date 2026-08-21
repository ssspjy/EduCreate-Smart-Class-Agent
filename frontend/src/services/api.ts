// services/api.ts — 前端 API 客户端
// 比赛版主线：上传 -> GPS澄清 -> 生成大纲 -> PPTX预览 -> 质检
// LessonIR 数据契约统一：GPS 澄清结果通过 GpsClarifyResult 承载，LessonIR 由后端管理版本

export interface Material {
  file_id: string;
  filename: string;
  status: "uploaded" | "parsing" | "parsed" | "failed" | "queued" | "error";
  mime?: string;
  extension?: string;
  size?: number;
  chunk_count?: number;
  created_at?: string;
  parsed_at?: string | null;
  error_message?: string | null;
}

export interface MaterialChunk {
  id: string;
  material_id: string;
  chunk_index: number;
  content: string;
  page_ref: number | null;
  bbox?: unknown;
  media_ref: string | null;
  modality: string;
  token_count: number;
}

// ── GPS 类型（与 backend/app/schemas/gps.py GpsClarifyResult 完全对齐）──────────

export interface GpsClarifyResult {
  subject: string;
  grade: string;
  topic: string;
  objectives: string[];
  key_points: string[];
  difficulty: "easy" | "medium" | "hard";
  style: string;       // 新增：授课风格
  confidence: number;  // 新增：置信度
}

export interface MissingSlot {
  slot: string;
  reason: string;
}

export interface ClarifyResponse {
  result: GpsClarifyResult;
  missing_slots: MissingSlot[];
  needs_more_info: boolean;
  suggestion: string | null;
  session_id?: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

// ── DAG 类型 ──────────────────────────────────────────────────────────────────

export interface DagNodeData {
  label: string;
  value: string | string[];
  type: "root" | "slot_filled" | "slot_missing" | "dialogue";
  level: number;
  is_filled: boolean;
  new_in_round: boolean;
  source_turn: number;
}

export interface DagMeta {
  filled_count: number;
  missing_count: number;
  total_slots: number;
  completion: number;
  dialogue_count: number;
  dialogue_collapsed: boolean;
}

export interface DagGraph {
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: DagNodeData; style?: Record<string, string> }>;
  edges: Array<{ id: string; source: string; target: string; label?: string; animated?: boolean }>;
  meta: DagMeta;
}

// ── Lesson 类型 ───────────────────────────────────────────────────────────────

export interface Lesson {
  id: string;
  title: string;
  subject: string;
  grade: string;
  topic: string;
  status: string;
}

// ── LessonIR 类型 ─────────────────────────────────────────────────────────────

export interface TeachingSlots {
  subject: string;
  grade: string;
  topic: string;
  duration_min: number;
  difficulty: "easy" | "medium" | "hard";
  style: string;
  objectives: string[];
  key_points: string[];
  activities: string[];
  prerequisites: string[];
}

export interface DialogueTurn {
  role: string;
  content: string;
  timestamp: string;
  filled_slots: string[];
}

export interface DagSnapshot {
  turns: DialogueTurn[];
}

export interface MaterialBinding {
  material_id: string;
  chunk_ids: string[];
  bound_slot: string;
  excerpt: string;
  page_ref: number | null;
}

export interface LessonIR {
  id: string;
  lesson_id: string;
  version: number;
  slots: TeachingSlots;
  dag_snapshot: DagSnapshot;
  reference_materials: MaterialBinding[];
  created_at: string;
}

export interface LessonIRCreate {
  lesson_id: string;
  slots: TeachingSlots;
  dag_snapshot: DagSnapshot;
  reference_materials: MaterialBinding[];
}

// ── PPT 大纲类型 ─────────────────────────────────────────────────────────────

export interface OutlineSection {
  id: string;
  title: string;
  bullets: string[];
  duration_minutes: number;
  slide_count: number;
}

export interface Outline {
  title: string;
  subject: string;
  grade: string;
  sections: OutlineSection[];
  total_slides: number;
  total_duration_minutes: number;
}

export interface QualityReport {
  score: number;
  clarity: number;
  coverage: number;
  engagement: number;
  suggestions: string[];
}

// ── API 调用 ─────────────────────────────────────────────────────────────────

const API_BASE = (import.meta.env.VITE_API_BASE || "/api/v1").replace(/\/$/, "");

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("educreate-access-token");
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

// ── 参考资料 ──────────────────────────────────────────────────────────────────

export const apiUploadMaterial = (file: File): Promise<Material> => {
  const form = new FormData();
  form.append("file", file);
  const token = localStorage.getItem("educreate-access-token");
  return fetch(`${API_BASE}/materials/upload`, {
    method: "POST",
    body: form,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  }).then(
    async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      return r.json() as Promise<Material>;
    }
  );
};

export const apiLogin = async (username: string, password: string): Promise<string> => {
  const body = new URLSearchParams({ username, password });
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { access_token: string };
  localStorage.setItem("educreate-access-token", payload.access_token);
  return payload.access_token;
};

export const apiGetCurrentUser = (): Promise<{ user_id: string; role: string }> =>
  apiFetch<{ user_id: string; role: string }>("/auth/me");

export const apiLogout = (): void => {
  localStorage.removeItem("educreate-access-token");
};

export const apiListMaterials = (): Promise<Material[]> =>
  apiFetch<Material[]>("/materials");

export const apiDeleteMaterial = (materialId: string): Promise<void> =>
  apiFetch<void>(`/materials/${materialId}`, { method: "DELETE" });

export const apiGetMaterialChunks = (materialId: string): Promise<MaterialChunk[]> =>
  apiFetch<MaterialChunk[]>(`/materials/${materialId}/chunks`);

// ── GPS 澄清 ─────────────────────────────────────────────────────────────────

/** 首次澄清（单轮） */
export const apiClarify = (
  query: string,
  materials: string[],
  lessonId?: string,
  sessionId?: string,
  messages?: ChatMessage[],
): Promise<ClarifyResponse> =>
  apiFetch<ClarifyResponse>("/gps/clarify", {
    method: "POST",
    body: JSON.stringify({
      query,
      materials,
      lesson_id: lessonId ?? null,
      session_id: sessionId ?? null,
      messages: messages ?? null,
    }),
  });

/** 多轮澄清（带对话历史） */
export const apiClarifyWithHistory = (
  messages: ChatMessage[],
  materials: string[],
  lessonId?: string,
  sessionId?: string,
): Promise<ClarifyResponse> =>
  apiFetch<ClarifyResponse>("/gps/clarify", {
    method: "POST",
    body: JSON.stringify({
      messages,
      materials,
      lesson_id: lessonId ?? null,
      session_id: sessionId ?? null,
    }),
  });

/** 获取 GPS 固定槽位定义 */
export const apiGetGpsSlots = (): Promise<Record<string, string>> =>
  apiFetch<Record<string, string>>("/gps/slots");

// ── Lesson / LessonIR ─────────────────────────────────────────────────────────

/** 创建 lesson workspace */
export const apiCreateLesson = (body: {
  title: string;
  subject?: string;
  grade?: string;
  topic?: string;
}): Promise<Lesson> =>
  apiFetch<Lesson>("/lessons", {
    method: "POST",
    body: JSON.stringify(body),
  });

/** 列出 lesson workspaces */
export const apiListLessons = (): Promise<Lesson[]> =>
  apiFetch<Lesson[]>("/lessons");

/** 获取 lesson 详情 */
export const apiGetLesson = (lessonId: string): Promise<Lesson> =>
  apiFetch<Lesson>(`/lessons/${lessonId}`);

/** 创建或更新 LessonIR（生成新版本） */
export const apiUpsertLessonIR = (body: LessonIRCreate): Promise<LessonIR> =>
  apiFetch<LessonIR>(`/lessons/${body.lesson_id}/ir`, {
    method: "POST",
    body: JSON.stringify(body),
  });

/** 获取当前最新版 LessonIR */
export const apiGetCurrentLessonIR = (lessonId: string): Promise<LessonIR> =>
  apiFetch<LessonIR>(`/lessons/${lessonId}/ir`);

/** 获取 LessonIR 所有版本 */
export const apiListLessonIRVersions = (
  lessonId: string,
): Promise<{ lesson_id: string; versions: LessonIR[] }> =>
  apiFetch<{ lesson_id: string; versions: LessonIR[] }>(
    `/lessons/${lessonId}/ir/versions`,
  );

/** 绑定参考资料到 lesson */
export const apiBindMaterial = (
  lessonId: string,
  materialId: string,
): Promise<{ status: string; lesson_id: string; material_id: string }> =>
  apiFetch<{ status: string; lesson_id: string; material_id: string }>(
    `/lessons/${lessonId}/materials/${materialId}/bind`,
    { method: "POST" },
  );

/** 列出 lesson 绑定的参考资料 */
export const apiListBoundMaterials = (
  lessonId: string,
): Promise<{ material_id: string; filename: string; status: string; chunk_count: number }[]> =>
  apiFetch(`/lessons/${lessonId}/materials`);

// ── PPT 大纲 ─────────────────────────────────────────────────────────────────

export const apiGenerateOutline = (gpsResult: GpsClarifyResult): Promise<Outline> =>
  apiFetch<Outline>("/lessons/outline", {
    method: "POST",
    body: JSON.stringify(gpsResult),
  });

// ── 导出 ─────────────────────────────────────────────────────────────────────

export const apiExportPPTX = (outline: Outline): Promise<{ url: string }> =>
  apiFetch<{ url: string }>("/exports/pptx", {
    method: "POST",
    body: JSON.stringify(outline),
  });

export const apiExportDOCX = (outline: Outline): Promise<{ url: string }> =>
  apiFetch<{ url: string }>("/exports/docx", {
    method: "POST",
    body: JSON.stringify(outline),
  });

// ── GPS DAG ────────────────────────────────────────────────────────────────────

/** 获取澄清会话的 DAG 可视化数据 */
export const apiGetSessionDag = (sessionId: string): Promise<DagGraph> =>
  apiFetch<DagGraph>(`/gps/session/${sessionId}/dag`);

/** 重置澄清会话（清空对话历史） */
export const apiResetGpsSession = (sessionId: string): Promise<{ status: string; session_id: string }> =>
  apiFetch<{ status: string; session_id: string }>(`/gps/session/${sessionId}/reset`, {
    method: "POST",
  });

/** 删除澄清会话 */
export const apiDeleteGpsSession = (sessionId: string): Promise<{ status: string; session_id: string }> =>
  apiFetch<{ status: string; session_id: string }>(`/gps/session/${sessionId}`, {
    method: "DELETE",
  });

// ── 质检 ─────────────────────────────────────────────────────────────────────

export const apiQualityCheck = (outline: Outline): Promise<QualityReport> =>
  apiFetch<QualityReport>("/quality/check", {
    method: "POST",
    body: JSON.stringify(outline),
  });
