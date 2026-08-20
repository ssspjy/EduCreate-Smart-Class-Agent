// pages/OutlinePage.tsx — 步骤 3：生成 PPT 大纲
import { useState } from "react";
import {
  Button,
  Card,
  Typography,
  Table,
  Tag,
  Space,
  Divider,
  Spin,
  message,
  Alert,
} from "antd";
import { PlayCircleOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useWorkflowStore } from "../stores/workflow";
import { apiGenerateOutline } from "../services/api";
import type { OutlineSection } from "../services/api";

const { Title, Text } = Typography;

export default function OutlinePage() {
  const { gpsResult, outline, setOutline, setCurrentStep } = useWorkflowStore();
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    if (!gpsResult) return;
    setLoading(true);
    try {
      const result = await apiGenerateOutline(gpsResult);
      setOutline(result);
      message.success("大纲生成完成");
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "生成失败";
      message.error(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<OutlineSection> = [
    {
      title: "#",
      dataIndex: "id",
      width: 60,
      render: (id: string) => <Tag>{id}</Tag>,
    },
    {
      title: "章节标题",
      dataIndex: "title",
      render: (t: string) => <Text strong>{t}</Text>,
    },
    {
      title: "要点",
      dataIndex: "bullets",
      render: (b: string[]) => (
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          {b.slice(0, 3).map((x, i) => (
            <li key={i} style={{ fontSize: 13 }}>
              {x}
            </li>
          ))}
          {b.length > 3 && <li style={{ fontSize: 13, color: "#999" }}>……</li>}
        </ul>
      ),
    },
    {
      title: "时长",
      dataIndex: "duration_minutes",
      width: 80,
      render: (m: number) => `${m} min`,
    },
    {
      title: "页数",
      dataIndex: "slide_count",
      width: 70,
      render: (n: number) => <Tag>{n}</Tag>,
    },
  ];

  return (
    <div className="page">
      <Title level={3}>步骤 3 / 5：生成 PPT 大纲</Title>
      <Text type="secondary">
        基于 GPS 澄清结果，自动生成章节结构、每页要点建议与时长分配。
      </Text>

      <Divider />

      {/* GPS 输入摘要 */}
      {gpsResult && (
        <Alert
          type="info"
          showIcon
          message={`${gpsResult.subject} · ${gpsResult.grade} · ${gpsResult.topic}`}
          description={`目标：${gpsResult.objectives.join("；")}`}
          style={{ marginBottom: 16 }}
        />
      )}

      {!outline ? (
        <div style={{ textAlign: "center", padding: 32 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Button
              type="primary"
              size="large"
              icon={<PlayCircleOutlined />}
              onClick={handleGenerate}
              loading={loading}
            >
              {loading ? "生成中……" : "点击生成大纲"}
            </Button>
          </div>
        </div>
      ) : (
        <>
          {/* 大纲总览 */}
          <Card
            title={
              <Space>
                <Text strong>{outline.title}</Text>
                <Tag color="blue">{outline.total_slides} 页</Tag>
                <Tag color="green">{outline.total_duration_minutes} 分钟</Tag>
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Space>
              <Text type="secondary">{outline.subject}</Text>
              <Text type="secondary">·</Text>
              <Text type="secondary">{outline.grade}</Text>
            </Space>
          </Card>

          {/* 章节表格 */}
          <Table
            columns={columns}
            dataSource={outline.sections}
            rowKey="id"
            pagination={false}
            size="small"
          />

          <Divider />
          <Space>
            <Button icon={<LeftOutlined />} onClick={() => setCurrentStep("clarify")}>
              上一步
            </Button>
            <Button
              type="primary"
              icon={<RightOutlined />}
              onClick={() => setCurrentStep("preview")}
            >
              下一步：预览课件
            </Button>
          </Space>
        </>
      )}
    </div>
  );
}
