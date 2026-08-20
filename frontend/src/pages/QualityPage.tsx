// pages/QualityPage.tsx — 步骤 5：质量检测与优化建议
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
  Progress,
  List,
  Alert,
} from "antd";
import {
  SafetyCertificateFilled,
  LeftOutlined,
  ReloadOutlined,
  CheckCircleFilled,
} from "@ant-design/icons";
import { useWorkflowStore } from "../stores/workflow";
import { apiQualityCheck } from "../services/api";

const { Title, Text, Paragraph } = Typography;

export default function QualityPage() {
  const { outline, qualityReport, setQualityReport, setCurrentStep } =
    useWorkflowStore();
  const [loading, setLoading] = useState(false);

  const handleCheck = async () => {
    if (!outline) return;
    setLoading(true);
    try {
      const result = await apiQualityCheck(outline);
      setQualityReport(result);
      message.success("质检完成");
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "质检失败";
      message.error(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "#52c41a";
    if (score >= 60) return "#faad14";
    return "#ff4d4f";
  };

  const getSubColor = (score: number) => {
    if (score >= 8) return "#52c41a";
    if (score >= 6) return "#faad14";
    return "#ff4d4f";
  };

  return (
    <div className="page">
      <Title level={3}>步骤 5 / 5：质量检测</Title>
      <Text type="secondary">
        对生成的大纲从清晰度、覆盖度、互动性三个维度评分，给出优化建议。
      </Text>

      <Steps
        current={4}
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

      {!outline ? (
        <Alert
          type="warning"
          message="请先完成前面的步骤，生成 PPT 大纲后再质检。"
          showIcon
        />
      ) : !qualityReport ? (
        <div style={{ textAlign: "center", padding: 32 }}>
          <SafetyCertificateFilled
            style={{ fontSize: 48, color: "#1890ff", marginBottom: 16 }}
          />
          <div>
            <Button
              type="primary"
              size="large"
              icon={<SafetyCertificateFilled />}
              onClick={handleCheck}
              loading={loading}
            >
              {loading ? "质检中……" : "开始质检"}
            </Button>
          </div>
          {loading && (
            <div style={{ marginTop: 16 }}>
              <Spin tip="正在分析大纲质量，请稍候……" />
            </div>
          )}
        </div>
      ) : (
        <>
          {/* 总分卡片 */}
          <Card
            style={{
              marginBottom: 16,
              background: `${getScoreColor(qualityReport.score)}11`,
              border: `1px solid ${getScoreColor(qualityReport.score)}`,
            }}
          >
            <Space align="center">
              <Progress
                type="circle"
                percent={qualityReport.score}
                strokeColor={getScoreColor(qualityReport.score)}
                size={80}
                format={(p) => (
                  <span style={{ fontSize: 18, fontWeight: "bold" }}>{p}</span>
                )}
              />
              <div>
                <Text strong style={{ fontSize: 18 }}>
                  {qualityReport.score >= 80
                    ? "优秀"
                    : qualityReport.score >= 60
                    ? "良好"
                    : "待改进"}
                </Text>
                <Paragraph type="secondary" style={{ margin: 0 }}>
                  总分 {qualityReport.score}/100
                </Paragraph>
              </div>
            </Space>
          </Card>

          {/* 三维度评分 */}
          <Space style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            {[
              { label: "清晰度", value: qualityReport.clarity, key: "clarity" as const },
              { label: "覆盖度", value: qualityReport.coverage, key: "coverage" as const },
              { label: "互动性", value: qualityReport.engagement, key: "engagement" as const },
            ].map(({ label, value, key }) => (
              <Card key={key} size="small" style={{ minWidth: 160 }}>
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Text type="secondary">{label}</Text>
                  <Progress
                    percent={(value / 10) * 100}
                    strokeColor={getSubColor(value)}
                    showInfo={false}
                    size="small"
                  />
                  <Text strong style={{ color: getSubColor(value) }}>
                    {value.toFixed(1)} / 10
                  </Text>
                </Space>
              </Card>
            ))}
          </Space>

          {/* 优化建议 */}
          <Card
            title="优化建议"
            style={{ marginTop: 16 }}
            headStyle={{ background: "#fffbe6" }}
          >
            <List
              size="small"
              dataSource={qualityReport.suggestions}
              renderItem={(s) => (
                <List.Item>
                  <Space>
                    <CheckCircleFilled style={{ color: "#faad14" }} />
                    <Text>{s}</Text>
                  </Space>
                </List.Item>
              )}
            />
          </Card>

          <Divider />
          <Space>
            <Button icon={<LeftOutlined />} onClick={() => setCurrentStep("preview")}>
              上一步
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => setQualityReport(null)}
              style={{ marginRight: 8 }}
            >
              重新质检
            </Button>
            <Button type="primary" onClick={() => setCurrentStep("upload")}>
              从头开始
            </Button>
          </Space>
        </>
      )}
    </div>
  );
}
