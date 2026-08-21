// stores/workflow.ts — 备课流程全局状态（Zustand）
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  GpsClarifyResult,
  Outline,
  Material,
  QualityReport,
} from "../services/api";

export type Step =
  | "upload"
  | "clarify"
  | "outline"
  | "preview"
  | "quality";

interface WorkflowState {
  // 当前步
  currentStep: Step;
  setCurrentStep: (step: Step) => void;

  // 参考资料
  materials: Material[];
  setMaterials: (materials: Material[]) => void;
  addMaterial: (m: Material) => void;
  removeMaterial: (fileId: string) => void;
  clearMaterials: () => void;

  // GPS 澄清
  gpsResult: GpsClarifyResult | null;
  setGpsResult: (r: GpsClarifyResult | null) => void;

  // 当前 lesson workspace ID（整个流程绑定同一个 lesson）
  lessonId: string | null;
  setLessonId: (id: string | null) => void;

  // GPS 多轮会话 ID（用于跨请求追踪同一轮澄清上下文）
  gpsSessionId: string | null;
  setGpsSessionId: (id: string | null) => void;

  // PPT 大纲
  outline: Outline | null;
  setOutline: (o: Outline | null) => void;

  // 质检报告
  qualityReport: QualityReport | null;
  setQualityReport: (r: QualityReport | null) => void;

  // 全局加载态
  loading: boolean;
  setLoading: (v: boolean) => void;

  // 全局错误
  error: string | null;
  setError: (e: string | null) => void;
}

export const useWorkflowStore = create<WorkflowState>()(persist((set) => ({
  currentStep: "upload",
  setCurrentStep: (step) => set({ currentStep: step }),

  materials: [],
  setMaterials: (materials) => set({ materials }),
  addMaterial: (m) =>
    set((s) => ({
      materials: [...s.materials.filter((item) => item.file_id !== m.file_id), m],
    })),
  removeMaterial: (fileId) =>
    set((s) => ({ materials: s.materials.filter((m) => m.file_id !== fileId) })),
  clearMaterials: () => set({ materials: [] }),

  gpsResult: null,
  setGpsResult: (r) => set({ gpsResult: r }),

  lessonId: null,
  setLessonId: (id) => set({ lessonId: id }),

  gpsSessionId: null,
  setGpsSessionId: (id) => set({ gpsSessionId: id }),

  outline: null,
  setOutline: (o) => set({ outline: o }),

  qualityReport: null,
  setQualityReport: (r) => set({ qualityReport: r }),

  loading: false,
  setLoading: (v) => set({ loading: v }),

  error: null,
  setError: (e) => set({ error: e }),
}), {
  name: "educreate-workflow",
  partialize: (state) => ({
    currentStep: state.currentStep,
    materials: state.materials,
    gpsResult: state.gpsResult,
    lessonId: state.lessonId,
    gpsSessionId: state.gpsSessionId,
    outline: state.outline,
    qualityReport: state.qualityReport,
  }),
}));
