// services/api.ts — 前端 API 客户端
// 比赛版主线：上传 -> GPS澄清 -> 生成大纲 -> PPTX预览 -> 质检
// LessonIR 数据契约统一：GPS 澄清结果通过 GpsClarifyResult 承载，LessonIR 由后端管理版本

export interface Material {
  file_id: string;
  filename: string;
  status: "uploaded" | "parsing" | "parsed" | "failed" | "queued" | "cancelling" | "cancelled" | "error";
  mime?: string;
  extension?: string;
  size?: number;
  chunk_count?: number;
  parse_progress?: number;
  can_cancel?: boolean;
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

export type PptEditAction =
  | { type: "move_section"; section_id: string; to_index: number }
  | { type: "rename_section"; section_id: string; title: string }
  | { type: "replace_bullet"; section_id: string; bullet_index: number; text: string }
  | { type: "append_bullet"; section_id: string; text: string }
  | { type: "remove_bullet"; section_id: string; bullet_index: number }
  | { type: "set_style"; style: "classic" | "modern" | "minimal" };

export type InteractionType = "choice" | "true_false" | "fill_blank";

export interface InteractiveItem {
  id: string;
  type: InteractionType;
  prompt: string;
  options: string[];
  answer: string;
  explanation: string;
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

export interface GenerationJob {
  job_id: string;
  lesson_id: string;
  job_type: "pptx";
  status: "queued" | "generating" | "completed" | "failed";
  progress: number;
  task_id?: string | null;
  output?: {
    url: string;
    filename: string;
    artifact_id?: string | null;
    version?: number | null;
    warnings?: string[];
  } | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
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

/** 订阅材料解析 SSE；调用方可保留现有轮询作为降级。 */
export const apiSubscribeMaterialEvents = (
  materialId: string,
  onUpdate: (material: Material) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void,
): AbortController => {
  const controller = new AbortController();
  void (async () => {
    try {
      const token = localStorage.getItem("educreate-access-token");
      const response = await fetch(`${API_BASE}/materials/${materialId}/events`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        signal: controller.signal,
      });
      if (!response.ok || !response.body) throw new Error(`SSE HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!controller.signal.aborted) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";
        for (const block of blocks) {
          const line = block.split("\n").find((item) => item.startsWith("data: "));
          if (!line) continue;
          const material = JSON.parse(line.slice(6)) as Material;
          onUpdate(material);
          if (["parsed", "uploaded", "failed", "cancelled", "error"].includes(material.status)) {
            onComplete?.();
            controller.abort();
            break;
          }
        }
      }
    } catch (error: unknown) {
      if (!controller.signal.aborted) onError?.(error instanceof Error ? error : new Error(String(error)));
    }
  })();
  return controller;
};

export const apiGetMaterial = (materialId: string): Promise<Material> =>
  apiFetch<Material>(`/materials/${materialId}`);

export const apiDeleteMaterial = (materialId: string): Promise<void> =>
  apiFetch<void>(`/materials/${materialId}`, { method: "DELETE" });

export const apiGetMaterialChunks = (materialId: string): Promise<MaterialChunk[]> =>
  apiFetch<MaterialChunk[]>(`/materials/${materialId}/chunks`);

export const apiCancelMaterialParse = (materialId: string): Promise<Material> =>
  apiFetch<Material>(`/materials/${materialId}/cancel`, { method: "POST" });

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

export const apiApplyPptActions = (body: {
  outline: Outline;
  actions: PptEditAction[];
  lesson_id?: string;
  instruction?: string;
}): Promise<{ outline: Outline; applied: Record<string, unknown>[]; warnings: string[]; edit_request_id?: string | null }> =>
  apiFetch("/pptagent/apply-actions", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const apiRewritePptInstruction = (body: {
  outline: Outline;
  instruction: string;
}): Promise<{
  actions: PptEditAction[];
  warnings: string[];
  confidence: number;
  explanation: string;
}> => apiFetch("/pptagent/rewrite-instruction", {
  method: "POST",
  body: JSON.stringify(body),
});

export const apiAnalyzePptReference = (materialId: string): Promise<{
  material_id: string;
  filename: string;
  slide_count: number;
  average_characters: number;
  density: string;
  recommended_style: "classic" | "modern" | "minimal";
}> => apiFetch("/pptagent/analyze-reference", {
  method: "POST",
  body: JSON.stringify({ material_id: materialId }),
});

export const apiGenerateInteractive = (body: {
  outline: Outline;
  interaction_type: InteractionType;
  count: number;
  section_id?: string;
}): Promise<{
  interaction_type: InteractionType;
  items: InteractiveItem[];
  html: string;
  warnings: string[];
}> => apiFetch("/interactive/generate", {
  method: "POST",
  body: JSON.stringify(body),
});

export const apiExportPPTX = (
  outline: Outline,
  options?: { lesson_id?: string; actions?: PptEditAction[] },
): Promise<{ url: string; artifact_id?: string | null; version?: number | null; warnings?: string[] }> =>
  apiFetch("/exports/pptx", {
    method: "POST",
    body: JSON.stringify({ ...outline, ...options }),
  });

export const apiExportDOCX = (outline: Outline): Promise<{ url: string }> =>
  apiFetch<{ url: string }>("/exports/docx", {
    method: "POST",
    body: JSON.stringify(outline),
  });

export const apiCreatePptxJob = (
  outline: Outline,
  lessonId: string,
  actions: PptEditAction[] = [],
): Promise<GenerationJob> => apiFetch<GenerationJob>("/exports/pptx/jobs", {
  method: "POST",
  body: JSON.stringify({ ...outline, lesson_id: lessonId, actions }),
});

export const apiGetGenerationJob = (jobId: string): Promise<GenerationJob> =>
  apiFetch<GenerationJob>(`/exports/jobs/${jobId}`);

/** Subscribe to PPTX generation events; callers retain REST polling fallback. */
export const apiSubscribeGenerationJob = (
  jobId: string,
  onUpdate: (job: GenerationJob) => void,
  onError?: (error: Error) => void,
): AbortController => {
  const controller = new AbortController();
  void (async () => {
    try {
      const token = localStorage.getItem("educreate-access-token");
      const response = await fetch(`${API_BASE}/exports/jobs/${jobId}/events`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`SSE 连接失败：HTTP ${response.status}`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const data = block.split("\n").find((line) => line.startsWith("data: "));
          if (data) onUpdate(JSON.parse(data.slice(6)) as GenerationJob);
          boundary = buffer.indexOf("\n\n");
        }
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        onError?.(error instanceof Error ? error : new Error(String(error)));
      }
    }
  })();
  return controller;
};

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
