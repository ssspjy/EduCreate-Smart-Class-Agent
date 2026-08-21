import { useEffect, useState } from "react";
import { Button, Card, Empty, Select, Space, Table, Tag, Typography, message } from "antd";
import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { apiListGenerationJobs } from "../services/api";
import type { GenerationJob } from "../services/api";

const { Title, Text } = Typography;

const statusLabel: Record<GenerationJob["status"], string> = {
  queued: "排队中",
  generating: "生成中",
  cancelling: "取消中",
  cancelled: "已取消",
  completed: "已完成",
  failed: "失败",
};

export default function GenerationHistoryPage() {
  const [items, setItems] = useState<GenerationJob[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<GenerationJob["status"] | undefined>();
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const result = await apiListGenerationJobs({ status, page, page_size: 20 });
      setItems(result.items);
      setTotal(result.total);
    } catch (error) {
      message.error(`加载生成历史失败：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [status, page]);

  return (
    <div className="page">
      <Card>
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <Space style={{ justifyContent: "space-between", width: "100%" }}>
            <div>
              <Title level={2} style={{ margin: 0 }}>课件生成历史</Title>
              <Text type="secondary">共 {total} 条任务，保留每次生成的状态和下载入口。</Text>
            </div>
            <Space>
              <Select
                allowClear
                placeholder="按状态筛选"
                style={{ width: 140 }}
                value={status}
                onChange={(value) => { setStatus(value); setPage(1); }}
                options={Object.entries(statusLabel).map(([value, label]) => ({ value, label }))}
              />
              <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
            </Space>
          </Space>
          {items.length === 0 && !loading ? <Empty description="暂无生成记录" /> : (
            <Table
              rowKey="job_id"
              loading={loading}
              dataSource={items}
              pagination={{ current: page, pageSize: 20, total, showSizeChanger: false, onChange: setPage }}
              columns={[
                { title: "任务", dataIndex: ["output", "filename"], render: (value: string | undefined, job: GenerationJob) => value || job.job_id.slice(0, 8) },
                { title: "状态", dataIndex: "status", render: (value: GenerationJob["status"]) => <Tag color={value === "completed" ? "success" : value === "failed" ? "error" : value === "cancelled" ? "default" : "processing"}>{statusLabel[value]}</Tag> },
                { title: "进度", dataIndex: "progress", render: (value: number) => `${value}%` },
                { title: "更新时间", dataIndex: "updated_at", render: (value: string) => new Date(value).toLocaleString() },
                { title: "操作", key: "action", render: (_: unknown, job: GenerationJob) => job.output?.url ? <Button type="link" icon={<DownloadOutlined />} href={job.output.url}>下载</Button> : null },
              ]}
            />
          )}
        </Space>
      </Card>
    </div>
  );
}
