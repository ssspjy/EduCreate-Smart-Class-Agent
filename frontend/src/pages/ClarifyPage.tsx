// pages/ClarifyPage.tsx — 步骤 2：GPS 教学意图澄清
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Input,
  List,
  Tag,
  Typography,
  Space,
  Divider,
  message,
  Steps,
  Alert,
  Collapse,
  Badge,
  Spin,
} from "antd";
import { SendOutlined, LeftOutlined, RightOutlined, NodeIndexOutlined, ReloadOutlined } from "@ant-design/icons";
import { useWorkflowStore } from "../stores/workflow";
import {
  apiClarify,
  apiCreateLesson,
  apiGetSessionDag,
  apiResetGpsSession,
  type ClarifyResponse,
  type DagGraph,
  type ChatMessage,
} from "../services/api";
import { GpsDag } from "../flow";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

// 难度标签颜色
const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "green",
  medium: "orange",
  hard: "red",
};

// 风格标签颜色
const STYLE_TAG_MAP: Record<string, string> = {
  theory: "blue",
  interactive: "cyan",
  experiment: "purple",
};

interface ClarifyPageState {
  query: string;
  loading: boolean;
  history: ChatMessage[];
  dagData: DagGraph | null;
  dagLoading: boolean;
  dagError: string | null;
  dagExpanded: boolean;   // DAG 面板是否展开
}

export default function ClarifyPage() {
  const {
    materials,
    gpsResult,
    setGpsResult,
    setCurrentStep,
    lessonId,
    setLessonId,
    gpsSessionId,
    setGpsSessionId,
  } = useWorkflowStore();

  const [state, setState] = useState<ClarifyPageState>({
    query: "",
    loading: false,
    history: [],
    dagData: null,
    dagLoading: false,
    dagError: null,
    dagExpanded: true,
  });

  const navigate = useNavigate();
  const dagFetchController = useRef<AbortController | null>(null);

  // ── 步骤索引（Steps 组件） ──────────────────────────────────────────────────
  const stepsItems = [
    { title: "上传材料" },
    { title: "意图澄清" },
    { title: "大纲生成" },
    { title: "预览" },
    { title: "质检" },
  ];

  // 当前步骤：已有 GPS 结果时高亮到步骤 2，否则高亮到当前对话轮次
  const currentStepIndex = gpsResult
    ? 1   // "意图澄清" 已完成
    : state.history.length; // 对话轮次作为进度

  // ── 获取 DAG 数据 ────────────────────────────────────────────────────────────
  const fetchDag = useCallback(async (sessionId: string) => {
    if (dagFetchController.current) {
      dagFetchController.current.abort();
    }
    const controller = new AbortController();
    dagFetchController.current = controller;

    setState((s) => ({ ...s, dagLoading: true, dagError: null }));
    try {
      const data = await apiGetSessionDag(sessionId);
      if (!controller.signal.aborted) {
        setState((s) => ({ ...s, dagData: data, dagLoading: false }));
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        const msg = err instanceof Error ? err.message : "获取 DAG 失败";
        setState((s) => ({ ...s, dagError: msg, dagLoading: false }));
      }
    }
  }, []);

  // sessionId 变化时自动获取 DAG
  useEffect(() => {
    if (gpsSessionId) {
      fetchDag(gpsSessionId);
      // 每 5 秒刷新一次 DAG（多轮对话场景）
      const interval = setInterval(() => fetchDag(gpsSessionId), 5000);
      return () => {
        clearInterval(interval);
        if (dagFetchController.current) {
          dagFetchController.current.abort();
        }
      };
    }
    return undefined;
  }, [gpsSessionId, fetchDag]);

  // ── 提交澄清 ──────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!state.query.trim()) return;

    const userMsg: ChatMessage = { role: "user", content: state.query };

    // 乐观更新：先显示用户消息
    setState((s) => ({
      ...s,
      history: [...s.history, userMsg],
      query: "",
      loading: true,
    }));

    try {
      // 确保 lesson workspace 存在
      let currentLessonId = lessonId;
      if (!currentLessonId) {
        const lesson = await apiCreateLesson({ title: `教案-${Date.now()}` });
        setLessonId(lesson.id);
        currentLessonId = lesson.id;
      }

      const resp: ClarifyResponse = await apiClarify(
        state.query,
        materials.map((m) => m.file_id),
        currentLessonId ?? undefined,
        gpsSessionId ?? undefined,
        state.history as ChatMessage[],
      );

      // 更新 GPS 结果
      setGpsResult(resp.result);

      // 保存 sessionId（首次澄清后）
      if (resp.session_id) {
        setGpsSessionId(resp.session_id);
      }

      // 构造助手回复
      const summaryParts: string[] = [];
      if (resp.result.subject) summaryParts.push(resp.result.subject);
      if (resp.result.grade) summaryParts.push(resp.result.grade);
      if (resp.result.topic) summaryParts.push(resp.result.topic);

      const assistantMsgs: ChatMessage[] = [];

      // 始终显示结构化摘要
      assistantMsgs.push({
        role: "assistant",
        content: `已解析：${summaryParts.join(" · ") || "（信息不足）"}`,
      });

      // 追问建议单独显示
      if (resp.needs_more_info && resp.suggestion) {
        assistantMsgs.push({
          role: "assistant",
          content: resp.suggestion,
        });
      }

      setState((s) => ({
        ...s,
        history: [...s.history, userMsg, ...assistantMsgs],
        loading: false,
      }));

      // 立即刷新 DAG（对话后立刻更新可视化）
      if (resp.session_id) {
        fetchDag(resp.session_id);
      }

    } catch (err) {
      const errMsg = err instanceof Error ? err.message : "澄清失败，请重试";
      message.error(errMsg);
      // 撤销乐观更新：移除刚才添加的用户消息
      setState((s) => ({
        ...s,
        history: s.history.slice(0, -1),
        query: state.query,
        loading: false,
      }));
    }
  };

  // ── 重置澄清 ──────────────────────────────────────────────────────────────
  const handleReset = async () => {
    if (!gpsSessionId) return;
    try {
      await apiResetGpsSession(gpsSessionId);
      setGpsResult(null);
      setState((s) => ({
        ...s,
        history: [],
        dagData: null,
        dagExpanded: true,
      }));
      message.success("已重置澄清会话，可以重新开始");
    } catch {
      message.error("重置失败");
    }
  };

  // ── 导航 ─────────────────────────────────────────────────────────────────
  const goToStep = (step: "upload" | "outline", path: string) => {
    setCurrentStep(step);
    navigate(path);
  };

  const canProceed = Boolean(gpsResult?.subject && gpsResult?.grade && gpsResult?.topic);

  return (
    <div className="page">
      <Title level={3}>步骤 2 / 5：教学意图澄清（GPS）</Title>
      <Text type="secondary">
        描述您的教学目标，系统通过多轮对话帮您结构化提取：科目、年级、知识点、能力目标。
      </Text>

      <Steps
        current={currentStepIndex}
        style={{ marginTop: 16, marginBottom: 16 }}
        items={stepsItems}
      />

      {/* ── DAG 可视化面板 ──────────────────────────────────────────────── */}
      <Collapse
        activeKey={state.dagExpanded ? ["dag"] : []}
        onChange={(keys) => setState((s) => ({ ...s, dagExpanded: keys.includes("dag") }))}
        style={{ marginBottom: 16 }}
      >
        <Panel
          header={
            <Space>
              <NodeIndexOutlined />
              <Text strong>GPS 意图结构图</Text>
              {state.dagData?.meta && (
                <Badge
                  status={state.dagData.meta.completion >= 1 ? "success" : "processing"}
                  text={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      完成度 {Math.round(state.dagData.meta.completion * 100)}%
                    </Text>
                  }
                />
              )}
            </Space>
          }
          key="dag"
        >
          {state.dagLoading ? (
            <div style={{ textAlign: "center", padding: "40px 0" }}>
              <Spin size="small" />
              <Text type="secondary" style={{ marginLeft: 8 }}>加载中…</Text>
            </div>
          ) : state.dagError ? (
            <Alert type="warning" message={state.dagError} showIcon />
          ) : (
            <GpsDag
              dagData={state.dagData ?? { nodes: [], edges: [], meta: { filled_count: 0, missing_count: 10, total_slots: 10, completion: 0, dialogue_count: 0, dialogue_collapsed: false } }}
              height={360}
            />
          )}
          {gpsSessionId && (
            <Button
              type="text"
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => fetchDag(gpsSessionId)}
              style={{ marginTop: 8 }}
            >
              刷新 DAG
            </Button>
          )}
        </Panel>
      </Collapse>

      {/* ── 对话历史 ──────────────────────────────────────────────────────── */}
      {state.history.length > 0 && (
        <List
          style={{ marginBottom: 16, maxHeight: 280, overflowY: "auto" }}
          dataSource={state.history}
          renderItem={(msg, idx) => (
            <List.Item
              style={{
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                border: "none",
                padding: "4px 0",
              }}
            >
              <Card
                size="small"
                style={{
                  maxWidth: "75%",
                  background: msg.role === "user" ? "#1890ff" : "#f5f5f5",
                  color: msg.role === "user" ? "#fff" : "#000",
                  border: msg.role === "assistant" && idx > 0 && state.history[idx - 1]?.role !== "assistant"
                    ? "2px solid #87e8de"
                    : undefined,
                }}
              >
                <Paragraph style={{ color: "inherit", margin: 0, whiteSpace: "pre-wrap" }}>
                  {msg.content}
                </Paragraph>
              </Card>
            </List.Item>
          )}
        />
      )}

      {/* ── GPS 结构化结果预览 ──────────────────────────────────────────── */}
      {gpsResult && (
        <>
          <Divider orientation="left">结构化提取结果</Divider>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space wrap>
              {gpsResult.subject && (
                <Tag color="blue">{gpsResult.subject}</Tag>
              )}
              {gpsResult.grade && (
                <Tag color="green">{gpsResult.grade}</Tag>
              )}
              {gpsResult.difficulty && (
                <Tag color={DIFFICULTY_COLOR[gpsResult.difficulty] || "default"}>
                  {gpsResult.difficulty}
                </Tag>
              )}
              {gpsResult.style && (
                <Tag color={STYLE_TAG_MAP[gpsResult.style] || "default"}>
                  {gpsResult.style === "theory" ? "理论" :
                    gpsResult.style === "interactive" ? "互动" :
                      gpsResult.style === "experiment" ? "实验" : gpsResult.style}
                </Tag>
              )}
            </Space>

            {gpsResult.topic && (
              <Paragraph strong style={{ marginTop: 8, marginBottom: 4 }}>
                课题：{gpsResult.topic}
              </Paragraph>
            )}

            {gpsResult.objectives.length > 0 && (
              <Paragraph style={{ marginBottom: 4 }}>
                <Text strong>学习目标：</Text>
                {gpsResult.objectives.join("；")}
              </Paragraph>
            )}

            {gpsResult.key_points.length > 0 && (
              <Paragraph style={{ marginBottom: 0 }}>
                <Text strong>教学重点：</Text>
                {gpsResult.key_points.join("；")}
              </Paragraph>
            )}

            {/* 置信度指示 */}
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                置信度：
              </Text>
              <Tag color={gpsResult.confidence >= 0.8 ? "success" : gpsResult.confidence >= 0.5 ? "warning" : "error"}>
                {Math.round(gpsResult.confidence * 100)}%
              </Tag>
            </div>
          </Card>
        </>
      )}

      {/* ── 输入框 ─────────────────────────────────────────────────────── */}
      <TextArea
        placeholder="例如：我想讲一节初中物理的浮力课，重点讲阿基米德原理，学生基础一般……"
        value={state.query}
        onChange={(e) => setState((s) => ({ ...s, query: e.target.value }))}
        onPressEnter={(e) => !e.shiftKey && (e.preventDefault(), handleSubmit())}
        rows={3}
        style={{ marginTop: 8 }}
      />

      <Space style={{ marginTop: 8 }}>
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSubmit}
          loading={state.loading}
          disabled={!state.query.trim()}
        >
          发送
        </Button>
        {gpsSessionId && (
          <Button
            icon={<ReloadOutlined />}
            onClick={handleReset}
            danger
          >
            重置澄清
          </Button>
        )}
      </Space>

      <Divider />

      {/* ── 底部导航 ─────────────────────────────────────────────────────── */}
      <Space>
        <Button
          icon={<LeftOutlined />}
          onClick={() => goToStep("upload", "/upload")}
        >
          上一步
        </Button>
        <Button
          type="primary"
          icon={<RightOutlined />}
          disabled={!canProceed}
          onClick={() => goToStep("outline", "/outline")}
        >
          下一步：生成大纲
        </Button>
      </Space>
    </div>
  );
}
