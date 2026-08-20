// pages/PreviewPage.tsx — 步骤 4：课件预览与导出
import { useState } from "react";
import {
  Button,
  Card,
  Typography,
  Tag,
  Space,
  Divider,
  Spin,
  message,
  Steps,
  List,
} from "antd";
import {
  DownloadOutlined,
  LeftOutlined,
  RightOutlined,
  CheckCircleFilled,
} from "@ant-design/icons";
import { useWorkflowStore } from "../stores/workflow";
import { apiExportPPTX } from "../services/api";

const { Title, Text, Paragraph } = Typography;

export default function PreviewPage() {
  const { outline, setCurrentStep } = useWorkflowStore();
  const [pptxUrl, setPptxUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    if (!outline) return;
    setExporting(true);
    try {
      const result = await apiExportPPTX(outline);
      setPptxUrl(result.url);
      message.success("PPTX 已生成，可下载");
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "导出失败";
      message.error(errMsg);
    } finally {
      setExporting(false);
    }
  };

  if (!outline) {
    return (
      <div className="page">
        <Title level={3}>步骤 4 / 5：预览课件</Title>
        <Text type="secondary">请先在"大纲生成"步骤生成 PPT 大纲。</Text>
        <div style={{ marginTop: 16 }}>
          <Button onClick={() => setCurrentStep("outline")}>去生成大纲</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Title level={3}>步骤 4 / 5：课件预览</Title>
      <Text type="secondary">确认大纲章节，可按需调整后导出 PPTX。</Text>

      <Steps
        current={3}
        style={{ marginTop: 16, marginBottom: 16 }}
        items={[
          { title: "上传" },
          { title: "澄清" },
          { title: "大纲" },
          { title: "预览" },
          { title: "质检" },
        ]}
      />

      <Divider />

      {/* 大纲总览 */}
      <Card
        title={
          <Space>
            <Text strong>{outline.title}</Text>
            <Tag color="blue">{outline.total_slides} 页</Tag>
          </Space>
        }
        extra={
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={handleExport}
          >
            导出 PPTX
          </Button>
        }
        style={{ marginBottom: 16 }}
      >
        <Space wrap>
          <Tag color="geekblue">{outline.subject}</Tag>
          <Tag color="green">{outline.grade}</Tag>
        </Space>
        <Paragraph style={{ marginTop: 8 }}>
          共 <strong>{outline.sections.length}</strong> 个章节，
          预计 <strong>{outline.total_duration_minutes}</strong> 分钟。
        </Paragraph>
      </Card>

      {/* 章节列表 */}
      <List
        header={<Text strong>章节结构</Text>}
        bordered
        dataSource={outline.sections}
        renderItem={(section) => (
          <List.Item>
            <List.Item.Meta
              avatar={<CheckCircleFilled style={{ color: "#52c41a" }} />}
              title={section.title}
              description={
                <Space wrap>
                  <Tag>{section.duration_minutes} 分钟</Tag>
                  <Tag>{section.slide_count} 页</Tag>
                  {section.bullets.slice(0, 2).map((b, i) => (
                    <Tag key={i} color="default" style={{ maxWidth: 200 }}>
                      {b.length > 20 ? b.slice(0, 20) + "…" : b}
                    </Tag>
                  ))}
                </Space>
              }
            />
          </List.Item>
        )}
      />

      {/* 导出状态 */}
      {pptxUrl && (
        <Card style={{ marginTop: 16, background: "#f6ffed", border: "1px solid #b7eb8f" }}>
          <Text style={{ color: "#52c41a" }}>
            <CheckCircleFilled /> PPTX 已生成！{" "}
            <a href={pptxUrl} download>
              点击下载
            </a>
          </Text>
        </Card>
      )}

      {exporting && !pptxUrl && (
        <div style={{ textAlign: "center", marginTop: 16 }}>
          <Spin tip="正在生成 PPTX，请稍候……" />
        </div>
      )}

      <Divider />
      <Space>
        <Button icon={<LeftOutlined />} onClick={() => setCurrentStep("outline")}>
          上一步
        </Button>
        <Button
          type="primary"
          icon={<RightOutlined />}
          onClick={() => setCurrentStep("quality")}
        >
          下一步：质量检测
        </Button>
      </Space>
    </div>
  );
}
