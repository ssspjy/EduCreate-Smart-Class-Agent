// pages/ClarifyPage.tsx — 步骤 2：GPS 教学意图澄清
import { useState, useEffect } from "react";
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
} from "antd";
import { SendOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import { useWorkflowStore } from "../stores/workflow";
import { apiClarify, apiCreateLesson, type ClarifyResponse } from "../services/api";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
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
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const navigate = useNavigate();

  const goToStep = (step: "upload" | "outline", path: string) => {
    setCurrentStep(step);
    navigate(path);
  };

  const handleSubmit = async () => {
    if (!query.trim()) return;
    const userMsg: ChatMessage = { role: "user", content: query };
    setHistory((h) => [...h, userMsg]);
    setLoading(true);
    try {
      // 如果还没有 lessonId，先创建一个
      let currentLessonId = lessonId;
      if (!currentLessonId) {
        const lesson = await apiCreateLesson({ title: `教案-${Date.now()}` });
        setLessonId(lesson.id);
        currentLessonId = lesson.id;
      }

      const resp: ClarifyResponse = await apiClarify(
        query,
        materials.map((m) => m.file_id),
        currentLessonId ?? undefined,
        gpsSessionId ?? undefined,
        history as ChatMessage[],
      );
      const result = resp.result;
      setGpsResult(result);

      // 如果后端返回了新的 sessionId，保存到 store
      if (resp.session_id) {
        setGpsSessionId(resp.session_id);
      }

      setHistory((h) => [
        ...h,
        {
          role: "assistant",
          content: `已解析：${result.subject} · ${result.grade} · ${result.topic}`,
        },
      ]);
      // 如果还有缺失槽位，展示追问建议
      if (resp.needs_more_info && resp.suggestion) {
        setHistory((h) => [
          ...h,
          {
            role: "assistant",
            content: resp.suggestion!,
          },
        ]);
      }
      setQuery("");
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "澄清失败";
      message.error(errMsg);
      setHistory((h) => h.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <Title level={3}>步骤 2 / 5：教学意图澄清（GPS）</Title>
      <Text type="secondary">
        描述您的教学目标，系统通过多轮对话帮您结构化提取：科目、年级、知识点、能力目标。
      </Text>

      <Steps
        current={gpsResult ? 2 : history.length}
        style={{ marginTop: 16, marginBottom: 16 }}
        items={[
          { title: "上传材料" },
          { title: "意图澄清" },
          { title: "大纲生成" },
          { title: "预览" },
          { title: "质检" },
        ]}
      />

      {/* 对话历史 */}
      {history.length > 0 && (
        <List
          style={{ marginBottom: 16, maxHeight: 300, overflowY: "auto" }}
          dataSource={history}
          renderItem={(msg) => (
            <List.Item
              style={{
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                border: "none",
              }}
            >
              <Card
                size="small"
                style={{
                  maxWidth: "70%",
                  background:
                    msg.role === "user" ? "#1890ff" : "#f5f5f5",
                  color: msg.role === "user" ? "#fff" : "#000",
                }}
              >
                <Paragraph style={{ color: "inherit", margin: 0 }}>
                  {msg.content}
                </Paragraph>
              </Card>
            </List.Item>
          )}
        />
      )}

      {/* GPS 结构化结果预览 */}
      {gpsResult && (
        <>
          <Divider>结构化结果</Divider>
          <Card size="small">
            <Space wrap>
              <Tag color="blue">{gpsResult.subject}</Tag>
              <Tag color="green">{gpsResult.grade}</Tag>
              <Tag color="orange">{gpsResult.difficulty}</Tag>
            </Space>
            <Paragraph strong style={{ marginTop: 8 }}>
              主题：{gpsResult.topic}
            </Paragraph>
            <Paragraph>
              <Text strong>教学目标：</Text>
              {gpsResult.objectives.join("；")}
            </Paragraph>
            <Paragraph>
              <Text strong>重点：</Text>
              {gpsResult.key_points.join("；")}
            </Paragraph>
          </Card>
        </>
      )}

      {/* 输入框 */}
      <TextArea
        placeholder="例如：我想讲一节初中物理的浮力课，重点讲阿基米德原理，学生基础一般……"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onPressEnter={(e) => !e.shiftKey && (e.preventDefault(), handleSubmit())}
        rows={3}
        style={{ marginTop: 8 }}
      />

      <Space style={{ marginTop: 8 }}>
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSubmit}
          loading={loading}
          disabled={!query.trim()}
        >
          发送
        </Button>
      </Space>

      <Divider />

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
          disabled={!gpsResult}
          onClick={() => goToStep("outline", "/outline")}
        >
          下一步：生成大纲
        </Button>
      </Space>
    </div>
  );
}
