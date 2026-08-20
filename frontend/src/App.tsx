// App.tsx — 师创智课教师工作台入口
import { Routes, Route, Navigate } from "react-router-dom";
import "./App.css";
import UploadPage from "./pages/UploadPage";
import ClarifyPage from "./pages/ClarifyPage";
import OutlinePage from "./pages/OutlinePage";
import PreviewPage from "./pages/PreviewPage";
import QualityPage from "./pages/QualityPage";
import { useWorkflowStore } from "./stores/workflow";

function Dashboard() {
  const { currentStep } = useWorkflowStore();
  return (
    <div className="page">
      <h1>师创智课 · 教师工作台</h1>
      <p className="subtitle">教师从"事务型"工作者转向"设计型"导师。</p>
      <p className="subtitle" style={{ marginTop: 8, color: "#888", fontSize: 14 }}>
        当前流程：上传 → 意图澄清 → 大纲生成 → 预览导出 → 质量检测
      </p>
      <nav className="nav">
        <a href="/upload">课程共创</a>
        <a href="/quality">质量中心</a>
        <a href="/health">健康检查</a>
      </nav>
    </div>
  );
}

function HealthPage() {
  return (
    <div className="page">
      <h1>后端连接测试</h1>
      <p>访问 <code>/api/v1/lessons</code> 验证联调。</p>
      <button
        onClick={async () => {
          const r = await fetch("/api/v1/lessons");
          const data = await r.json();
          alert(`后端响应：${JSON.stringify(data)}`);
        }}
      >
        测试后端
      </button>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/clarify" element={<ClarifyPage />} />
      <Route path="/outline" element={<OutlinePage />} />
      <Route path="/preview" element={<PreviewPage />} />
      <Route path="/quality" element={<QualityPage />} />
      <Route path="/health" element={<HealthPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
