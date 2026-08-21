// pages/PreviewPage.tsx — PPT 预览与导出页
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Input,
  InputNumber,
  message,
  Progress,
  Result,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
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
import { apiApplyPptActions, apiCancelGenerationJob, apiCreatePptxJob, apiExportDOCX, apiExportPPTX, apiGenerateInteractive, apiGetGenerationJob, apiRetryGenerationJob, apiRewritePptInstruction, apiSubscribeGenerationJob } from "../services/api";
import type { GenerationJob, InteractionType, Outline, PptEditAction } from "../services/api";

const { Title, Text } = Typography;

type ExportStage = "idle" | "exporting" | "done" | "error";

export default function PreviewPage() {
  const navigate = useNavigate();
  const { outline, setOutline, setCurrentStep, lessonId } = useWorkflowStore();
  const [stage, setStage] = useState<ExportStage>("idle");
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [docxUrl, setDocxUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [generationJobId, setGenerationJobId] = useState<string | null>(null);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationJobStatus, setGenerationJobStatus] = useState<GenerationJob["status"] | null>(null);
  const [instruction, setInstruction] = useState("");
  const [rewriteLoading, setRewriteLoading] = useState(false);
  const [pendingActions, setPendingActions] = useState<PptEditAction[]>([]);
  const [rewriteExplanation, setRewriteExplanation] = useState<string | null>(null);
  const [interactionType, setInteractionType] = useState<InteractionType>("choice");
  const [interactionCount, setInteractionCount] = useState(3);
  const [interactionHtml, setInteractionHtml] = useState<string | null>(null);
  const [interactionLoading, setInteractionLoading] = useState(false);
  const settledJobsRef = useRef(new Set<string>());

  const currentOutline = outline as Outline | null;

  const applyGenerationJob = useCallback((job: GenerationJob) => {
    setGenerationProgress(job.progress);
    setGenerationJobStatus(job.status);
    if ((job.status === "completed" || job.status === "failed") && settledJobsRef.current.has(job.job_id)) {
      return;
    }
    if (job.status === "completed" && job.output?.url) {
      settledJobsRef.current.add(job.job_id);
      setDownloadUrl(job.output.url);
      setStage("done");
      job.output.warnings?.forEach((warning) => message.warning(warning));
      message.success("PPT 导出成功，点击下载");
    } else if (job.status === "failed") {
      settledJobsRef.current.add(job.job_id);
      setErrorMsg(job.error_message || "课件生成任务失败");
      setStage("error");
    } else if (job.status === "cancelled") {
      settledJobsRef.current.add(job.job_id);
      setErrorMsg(job.error_message || "课件生成已取消");
      setStage("error");
      message.info("课件生成已取消");
    } else if (job.status === "cancelling") {
      message.info("正在等待生成器安全停止");
    }
  }, []);

  useEffect(() => {
    if (!generationJobId || stage !== "exporting") return;
    const controller = apiSubscribeGenerationJob(generationJobId, applyGenerationJob);
    const polling = window.setInterval(() => {
      void apiGetGenerationJob(generationJobId).then(applyGenerationJob).catch(() => undefined);
    }, 1500);
    return () => {
      controller.abort();
      window.clearInterval(polling);
    };
  }, [applyGenerationJob, generationJobId, stage]);

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

  const handleRewriteInstruction = async () => {
    if (!currentOutline || !instruction.trim()) {
      message.warning("请先输入修改意见");
      return;
    }
    setRewriteLoading(true);
    try {
      const response = await apiRewritePptInstruction({ outline: currentOutline, instruction: instruction.trim() });
      setPendingActions(response.actions);
      setRewriteExplanation(response.explanation);
      response.warnings.forEach((warning) => message.warning(warning));
      if (response.actions.length) message.success(`已识别 ${response.actions.length} 个结构化动作，请确认应用`);
    } catch (err: unknown) {
      message.error(`意见解析失败：${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRewriteLoading(false);
    }
  };

  const handleApplyPending = async () => {
    if (!currentOutline || !pendingActions.length) return;
    try {
      const response = await apiApplyPptActions({
        outline: currentOutline,
        actions: pendingActions,
        lesson_id: lessonId || undefined,
        instruction: instruction.trim(),
      });
      setOutline(response.outline);
      setPendingActions([]);
      setRewriteExplanation(null);
      setStage("idle");
      setDownloadUrl(null);
      response.warnings.forEach((warning) => message.warning(warning));
      message.success("修改意见已应用到大纲");
    } catch (err: unknown) {
      message.error(`应用失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleGenerateInteractive = async () => {
    if (!currentOutline) return;
    setInteractionLoading(true);
    try {
      const response = await apiGenerateInteractive({
        outline: currentOutline,
        interaction_type: interactionType,
        count: interactionCount,
      });
      setInteractionHtml(response.html);
      response.warnings.forEach((warning) => message.warning(warning));
      if (response.items.length) message.success(`已生成 ${response.items.length} 道互动题`);
    } catch (err: unknown) {
      message.error(`互动内容生成失败：${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setInteractionLoading(false);
    }
  };

  const handleExport = async () => {
    if (!currentOutline) {
      message.warning("请先生成大纲");
      return;
    }
    setStage("exporting");
    setGenerationProgress(0);
    setGenerationJobId(null);
    setGenerationJobStatus(null);
    setErrorMsg(null);
    try {
      if (lessonId) {
        const job = await apiCreatePptxJob(currentOutline, lessonId);
        applyGenerationJob(job);
        if (job.status === "queued" || job.status === "generating") {
          setGenerationJobId(job.job_id);
        }
        return;
      }
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

  const handleCancelGeneration = async () => {
    if (!generationJobId) return;
    try {
      const job = await apiCancelGenerationJob(generationJobId);
      applyGenerationJob(job);
    } catch (err: unknown) {
      message.error(`取消失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleRetryGeneration = async () => {
    if (!generationJobId) {
      setStage("idle");
      return;
    }
    // 同一任务取消/失败后重试时，允许新的终态再次驱动界面。
    settledJobsRef.current.delete(generationJobId);
    setStage("exporting");
    setGenerationProgress(0);
    setErrorMsg(null);
    try {
      const job = await apiRetryGenerationJob(generationJobId);
      applyGenerationJob(job);
      if (job.status === "queued" || job.status === "generating") {
        setGenerationJobId(job.job_id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      setStage("error");
      message.error(`重试失败：${msg}`);
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

      <Card title="教师修改意见" size="small" style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input.TextArea
            rows={3}
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            placeholder="例如：把第2节上移，增加一个生活案例，并改成现代活泼风格"
            maxLength={500}
            showCount
          />
          <Space wrap>
            <Button onClick={() => void handleRewriteInstruction()} loading={rewriteLoading}>
              识别修改意见
            </Button>
            {pendingActions.map((action, index) => (
              <Tag color="blue" key={`${action.type}-${index}`}>{action.type}</Tag>
            ))}
            {pendingActions.length > 0 && (
              <Button type="primary" onClick={() => void handleApplyPending()}>
                确认应用
              </Button>
            )}
          </Space>
          {rewriteExplanation && <Text type="secondary">{rewriteExplanation}</Text>}
        </Space>
      </Card>

      <Card title="课堂互动内容" size="small" style={{ marginBottom: 24 }}>
        <Space wrap>
          <Select
            value={interactionType}
            style={{ width: 140 }}
            onChange={(value: InteractionType) => setInteractionType(value)}
            options={[
              { value: "choice", label: "选择题" },
              { value: "true_false", label: "判断题" },
              { value: "fill_blank", label: "填空题" },
            ]}
          />
          <InputNumber min={1} max={5} value={interactionCount} onChange={(value) => setInteractionCount(value || 1)} />
          <Button type="primary" onClick={() => void handleGenerateInteractive()} loading={interactionLoading}>
            生成互动题
          </Button>
        </Space>
        {interactionHtml && (
          <iframe
            title="课堂互动预览"
            sandbox=""
            srcDoc={interactionHtml}
            style={{ width: "100%", minHeight: 320, border: "1px solid #e5e7eb", borderRadius: 8, marginTop: 16 }}
          />
        )}
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
              subTitle={
                <Space direction="vertical" style={{ width: 360 }}>
                  <Text type="secondary">
                    {generationJobStatus === "cancelling" ? "正在安全停止生成任务" : "后端正在调用 python-pptx 安全渲染大纲内容"}
                  </Text>
                  <Progress percent={generationProgress} status="active" />
                  {generationJobId && generationJobStatus !== "cancelling" && (
                    <Button danger onClick={() => void handleCancelGeneration()}>取消生成</Button>
                  )}
                </Space>
              }
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
                <Button key="retry" type="primary" onClick={() => void handleRetryGeneration()}>
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
