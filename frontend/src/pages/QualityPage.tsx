// pages/QualityPage.tsx — 质检报告页
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  List,
  message,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import { useWorkflowStore } from "../stores/workflow";
import { apiQualityCheck } from "../services/api";
import type { Outline, QualityReport } from "../services/api";

const { Title, Text } = Typography;

const SCORE_COLOR = (score: number): string =>
  score >= 80 ? "#52c41a" : score >= 60 ? "#faad14" : "#ff4d4f";

export default function QualityPage() {
  const navigate = useNavigate();
  const { outline } = useWorkflowStore();
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentOutline = outline as Outline | null;

  const handleCheck = async () => {
    if (!currentOutline) {
      message.warning("请先生成大纲");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await apiQualityCheck(currentOutline);
      setReport(result);
      message.success("质检完成");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      message.error(`质检失败：${msg}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!currentOutline) {
      message.info("请先生成大纲再进行质检");
    }
  }, [currentOutline]);

  // Radar chart data
  const radarData = report
    ? [
        { dimension: "清晰度", value: (report.clarity || 0) * 100 },
        { dimension: "覆盖度", value: (report.coverage || 0) * 100 },
        { dimension: "互动性", value: (report.engagement || 0) * 100 },
      ]
    : [];

  const radarOption = {
    tooltip: {
      trigger: "item",
    },
    radar: {
      indicator: radarData.map((item) => ({
        name: item.dimension,
        max: 100,
      })),
      radius: "62%",
      splitNumber: 4,
      axisName: {
        color: "#4b5563",
      },
    },
    series: [
      {
        type: "radar",
        data: radarData.length
          ? [
              {
                value: radarData.map((item) => item.value),
                name: "分项得分",
                areaStyle: {
                  color: "rgba(24, 144, 255, 0.2)",
                },
                lineStyle: {
                  color: "#1890ff",
                },
                itemStyle: {
                  color: "#1890ff",
                },
              },
            ]
          : [],
      },
    ],
  };

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>🔍 质检报告</Title>
        {!currentOutline && (
          <Tag color="orange">需要先生成大纲</Tag>
        )}
      </div>

      {!currentOutline ? (
        <Empty
          description="请先完成大纲生成"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={() => navigate("/outline")}>
            去生成大纲
          </Button>
        </Empty>
      ) : (
        <>
          {/* 质检按钮 */}
          <Card size="small" style={{ marginBottom: 16 }}>
            <Space>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={handleCheck}
                loading={loading}
                disabled={loading}
              >
                执行质检
              </Button>
              {report && (
                <Button icon={<ReloadOutlined />} onClick={handleCheck} loading={loading}>
                  重新质检
                </Button>
              )}
              <Text type="secondary">
                基于大纲结构评估清晰度 / 覆盖度 / 互动性
              </Text>
            </Space>
            {error && (
              <Alert
                type="error"
                message={error}
                style={{ marginTop: 8 }}
                closable
                onClose={() => setError(null)}
              />
            )}
          </Card>

          {!report && !loading && (
            <Empty
              description="点击「执行质检」生成质检报告"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}

          {loading && (
            <Card>
              <div style={{ textAlign: "center", padding: "40px 0" }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>
                  <Text>正在分析大纲质量，请稍候...</Text>
                </div>
              </div>
            </Card>
          )}

          {report && !loading && (
            <>
              {/* 总分 + 分项雷达 */}
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={8}>
                  <Card size="small">
                    <Statistic
                      title="综合评分"
                      value={report.score}
                      suffix="/ 100"
                      valueStyle={{
                        color: SCORE_COLOR(report.score),
                        fontSize: 36,
                        fontWeight: "bold",
                      }}
                      prefix={
                        report.score >= 80 ? (
                          <CheckCircleOutlined style={{ color: "#52c41a" }} />
                        ) : report.score >= 60 ? (
                          <CheckCircleOutlined style={{ color: "#faad14" }} />
                        ) : (
                          <CloseCircleOutlined style={{ color: "#ff4d4f" }} />
                        )
                      }
                    />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card size="small" title="分项得分">
                    <Space direction="vertical" size="small" style={{ width: "100%" }}>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>清晰度</Text>
                        <Progress
                          percent={Math.round((report.clarity || 0) * 100)}
                          size="small"
                          strokeColor={SCORE_COLOR((report.clarity || 0) * 100)}
                        />
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>覆盖度</Text>
                        <Progress
                          percent={Math.round((report.coverage || 0) * 100)}
                          size="small"
                          strokeColor={SCORE_COLOR((report.coverage || 0) * 100)}
                        />
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>互动性</Text>
                        <Progress
                          percent={Math.round((report.engagement || 0) * 100)}
                          size="small"
                          strokeColor={SCORE_COLOR((report.engagement || 0) * 100)}
                        />
                      </div>
                    </Space>
                  </Card>
                </Col>
                <Col span={8}>
                  <Card size="small" title="雷达图">
                    {radarData.length > 0 && (
                      <ReactECharts
                        option={radarOption}
                        style={{ height: 180 }}
                        opts={{ renderer: "canvas" }}
                      />
                    )}
                  </Card>
                </Col>
              </Row>

              {/* 改进建议 */}
              <Card title="📋 改进建议">
                {report.suggestions && report.suggestions.length > 0 ? (
                  <List
                    size="small"
                    dataSource={report.suggestions}
                    renderItem={(s, i) => (
                      <List.Item>
                        <Space>
                          <Tag color="orange">{i + 1}</Tag>
                          <Text>{s}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty
                    description="大纲质量良好，暂无需强制改进项"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                )}
              </Card>

              {/* 底部导航 */}
              <div style={{ marginTop: 24, textAlign: "center" }}>
                <Space>
                  <Button onClick={() => navigate("/preview")}>返回预览</Button>
                  <Button
                    type="primary"
                    onClick={() => {
                      if (report.score >= 80) {
                        message.success("大纲质量达标，可以直接使用！");
                      } else {
                        message.info("建议根据建议优化后再次质检");
                      }
                    }}
                  >
                    完成质检
                  </Button>
                </Space>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
