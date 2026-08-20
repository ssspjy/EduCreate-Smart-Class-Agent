// pages/OutlinePage.tsx — PPT 大纲展示页
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Col,
  Collapse,
  Divider,
  Empty,
  message,
  Row,
  Statistic,
  Tag,
  Typography,
} from "antd";
import { ExportOutlined, ArrowLeftOutlined, FieldTimeOutlined } from "@ant-design/icons";
import { useWorkflowStore } from "../stores/workflow";
import { apiGenerateOutline } from "../services/api";
import type { GpsClarifyResult, Outline } from "../services/api";

const { Title, Text } = Typography;

const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "green",
  medium: "orange",
  hard: "red",
};

const DIFFICULTY_TEXT: Record<string, string> = {
  easy: "基础",
  medium: "中等",
  hard: "进阶",
};

export default function OutlinePage() {
  const navigate = useNavigate();
  const { gpsResult, outline, setOutline, setCurrentStep } = useWorkflowStore();
  const [loading, setLoading] = useState(false);

  // 没有 GPS 结果时，提示跳转
  useEffect(() => {
    if (!gpsResult) {
      message.warning("请先完成 GPS 意图澄清");
    }
  }, [gpsResult]);

  const handleGenerate = async () => {
    if (!gpsResult) {
      message.warning("请先完成 GPS 意图澄清");
      return;
    }
    setLoading(true);
    try {
      const result = await apiGenerateOutline(gpsResult as GpsClarifyResult);
      setOutline(result);
      message.success("大纲生成成功");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      message.error(`生成失败：${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    setCurrentStep("preview");
    navigate("/preview");
  };

  const gps = gpsResult as GpsClarifyResult | null;
  const currentOutline = outline as Outline | null;

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/clarify")}>
          返回澄清
        </Button>
        <Title level={4} style={{ margin: 0 }}>📑 PPT 大纲生成</Title>
        {currentOutline && (
          <Tag color="blue">v{currentOutline.sections.length} 章节</Tag>
        )}
      </div>

      {/* GPS 信息摘要 */}
      {gps && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={4}>
              <Statistic title="科目" value={gps.subject || "—"} />
            </Col>
            <Col span={4}>
              <Statistic title="年级" value={gps.grade || "—"} />
            </Col>
            <Col span={6}>
              <Statistic title="课题" value={gps.topic || "—"} />
            </Col>
            <Col span={4}>
              <Statistic
                title="难度"
                value={DIFFICULTY_TEXT[gps.difficulty] || gps.difficulty || "—"}
                valueStyle={{ color: DIFFICULTY_COLOR[gps.difficulty] || "#888" }}
              />
            </Col>
            <Col span={4}>
              <Statistic title="风格" value={gps.style || "—"} />
            </Col>
            <Col span={2}>
              <Statistic
                title="置信度"
                value={`${Math.round((gps.confidence || 0) * 100)}%`}
                valueStyle={{ fontSize: 16 }}
              />
            </Col>
          </Row>

          {(gps.objectives?.length > 0 || gps.key_points?.length > 0) && (
            <>
              <Divider style={{ margin: "12px 0" }} />
              <Row gutter={24}>
                {gps.objectives?.length > 0 && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 12 }}>学习目标</Text>
                    <div>
                      {gps.objectives.map((obj, i) => (
                        <Tag key={i} style={{ marginTop: 4 }}>{obj}</Tag>
                      ))}
                    </div>
                  </Col>
                )}
                {gps.key_points?.length > 0 && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 12 }}>教学重点</Text>
                    <div>
                      {gps.key_points.map((kp, i) => (
                        <Tag key={i} color="orange" style={{ marginTop: 4 }}>{kp}</Tag>
                      ))}
                    </div>
                  </Col>
                )}
              </Row>
            </>
          )}
        </Card>
      )}

      {/* 大纲区域 */}
      {!currentOutline ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="点击下方按钮，基于 GPS 信息生成 PPT 大纲"
        >
          <Button
            type="primary"
            size="large"
            onClick={handleGenerate}
            loading={loading}
            disabled={!gpsResult}
          >
            基于 GPS 生成大纲
          </Button>
          {!gpsResult && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                需要先完成「意图澄清」步骤
              </Text>
            </div>
          )}
        </Empty>
      ) : (
        <>
          {/* 大纲概览 */}
          <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={32} align="middle">
              <Col>
                <Statistic
                  title="总页数"
                  value={currentOutline.total_slides}
                  suffix="页"
                />
              </Col>
              <Col>
                <Statistic
                  title="总时长"
                  value={currentOutline.total_duration_minutes}
                  suffix="分钟"
                  prefix={<FieldTimeOutlined />}
                />
              </Col>
              <Col>
                <Statistic
                  title="章节数"
                  value={currentOutline.sections.length}
                  suffix="节"
                />
              </Col>
              <Col style={{ marginLeft: "auto" }}>
                <Button
                  type="primary"
                  icon={<ExportOutlined />}
                  onClick={handleExport}
                  size="large"
                >
                  预览并导出
                </Button>
              </Col>
            </Row>
          </Card>

          {/* 分节折叠 */}
          <Collapse
            defaultActiveKey={currentOutline.sections.map((_, i) => String(i))}
            items={currentOutline.sections.map((section, i) => ({
              key: String(i),
              label: (
                <span>
                  <Tag>{i + 1}</Tag>
                  <Text strong>{section.title}</Text>
                  <Text type="secondary" style={{ marginLeft: 12, fontSize: 12 }}>
                    {section.duration_minutes} 分钟 · {section.slide_count} 页
                  </Text>
                </span>
              ),
              children: (
                <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                  {section.bullets.map((b, j) => (
                    <li key={j}>
                      <Text style={{ fontSize: 13 }}>{b}</Text>
                    </li>
                  ))}
                </ul>
              ),
            }))}
          />

          {/* 重新生成 */}
          <div style={{ marginTop: 16, textAlign: "center" }}>
            <Button onClick={handleGenerate} loading={loading}>
              重新生成大纲
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
