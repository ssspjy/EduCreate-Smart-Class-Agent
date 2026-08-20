// pages/UploadPage.tsx — 步骤 1：上传参考资料
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, Button, List, message, Typography } from "antd";
import { InboxOutlined, DeleteOutlined, RightOutlined } from "@ant-design/icons";
import { useWorkflowStore } from "../stores/workflow";
import { apiUploadMaterial } from "../services/api";

const { Title, Text } = Typography;
const { Dragger } = Upload;

export default function UploadPage() {
  const { materials, addMaterial, setCurrentStep } = useWorkflowStore();
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const result = await apiUploadMaterial(file);
      addMaterial(result);
      message.success(`${file.name} 上传成功`);
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "上传失败";
      message.error(errMsg);
    } finally {
      setUploading(false);
    }
    return false; // 阻止默认上传
  };

  const canProceed = materials.length > 0;
  const goNext = () => {
    setCurrentStep("clarify");
    navigate("/clarify");
  };

  return (
    <div className="page">
      <Title level={3}>步骤 1 / 5：上传参考资料</Title>
      <Text type="secondary">上传 PDF、Word、PPT、图片或视频，系统将解析内容用于后续生成。</Text>

      <Dragger
        accept=".pdf,.doc,.docx,.ppt,.pptx,.png,.jpg,.jpeg,.mp4"
        showUploadList={false}
        beforeUpload={handleUpload}
        disabled={uploading}
        style={{ marginTop: 24 }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽上传文件</p>
        <p className="ant-upload-hint">支持 PDF、Word、PowerPoint</p>
      </Dragger>

      {materials.length > 0 && (
        <List
          style={{ marginTop: 16 }}
          header={<Text strong>已上传 ({materials.length})</Text>}
          bordered
          dataSource={materials}
          renderItem={(item) => (
            <List.Item
              actions={[
                <DeleteOutlined
                  key="del"
                  onClick={() =>
                    useWorkflowStore.getState().clearMaterials()
                  }
                />,
              ]}
            >
              <List.Item.Meta
                title={item.filename}
                description={`ID: ${item.file_id} · 状态: ${item.status}`}
              />
            </List.Item>
          )}
        />
      )}

      <Button
        type="primary"
        icon={<RightOutlined />}
        disabled={!canProceed}
        onClick={goNext}
        style={{ marginTop: 24 }}
      >
        下一步：教学意图澄清
      </Button>
    </div>
  );
}
