// stores/workflow.ts — 备课流程全局状态（Zustand）
import { create } from "zustand";
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
  addMaterial: (m: Material) => void;
  clearMaterials: () => void;

  // GPS 澄清
  gpsResult: GpsClarifyResult | null;
  setGpsResult: (r: GpsClarifyResult | null) => void;

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

export const useWorkflowStore = create<WorkflowState>((set) => ({
  currentStep: "upload",
  setCurrentStep: (step) => set({ currentStep: step }),

  materials: [],
  addMaterial: (m) =>
    set((s) => ({ materials: [...s.materials, m] })),
  clearMaterials: () => set({ materials: [] }),

  gpsResult: null,
  setGpsResult: (r) => set({ gpsResult: r }),

  outline: null,
  setOutline: (o) => set({ outline: o }),

  qualityReport: null,
  setQualityReport: (r) => set({ qualityReport: r }),

  loading: false,
  setLoading: (v) => set({ loading: v }),

  error: null,
  setError: (e) => set({ error: e }),
}));
