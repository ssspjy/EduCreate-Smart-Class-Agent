// pages/ClarifyPage.tsx — GPS 意图澄清页
// 左侧：React Flow DAG 可视化（GpsDag 组件）
// 右侧上半：多轮对话 Chat
// 右侧下半：GPS 槽位状态卡片
// 底部：操作区（跳过 / 生成大纲 / 重置）

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Empty, Input, message, Space, Spin, Tag, Typography } from "antd";
import { SendOutlined, SyncOutlined, ArrowRightOutlined } from "@ant-design/icons";
import GpsDag from "../flow/GpsDag";
import type {
  ChatMessage,
  ClarifyResponse,
  DagGraph,
  GpsClarifyResult,
  MissingSlot,
} from "../services/api";
import { apiClarify, apiClarifyWithHistory, apiGetSessionDag } from "../services/api";
import { useWorkflowStore } from "../stores/workflow";

const { Text, Title } = Typography;
const { TextArea } = Input;

const SLOT_DISPLAY: Record<string, string> = {
  subject: "科目",
  grade: "年级",
  topic: "课题",
  objectives: "学习目标",
  key_points: "教学重点",
};

// ── Chat bubble ─────────────────────────────────────────────────────────────────

interface BubbleProps {
  role: "user" | "assistant" | "system";
  content: string;
}

function Bubble({ role, content }: BubbleProps) {
  const isUser = role === "user";
  return (
    <div style={{ textAlign: isUser ? "right" : "left", marginBottom: 12 }}>
      <div
        style={{
          display: "inline-block",
          maxWidth: "80%",
          padding: "10px 14px",
          borderRadius: 12,
          background: isUser ? "#1890ff" : "#f5f5f5",
          color: isUser ? "#fff" : "#1f2937",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        <Text style={{ color: "inherit", fontSize: 14 }}>{content}</Text>
      </div>
    </div>
  );
}

// ── Slot status tag ────────────────────────────────────────────────────────────

function SlotTag({ slot, value, missing }: { slot: string; value: string | string[]; missing: boolean }) {
  const displayName = SLOT_DISPLAY[slot] || slot;
  const displayValue = Array.isArray(value) ? value.join("；") : value;
  return (
    <Tag
      color={missing ? "default" : "green"}
      style={{ borderRadius: 6, fontSize: 13, padding: "2px 10px" }}
    >
      {missing ? `⏳ ${displayName}：待填写` : `✅ ${displayName}：${displayValue || "—"}`}
    </Tag>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function ClarifyPage() {
  const navigate = useNavigate();
  const {
    gpsSessionId,
    setGpsSessionId,
    gpsResult,
    setGpsResult,
    setCurrentStep,
    lessonId,
    materials,
  } = useWorkflowStore();

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [dagData, setDagData] = useState<DagGraph | null>(null);
  const [missingSlots, setMissingSlots] = useState<MissingSlot[]>([]);
  const [needsMore, setNeedsMore] = useState(true);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const materialIds = materials.map((m) => m.file_id);

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  }, []);

  // 刷新 DAG 数据
  // refreshDag 依赖说明：
  // 1. 无外部状态依赖，仅通过 sessionId 参数驱动；
  // 2. 不加进 useCallback 依赖数组，避免每次 render 都重新创建函数；
  // 3. sessionId 通过参数传入，总是引用最新值。
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const refreshDag = useCallback(async (sessionId: string) => {
    try {
      const dag = await apiGetSessionDag(sessionId);
      setDagData(dag);
    } catch (err) {
      console.warn("[ClarifyPage] DAG 刷新失败", err);
    }
  }, []);

  // 首次加载：恢复 session（如果 store 有 session_id）
  useEffect(() => {
    if (gpsSessionId) {
      refreshDag(gpsSessionId);
    }
  }, [gpsSessionId, refreshDag]);

  // 发送消息
  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    setInput("");
    setLoading(true);

    const userMsg: ChatMessage = { role: "user", content: trimmed };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    scrollToBottom();

    try {
      let resp: ClarifyResponse;
      if (messages.length === 0) {
        // 首次：传 query + 空 messages
        resp = await apiClarify(
          trimmed,
          materialIds,
          lessonId ?? undefined,
          gpsSessionId ?? undefined,
          undefined,
        );
      } else {
        // 多轮：传完整历史 + session_id
        resp = await apiClarifyWithHistory(
          newMessages,
          materialIds,
          lessonId ?? undefined,
          gpsSessionId ?? undefined,
        );
      }

      // 更新 session_id
      if (resp.session_id) {
        setGpsSessionId(resp.session_id);
      }

      // 更新 GPS 结果
      setGpsResult(resp.result);
      setMissingSlots(resp.missing_slots || []);
      setNeedsMore(resp.needs_more_info);

      // 添加助手回复
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: resp.suggestion || "好的，信息已记录。",
      };
      setMessages((prev) => [...prev, assistantMsg]);
      scrollToBottom();

      // 刷新 DAG
      if (resp.session_id) {
        refreshDag(resp.session_id);
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : String(err);
      message.error(`澄清失败：${errMsg}`);
      // 出错时回退 input
      setInput(trimmed);
    } finally {
      setLoading(false);
    }
  };

  // 跳过当前缺失槽位
  const handleSkipSlot = (slot: string) => {
    const slotName = SLOT_DISPLAY[slot] || slot;
    setMissingSlots((prev) => prev.filter((s) => s.slot !== slot));
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: `好的，已跳过「${slotName}」，继续收集其他信息。` },
    ]);
    scrollToBottom();
  };

  // 生成大纲（slot 已填满，或用户主动点击）
  const handleGenerateOutline = () => {
    if (!gpsResult) {
      message.warning("请先完成 GPS 澄清");
      return;
    }
    setCurrentStep("outline");
    navigate("/outline");
  };

  // 重置会话
  const handleReset = async () => {
    if (!gpsSessionId) {
      setMessages([]);
      setDagData(null);
      setMissingSlots([]);
      setGpsResult(null);
      return;
    }
    try {
      const { apiResetGpsSession } = await import("../services/api");
      const { session_id } = await apiResetGpsSession(gpsSessionId);
      setGpsSessionId(session_id);
      setMessages([]);
      setMissingSlots([]);
      setGpsResult(null);
      setNeedsMore(true);
      setDagData(null);
      message.success("会话已重置");
    } catch {
      message.error("重置失败");
    }
  };

  const result = gpsResult;
  const allSlots = ["subject", "grade", "topic", "objectives", "key_points"];
  const missingSet = new Set(missingSlots.map((s) => s.slot));

  // 进度百分比
  const hasValue = (value: unknown): boolean => {
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "string") return value.trim().length > 0;
    return value !== null && value !== undefined;
  };
  const filledCount = allSlots.filter((slot) => {
    if (missingSet.has(slot)) return false;
    return hasValue(result?.[slot as keyof GpsClarifyResult]);
  }).length;
  const progressPct = Math.round((filledCount / allSlots.length) * 100);

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", marginBottom: 16, gap: 12 }}>
        <Title level={4} style={{ margin: 0 }}>📋 GPS 意图澄清</Title>
        <Tag color={needsMore ? "orange" : "green"}>
          {needsMore ? `完成度 ${progressPct}%` : "✅ 信息已齐全"}
        </Tag>
        {gpsSessionId && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            会话 ID：{gpsSessionId}
          </Text>
        )}
      </div>

      <div style={{ display: "flex", gap: 16, height: "calc(100vh - 220px)" }}>
        {/* ── 左侧：React Flow DAG ──────────────────────────────── */}
        <div style={{ width: 360, flexShrink: 0 }}>
          <GpsDag
            dagData={dagData || { nodes: [], edges: [], meta: { filled_count: 0, missing_count: 5, total_slots: 5, completion: 0, dialogue_count: 0, dialogue_collapsed: false } }}
            highlightNew
            height="100%"
          />
        </div>

        {/* ── 右侧：对话 + 槽位状态 ────────────────────────────── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
          {/* 槽位状态卡片 */}
          <Card size="small" title="教学意图槽位" style={{ flexShrink: 0 }}>
            <Space wrap size={[4, 4]}>
              {allSlots.map((slot) => (
                <SlotTag
                  key={slot}
                  slot={slot}
                  value={(() => {
                    const rawValue = result?.[slot as keyof GpsClarifyResult];
                    if (Array.isArray(rawValue)) return rawValue;
                    if (typeof rawValue === "string") return rawValue;
                    return "";
                  })()}
                  missing={missingSet.has(slot)}
                />
              ))}
            </Space>
            {missingSlots.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  待补充：
                </Text>{" "}
                {missingSlots.map((s) => (
                  <Tag
                    key={s.slot}
                    color="orange"
                    style={{ cursor: "pointer", marginTop: 4 }}
                    onClick={() => handleSkipSlot(s.slot)}
                  >
                    跳过「{SLOT_DISPLAY[s.slot] || s.slot}」
                  </Tag>
                ))}
              </div>
            )}
          </Card>

          {/* Chat 区域 */}
          <Card
            size="small"
            title="对话记录"
            style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
            styles={{ body: { flex: 1, overflowY: "auto", padding: "12px 16px" } } as Record<string, unknown>}
          >
            {messages.length === 0 ? (
              <Empty
                description="开始对话，告诉我您想教什么课"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ) : (
              <>
                {messages.map((msg, idx) => (
                  <Bubble key={idx} role={msg.role} content={msg.content} />
                ))}
                {loading && (
                  <div style={{ textAlign: "left", marginBottom: 12 }}>
                    <Spin size="small" />
                    <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                      AI 正在分析...
                    </Text>
                  </div>
                )}
                <div ref={chatEndRef} />
              </>
            )}

            {/* 输入框 */}
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="描述您想教授的课程内容..."
                autoSize={{ minRows: 1, maxRows: 3 }}
                style={{ flex: 1 }}
                disabled={loading}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={loading}
                disabled={!input.trim()}
              >
                发送
              </Button>
            </div>
          </Card>

          {/* 操作区 */}
          <Space style={{ flexShrink: 0 }}>
            <Button
              icon={<SyncOutlined />}
              onClick={handleReset}
            >
              重置会话
            </Button>
            <Button
              type="primary"
              icon={<ArrowRightOutlined />}
              onClick={handleGenerateOutline}
              disabled={!result}
            >
              生成大纲
            </Button>
          </Space>
        </div>
      </div>
    </div>
  );
}
