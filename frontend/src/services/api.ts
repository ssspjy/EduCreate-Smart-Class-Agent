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
  error_message?: string | null;
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
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── 参考资料 ──────────────────────────────────────────────────────────────────

export const apiUploadMaterial = (file: File): Promise<Material> => {
  const form = new FormData();
  form.append("file", file);
  return fetch(`${API_BASE}/materials/upload`, { method: "POST", body: form }).then(
    async (r) => {
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      return r.json() as Promise<Material>;
    }
  );
};

export const apiListMaterials = (): Promise<Material[]> =>
  apiFetch<Material[]>("/materials");

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

// ── 质检 ─────────────────────────────────────────────────────────────────────

export const apiQualityCheck = (outline: Outline): Promise<QualityReport> =>
  apiFetch<QualityReport>("/quality/check", {
    method: "POST",
    body: JSON.stringify(outline),
  });
