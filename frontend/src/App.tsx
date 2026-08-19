import { Routes, Route, Link } from "react-router-dom";
import "./App.css";

function Dashboard() {
  return (
    <div className="page">
      <h1>师创智课 · 教师工作台</h1>
      <p className="subtitle">教师从"事务型"工作者转向"设计型"导师。</p>
      <nav className="nav">
        <Link to="/courses">课程空间</Link>
        <Link to="/co-create">AI 共创</Link>
        <Link to="/quality">质量中心</Link>
        <Link to="/health">健康检查</Link>
      </nav>
    </div>
  );
}

function CoursesPage() {
  return <div className="page"><h1>课程空间</h1><p>占位</p></div>;
}

function CoCreatePage() {
  return <div className="page"><h1>AI 共创</h1><p>占位</p></div>;
}

function QualityPage() {
  return <div className="page"><h1>质量中心</h1><p>占位</p></div>;
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
      <Route path="/courses" element={<CoursesPage />} />
      <Route path="/co-create" element={<CoCreatePage />} />
      <Route path="/quality" element={<QualityPage />} />
      <Route path="/health" element={<HealthPage />} />
    </Routes>
  );
}