// pages/UploadPage.tsx — 课程资料上传页
// 支持多文件上传、自动解析、材料管理
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
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
  FileSearchOutlined,
  RightOutlined,
} from "@ant-design/icons";
import {
  apiDeleteMaterial,
  apiGetMaterialChunks,
  apiListMaterials,
  apiUploadMaterial,
} from "../services/api";
import { useWorkflowStore } from "../stores/workflow";
import type { Material, MaterialChunk } from "../services/api";
import { getChunkSourceLabel, isMaterialUsable, SUPPORTED_FILE_ACCEPT } from "../utils/materials";

const { Paragraph, Title, Text } = Typography;

type UploadStage = "idle" | "uploading" | "parsing" | "partial" | "done";
type UploadFailure = { filename: string; reason: string };

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
  const { materials, setMaterials, addMaterial, removeMaterial, setCurrentStep } = useWorkflowStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [stage, setStage] = useState<UploadStage>("idle");
  const [uploadingCount, setUploadingCount] = useState(0);
  const [failedFiles, setFailedFiles] = useState<UploadFailure[]>([]);
  const [syncWarning, setSyncWarning] = useState<string | null>(null);
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);
  const [selectedChunks, setSelectedChunks] = useState<MaterialChunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);

  useEffect(() => {
    let active = true;
    void apiListMaterials()
      .then((serverMaterials) => {
        if (!active) return;
        setMaterials(serverMaterials);
        setSyncWarning(null);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setSyncWarning(error instanceof Error ? error.message : "无法同步材料列表");
      });
    return () => {
      active = false;
    };
  }, [setMaterials]);

  // 实际执行上传
  const handleUpload = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    setStage("uploading");
    setUploadingCount(files.length);
    setFailedFiles([]);
    const newMaterials: Material[] = [];
    const failed: UploadFailure[] = [];

    for (const file of files) {
      try {
        const mat = await apiUploadMaterial(file);
        addMaterial(mat);
        // The backend keeps a failed material record so the error remains inspectable.
        if (mat.status === "failed" || mat.status === "error") {
          failed.push({ filename: file.name, reason: mat.error_message || "服务器解析失败" });
          continue;
        }
        newMaterials.push(mat);
      } catch (err) {
        const reason = err instanceof Error ? err.message : "未知上传错误";
        failed.push({ filename: file.name, reason });
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
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    await handleUpload(files);
  }, [handleUpload]);

  // 删除单个材料
  const handleDelete = async (fileId: string) => {
    try {
      await apiDeleteMaterial(fileId);
      removeMaterial(fileId);
      if (selectedMaterial?.file_id === fileId) {
        setSelectedMaterial(null);
        setSelectedChunks([]);
      }
      message.success("已删除");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "删除失败");
    }
  };

  const handleInspect = async (material: Material) => {
    setSelectedMaterial(material);
    setSelectedChunks([]);
    setChunksLoading(true);
    try {
      setSelectedChunks(await apiGetMaterialChunks(material.file_id));
    } catch (error) {
      message.error(error instanceof Error ? error.message : "读取解析片段失败");
    } finally {
      setChunksLoading(false);
    }
  };

  // 继续到澄清页
  const handleNext = () => {
    const usableMaterials = materials.filter(isMaterialUsable);
    if (usableMaterials.length === 0) {
      message.warning("请至少上传一份参考资料");
      return;
    }
    setCurrentStep("clarify");
    navigate("/clarify");
  };

  const totalFiles = materials.length;
  const parsedFiles = materials.filter((m) => m.status === "parsed").length;
  const usableFiles = materials.filter(isMaterialUsable).length;
  const failedCount = failedFiles.length;

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>📂 课程资料上传</Title>
        <Text type="secondary">上传 PDF、Office、图片或视频，解析结果可直接检查</Text>
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
        <Col xs={24} lg={14}>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={SUPPORTED_FILE_ACCEPT}
            style={{ display: "none" }}
            onChange={(e) => {
              const files = Array.from(e.currentTarget.files || []);
              void handleUpload(files);
              // Allow selecting the same file again after a failed attempt.
              e.currentTarget.value = "";
            }}
          />
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
                fileInputRef.current?.click();
              }}
            >
              <CloudUploadOutlined style={{ fontSize: 48, color: "#1890ff", marginBottom: 8 }} />
              <div>
                <Text strong style={{ fontSize: 15 }}>拖拽文件到此处，或点击选择文件</Text>
              </div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                支持 PDF / PPTX / DOCX / Markdown / 图片 / MP4 / 音频，单文件 ≤ 50MB
              </Text>
            </div>

            {/* 上传进度 */}
            {stage === "uploading" && (
              <Alert
                type="info"
                icon={<Spin size="small" />}
                message={`正在上传并解析 ${uploadingCount} 个文件...`}
                style={{ marginBottom: 12 }}
              />
            )}

            {failedCount > 0 && (
              <Alert
                type="error"
                message={`${failedCount} 个文件上传失败，请重试`}
                description={
                  <div>
                    {failedFiles.map(({ filename, reason }) => (
                      <div key={`${filename}-${reason}`}>
                        {filename}：{reason}
                      </div>
                    ))}
                  </div>
                }
                style={{ marginBottom: 12 }}
              />
            )}

            {syncWarning && (
              <Alert
                type="warning"
                message="服务器材料列表同步失败，当前显示本地缓存"
                description={syncWarning}
                style={{ marginBottom: 12 }}
                closable
                onClose={() => setSyncWarning(null)}
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
                        key="inspect"
                        type="link"
                        size="small"
                        icon={<FileSearchOutlined />}
                        onClick={() => void handleInspect(item)}
                      >
                        查看解析
                      </Button>,
                      <Button
                        key="del"
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                         onClick={() => void handleDelete(item.file_id)}
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
                        <Text
                          type={item.status === "failed" || item.status === "error" ? "danger" : "warning"}
                          style={{ fontSize: 11 }}
                        >
                          {item.error_message}
                        </Text>
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
        <Col xs={24} lg={10} style={{ marginTop: 16 }}>
          <Card size="small" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic title="已上传" value={totalFiles} suffix="个文件" />
              </Col>
              <Col span={12}>
                <Statistic
                  title="可用于备课"
                  value={usableFiles}
                  suffix={`/ ${totalFiles}`}
                  valueStyle={{ color: usableFiles === totalFiles && totalFiles > 0 ? "#52c41a" : "#888" }}
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
                  <Text>已准备好 {usableFiles} 个参考材料，其中 {parsedFiles} 个包含解析片段</Text>
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

      <Drawer
        title={selectedMaterial ? `解析结果：${selectedMaterial.filename}` : "解析结果"}
        width={640}
        open={Boolean(selectedMaterial)}
        onClose={() => {
          setSelectedMaterial(null);
          setSelectedChunks([]);
        }}
      >
        {selectedMaterial && (
          <>
            <Descriptions size="small" column={2} bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLOR[selectedMaterial.status] || "default"}>
                  {STATUS_TEXT[selectedMaterial.status] || selectedMaterial.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="解析片段">{selectedMaterial.chunk_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="格式">{selectedMaterial.extension?.toUpperCase() || "未知"}</Descriptions.Item>
              <Descriptions.Item label="大小">
                {selectedMaterial.size != null ? `${(selectedMaterial.size / 1024).toFixed(1)} KB` : "未知"}
              </Descriptions.Item>
            </Descriptions>

            {selectedMaterial.error_message && (
              <Alert
                type={selectedMaterial.status === "failed" || selectedMaterial.status === "error" ? "error" : "warning"}
                message={selectedMaterial.status === "failed" ? "解析失败" : "解析提示"}
                description={selectedMaterial.error_message}
                style={{ marginBottom: 16 }}
              />
            )}

            {chunksLoading ? (
              <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
            ) : selectedChunks.length === 0 ? (
              <Empty description="该材料没有可展示的文本片段" />
            ) : (
              <List
                dataSource={selectedChunks}
                renderItem={(chunk) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <Space wrap>
                          <Text>片段 {chunk.chunk_index + 1}</Text>
                          <Tag>{chunk.modality}</Tag>
                          {getChunkSourceLabel(chunk) && <Tag color="blue">{getChunkSourceLabel(chunk)}</Tag>}
                        </Space>
                      }
                      description={
                        <Paragraph ellipsis={{ rows: 4, expandable: true, symbol: "展开" }} style={{ marginBottom: 0 }}>
                          {chunk.content}
                        </Paragraph>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </>
        )}
      </Drawer>
    </div>
  );
}
