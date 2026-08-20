// pages/UploadPage.tsx — 课程资料上传页
// 支持多文件上传、自动解析、材料管理
import { useCallback, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  List,
  message,
  Row,
  Space,
  Spin,
  Steps,
  Tag,
  Typography,
  Statistic,
} from "antd";
import {
  CheckCircleOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  FileOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { apiUploadMaterial } from "../services/api";
import { useWorkflowStore } from "../stores/workflow";
import type { Material } from "../services/api";

const { Title, Text } = Typography;

type UploadStage = "idle" | "uploading" | "parsing" | "partial" | "done";

const STATUS_COLOR: Record<string, string> = {
  uploaded: "blue",
  parsing: "orange",
  parsed: "green",
  failed: "red",
  queued: "default",
  error: "red",
};

const STATUS_TEXT: Record<string, string> = {
  uploaded: "已上传",
  parsing: "解析中",
  parsed: "已就绪",
  failed: "失败",
  queued: "排队中",
  error: "错误",
};

export default function UploadPage() {
  const navigate = useNavigate();
  const { materials, addMaterial, removeMaterial, setCurrentStep } = useWorkflowStore();
  const [stage, setStage] = useState<UploadStage>("idle");
  const [uploadingCount, setUploadingCount] = useState(0);
  const [failedFiles, setFailedFiles] = useState<string[]>([]);

  // 实际执行上传
  const handleUpload = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    setStage("uploading");
    setUploadingCount(files.length);
    setFailedFiles([]);
    const newMaterials: Material[] = [];
    const failed: string[] = [];

    for (const file of files) {
      try {
        const mat = await apiUploadMaterial(file);
        newMaterials.push(mat);
        addMaterial(mat);
      } catch (err) {
        failed.push(file.name);
        console.error(`[UploadPage] ${file.name} 上传失败：`, err);
      }
    }

    setUploadingCount(0);
    if (newMaterials.length > 0) {
      setStage(newMaterials.length === files.length ? "done" : "partial");
    } else {
      setStage("idle");
    }
    setFailedFiles(failed);
    if (failed.length > 0) {
      message.error(`${failed.length} 个文件上传失败`);
    }
    if (newMaterials.length > 0) {
      message.success(`${newMaterials.length} 个文件上传成功`);
    }
  }, [addMaterial]);

  // 拖拽文件时触发上传
  const handleDrop = useCallback(async (e: DragEvent<HTMLDivElement>) => {
    const files = Array.from(e.dataTransfer.files);
    await handleUpload(files);
  }, [handleUpload]);

  // 删除单个材料
  const handleDelete = (fileId: string) => {
    removeMaterial(fileId);
    message.success("已删除");
  };

  // 继续到澄清页
  const handleNext = () => {
    if (materials.length === 0) {
      message.warning("请至少上传一份参考资料");
      return;
    }
    setCurrentStep("clarify");
    navigate("/clarify");
  };

  const totalFiles = materials.length;
  const parsedFiles = materials.filter((m) => m.status === "parsed").length;
  const failedCount = failedFiles.length;

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>📂 课程资料上传</Title>
        <Text type="secondary">上传教学参考材料（PPT / Word / PDF），支持多文件</Text>
      </div>

      {/* 步骤提示 */}
      <Steps
        current={0}
        style={{ marginBottom: 24 }}
        items={[
          { title: "上传资料", status: "process" },
          { title: "意图澄清", status: "wait" },
          { title: "生成大纲", status: "wait" },
          { title: "预览导出", status: "wait" },
        ]}
      />

      <Row gutter={16}>
        {/* 左侧：上传区 */}
        <Col span={14}>
          <Card
            title="上传参考材料"
            size="small"
            style={{ height: "100%" }}
          >
            {/* 拖拽上传区 */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              style={{
                border: "2px dashed #d9d9d9",
                borderRadius: 8,
                padding: "32px 16px",
                textAlign: "center",
                background: "#fafafa",
                cursor: "pointer",
                marginBottom: 16,
              }}
              onClick={() => {
                const input = document.createElement("input");
                input.type = "file";
                input.multiple = true;
                input.accept = ".pdf,.ppt,.pptx,.doc,.docx,.md,.txt";
                input.onchange = (e) => {
                  const files = Array.from((e.target as HTMLInputElement).files || []);
                  handleUpload(files);
                };
                input.click();
              }}
            >
              <CloudUploadOutlined style={{ fontSize: 48, color: "#1890ff", marginBottom: 8 }} />
              <div>
                <Text strong style={{ fontSize: 15 }}>拖拽文件到此处，或点击选择文件</Text>
              </div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                支持 PDF / PPT / Word / Markdown，单文件 ≤ 50MB
              </Text>
            </div>

            {/* 上传进度 */}
            {stage === "uploading" && (
              <Alert
                type="info"
                icon={<Spin size="small" />}
                message={`正在上传 ${uploadingCount} 个文件...`}
                style={{ marginBottom: 12 }}
              />
            )}

            {failedCount > 0 && (
              <Alert
                type="error"
                message={`${failedCount} 个文件上传失败，请重试`}
                style={{ marginBottom: 12 }}
              />
            )}

            {/* 文件列表 */}
            {materials.length > 0 && (
              <List
                size="small"
                dataSource={materials}
                renderItem={(item) => (
                  <List.Item
                    actions={[
                      <Button
                        key="del"
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={() => handleDelete(item.file_id)}
                      />,
                    ]}
                  >
                    <List.Item.Meta
                      avatar={<FileOutlined style={{ fontSize: 20 }} />}
                      title={
                        <Space>
                          <Text>{item.filename}</Text>
                          <Tag color={STATUS_COLOR[item.status] || "default"} style={{ fontSize: 11 }}>
                            {STATUS_TEXT[item.status] || item.status}
                          </Tag>
                          {item.chunk_count != null && (
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {item.chunk_count} 个片段
                            </Text>
                          )}
                        </Space>
                      }
                      description={item.error_message && (
                        <Text type="danger" style={{ fontSize: 11 }}>{item.error_message}</Text>
                      )}
                    />
                  </List.Item>
                )}
              />
            )}

            {/* 提示 */}
            <Alert
              type="info"
              message="材料用于辅助 GPS 意图提取和 PPT 内容生成"
              description="上传越多参考材料，AI 对课程内容的理解越准确"
              style={{ marginTop: 12 }}
            />
          </Card>
        </Col>

        {/* 右侧：统计与操作 */}
        <Col span={10}>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic title="已上传" value={totalFiles} suffix="个文件" />
              </Col>
              <Col span={12}>
                <Statistic
                  title="已就绪"
                  value={parsedFiles}
                  suffix={`/ ${totalFiles}`}
                  valueStyle={{ color: parsedFiles === totalFiles && totalFiles > 0 ? "#52c41a" : "#888" }}
                />
              </Col>
            </Row>
          </Card>

          {/* 当前状态 */}
          {materials.length === 0 && stage === "idle" && (
            <Card>
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="还没有上传任何文件"
              />
            </Card>
          )}

          {materials.length > 0 && stage !== "uploading" && (
            <Card
              title="下一步"
              size="small"
              styles={{ body: { padding: "16px" } as Record<string, unknown> }}
            >
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                <div>
                  <CheckCircleOutlined style={{ color: "#52c41a", marginRight: 8 }} />
                  <Text>已准备好 {totalFiles} 个参考材料</Text>
                </div>
                <Button
                  type="primary"
                  size="large"
                  block
                  onClick={handleNext}
                  icon={<RightOutlined />}
                  iconPosition="end"
                >
                  开始 GPS 意图澄清
                </Button>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  跳过上传直接进入澄清页也可以
                </Text>
              </Space>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
}
