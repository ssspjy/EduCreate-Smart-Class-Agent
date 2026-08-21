// pages/PreviewPage.tsx — PPT 预览与导出页
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  message,
  Result,
  Row,
  Space,
  Spin,
  Statistic,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  DownloadOutlined,
  ExportOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
} from "@ant-design/icons";
import { useWorkflowStore } from "../stores/workflow";
import { apiApplyPptActions, apiExportDOCX, apiExportPPTX } from "../services/api";
import type { Outline, PptEditAction } from "../services/api";

const { Title, Text } = Typography;

type ExportStage = "idle" | "exporting" | "done" | "error";

export default function PreviewPage() {
  const navigate = useNavigate();
  const { outline, setOutline, setCurrentStep, lessonId } = useWorkflowStore();
  const [stage, setStage] = useState<ExportStage>("idle");
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [docxUrl, setDocxUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const currentOutline = outline as Outline | null;

  const handleEditAction = async (action: PptEditAction) => {
    if (!currentOutline) return;
    try {
      const response = await apiApplyPptActions({
        outline: currentOutline,
        actions: [action],
        lesson_id: lessonId || undefined,
        instruction: "预览页章节顺序调整",
      });
      setOutline(response.outline);
      response.warnings.forEach((warning) => message.warning(warning));
      message.success("结构化编辑已应用");
    } catch (err: unknown) {
      message.error(`编辑失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleExport = async () => {
    if (!currentOutline) {
      message.warning("请先生成大纲");
      return;
    }
    setStage("exporting");
    setErrorMsg(null);
    try {
      const resp = await apiExportPPTX(currentOutline, lessonId ? { lesson_id: lessonId } : undefined);
      setDownloadUrl(resp.url);
      setStage("done");
      message.success("PPT 导出成功，点击下载");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setStage("error");
      message.error(`导出失败：${msg}`);
    }
  };

  const handleExportDocx = async () => {
    if (!currentOutline) return;
    try {
      const resp = await apiExportDOCX(currentOutline);
      setDocxUrl(resp.url);
      message.success("DOCX 教案导出成功");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      message.error(`DOCX 导出失败：${msg}`);
    }
  };

  // 直接下载
  const handleDownload = () => {
    if (!downloadUrl) return;
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `${currentOutline?.title || "课件"}.pptx`;
    a.click();
  };

  if (!currentOutline) {
    return (
      <div className="page">
        <Title level={4}>📄 PPT 预览与导出</Title>
        <Empty
          description="请先在「大纲生成」页面完成大纲"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={() => navigate("/outline")}>
            去生成大纲
          </Button>
        </Empty>
      </div>
    );
  }

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>📄 PPT 预览与导出</Title>
        <Text type="secondary">
          {currentOutline.title}
        </Text>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="总页数" value={currentOutline.total_slides} suffix="页" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="总时长"
              value={currentOutline.total_duration_minutes}
              suffix="分钟"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="章节数" value={currentOutline.sections.length} suffix="节" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="导出状态" value={stage === "done" ? "✅ 就绪" : "⏳ 待导出"} />
          </Card>
        </Col>
      </Row>

      {/* 大纲内容预览 */}
      <Card
        title="大纲内容预览"
        size="small"
        style={{ marginBottom: 24 }}
        styles={{ body: { maxHeight: 360, overflowY: "auto" } as Record<string, unknown> }}
      >
        {currentOutline.sections.map((section, i) => (
          <div key={section.id} style={{ marginBottom: i < currentOutline.sections.length - 1 ? 16 : 0 }}>
            <Space wrap>
              <Text strong>{i + 1}. {section.title}</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {section.duration_minutes} 分钟 · {section.slide_count} 页
              </Text>
              <Button
                size="small"
                icon={<ArrowUpOutlined />}
                disabled={i === 0}
                onClick={() => void handleEditAction({ type: "move_section", section_id: section.id, to_index: i - 1 })}
              />
              <Button
                size="small"
                icon={<ArrowDownOutlined />}
                disabled={i === currentOutline.sections.length - 1}
                onClick={() => void handleEditAction({ type: "move_section", section_id: section.id, to_index: i + 1 })}
              />
            </Space>
            <ul style={{ margin: "4px 0 0 20px", paddingLeft: 0 }}>
              {section.bullets.map((b, j) => (
                <li key={j}>
                  <Text style={{ fontSize: 12 }}>{b}</Text>
                </li>
              ))}
            </ul>
            {i < currentOutline.sections.length - 1 && <Divider style={{ margin: "12px 0" }} />}
          </div>
        ))}
      </Card>

      {/* 导出操作 */}
      <Card>
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          {stage === "idle" && (
            <>
              <Alert
                type="info"
                message="确认导出"
                description={`将基于大纲「${currentOutline.title}」生成 PPT 文件，请确认后点击导出。`}
              />
              <Space>
                <Button
                  type="primary"
                  icon={<ExportOutlined />}
                  size="large"
                  onClick={handleExport}
                >
                  导出 PPTX
                </Button>
                <Button onClick={() => void handleExportDocx()}>
                  导出 DOCX 教案
                </Button>
                <Button onClick={() => navigate("/outline")}>返回修改大纲</Button>
              </Space>
            </>
          )}

          {stage === "exporting" && (
            <Result
              icon={<Spin size="large" />}
              title="正在生成 PPT，请稍候..."
              subTitle="后端正在调用 python-pptx 渲染大纲内容"
            />
          )}

          {stage === "done" && downloadUrl && (
            <Result
              status="success"
              icon={<CheckCircleOutlined />}
              title="PPT 导出成功！"
              subTitle="文件已就绪，点击下方按钮下载"
              extra={[
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  size="large"
                  onClick={handleDownload}
                  key="download"
                >
                  下载 PPT 文件
                </Button>,
                <Button key="quality" onClick={() => { setCurrentStep("quality"); navigate("/quality"); }}>
                  前往质检
                </Button>,
                ...(docxUrl ? [
                  <Button key="docx" href={docxUrl} download>
                    下载 DOCX 教案
                  </Button>,
                ] : []),
              ]}
            />
          )}

          {stage === "error" && (
            <Result
              status="error"
              title="导出失败"
              subTitle={errorMsg || "请稍后重试"}
              extra={[
                <Button key="retry" type="primary" onClick={() => setStage("idle")}>
                  重试
                </Button>,
              ]}
            />
          )}
        </Space>
      </Card>
    </div>
  );
}
