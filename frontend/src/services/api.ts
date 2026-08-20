// services/api.ts — 前端 API 客户端（Axios + TanStack Query 兼容）
// 比赛版主线：上传 -> GPS澄清 -> 生成大纲 -> PPTX预览 -> 质检

export interface Material {
  file_id: string;
  filename: string;
  status: "queued" | "parsed" | "error";
}

export interface GpsClarifyResult {
  subject: string;
  grade: string;
  topic: string;
  objectives: string[];
  key_points: string[];
  difficulty: "easy" | "medium" | "hard";
}

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
  score: number;           // 0-100
  clarity: number;          // 0-10
  coverage: number;         // 0-10
  engagement: number;       // 0-10
  suggestions: string[];
}

// --- API 调用 ---

const BASE = "/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
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

// 参考资料
export const apiUploadMaterial = (file: File): Promise<Material> => {
  const form = new FormData();
  form.append("file", file);
  return fetch(`${BASE}/materials/upload`, { method: "POST", body: form }).then(
    (r) => r.json() as Promise<Material>
  );
};

export const apiListMaterials = (): Promise<Material[]> =>
  apiFetch<Material[]>("/materials");

// GPS 澄清
export const apiClarify = (query: string, materials: string[]): Promise<GpsClarifyResult> =>
  apiFetch<GpsClarifyResult>("/gps/clarify", {
    method: "POST",
    body: JSON.stringify({ query, materials }),
  });

export const apiClarifyWithHistory = (
  messages: { role: "user" | "assistant"; content: string }[],
  materials: string[]
): Promise<GpsClarifyResult> =>
  apiFetch<GpsClarifyResult>("/gps/clarify", {
    method: "POST",
    body: JSON.stringify({ messages, materials }),
  });

// PPT 大纲生成
export const apiGenerateOutline = (gpsResult: GpsClarifyResult): Promise<Outline> =>
  apiFetch<Outline>("/lessons/outline", {
    method: "POST",
    body: JSON.stringify(gpsResult),
  });

// PPT 导出（返回 base64 或 URL）
export const apiExportPPTX = (outline: Outline): Promise<{ url: string }> =>
  apiFetch<{ url: string }>("/exports/pptx", {
    method: "POST",
    body: JSON.stringify(outline),
  });

// 质检
export const apiQualityCheck = (outline: Outline): Promise<QualityReport> =>
  apiFetch<QualityReport>("/quality/check", {
    method: "POST",
    body: JSON.stringify(outline),
  });
