// App.tsx — 师创智课教师工作台入口
import { Routes, Route, Navigate, Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import { Button, Spin } from "antd";
import "./App.css";
import UploadPage from "./pages/UploadPage";
import ClarifyPage from "./pages/ClarifyPage";
import OutlinePage from "./pages/OutlinePage";
import PreviewPage from "./pages/PreviewPage";
import QualityPage from "./pages/QualityPage";
import { useWorkflowStore } from "./stores/workflow";
import LoginPage from "./pages/LoginPage";
import { apiGetCurrentUser, apiLogout } from "./services/api";

function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let active = true;
    apiGetCurrentUser()
      .then(() => {
        if (active) setChecking(false);
      })
      .catch(() => {
        if (active) {
          navigate("/login", { replace: true, state: { from: location } });
        }
      });
    return () => {
      active = false;
    };
  }, [location, navigate]);

  if (checking) {
    return <div className="page" style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}><Spin /></div>;
  }
  return <>{children}</>;
}

function Dashboard() {
  const { currentStep } = useWorkflowStore();
  const stepLabel = {
    upload: "上传资料",
    clarify: "意图澄清",
    outline: "大纲生成",
    preview: "预览导出",
    quality: "质量检测",
  }[currentStep];

  return (
    <div className="page">
      <h1>师创智课 · 教师工作台</h1>
      <p className="subtitle">教师从"事务型"工作者转向"设计型"导师。</p>
      <p className="subtitle" style={{ marginTop: 8, color: "#888", fontSize: 14 }}>
        当前步骤：{stepLabel} · 上传 → 意图澄清 → 大纲生成 → 预览导出 → 质量检测
      </p>
      <nav className="nav">
        <Link to="/upload">课程共创</Link>
        <Link to="/quality">质量中心</Link>
        <Link to="/health">健康检查</Link>
        <Button
          type="link"
          onClick={() => {
            apiLogout();
            window.location.href = "/login";
          }}
        >
          退出登录
        </Button>
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
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/upload" element={<RequireAuth><UploadPage /></RequireAuth>} />
      <Route path="/clarify" element={<RequireAuth><ClarifyPage /></RequireAuth>} />
      <Route path="/outline" element={<RequireAuth><OutlinePage /></RequireAuth>} />
      <Route path="/preview" element={<RequireAuth><PreviewPage /></RequireAuth>} />
      <Route path="/quality" element={<RequireAuth><QualityPage /></RequireAuth>} />
      <Route path="/health" element={<RequireAuth><HealthPage /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
