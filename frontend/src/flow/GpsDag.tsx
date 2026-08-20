// flow/GpsDag.tsx — GPS DAG 可视化组件
// 基于 React Flow 渲染后端 build_dag() 输出的节点/边结构
import React, { useEffect, useMemo } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MarkerType,
  Node,
  NodeProps,
  useEdgesState,
  useNodesState,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import { Badge, Card, Progress, Space, Typography, Tooltip } from "antd";

// ── 类型定义 ──────────────────────────────────────────────────────────────────

export interface DagNodeData {
  label: string;
  value: string | string[];
  type: "root" | "slot_filled" | "slot_missing" | "dialogue";
  level: number;
  is_filled: boolean;
  new_in_round: boolean;
  source_turn: number;
}

export interface DagMeta {
  filled_count: number;
  missing_count: number;
  total_slots: number;
  completion: number;
  dialogue_count: number;
  dialogue_collapsed: boolean;
}

export interface DagGraph {
  nodes: (Node<DagNodeData> & { style?: Record<string, string> })[];
  edges: Edge[];
  meta: DagMeta;
}

// ── 自定义节点组件 ─────────────────────────────────────────────────────────────

const { Text } = Typography;

// 通用节点包装
function GpsNode({ data }: NodeProps<DagNodeData>) {
  const isList = Array.isArray(data.value);
  const valueStr = isList
    ? (data.value as string[]).join("；")
    : (data.value as string);

  return (
    <div
      style={{
        border: data.type === "root"
          ? "2px solid #1890ff"
          : data.type === "slot_filled"
            ? "2px solid #52c41a"
            : data.type === "slot_missing"
              ? "2px dashed #d9d9d9"
              : data.type === "dialogue"
                ? data.label.includes("教师")
                  ? "2px solid #1890ff"
                  : "2px solid #52c41a"
                : "2px solid #d9d9d9",
        borderRadius: 8,
        background: data.type === "root"
          ? "#e6f7ff"
          : data.type === "slot_filled"
            ? "#f6ffed"
            : data.type === "slot_missing"
              ? "#fafafa"
              : data.label.includes("教师")
                ? "#e6f7ff"
                : "#f6ffed",
        padding: "8px 12px",
        minWidth: 160,
        maxWidth: 260,
        color: data.type === "slot_missing" ? "#999" : "#000",
      }}
    >
      <Text strong style={{ fontSize: 12, display: "block", marginBottom: 4 }}>
        {data.label}
        {data.new_in_round && (
          <Badge
            count="新"
            size="small"
            style={{ marginLeft: 6, fontSize: 10 }}
          />
        )}
      </Text>
      {valueStr && (
        <Tooltip title={valueStr}>
          <Text
            style={{ fontSize: 11, display: "block" }}
            ellipsis={{ tooltip: false }}
          >
            {valueStr.length > 30 ? valueStr.slice(0, 30) + "…" : valueStr}
          </Text>
        </Tooltip>
      )}
    </div>
  );
}

// 根节点（尺寸更大）
function RootNode({ data }: NodeProps<DagNodeData>) {
  const valueStr = Array.isArray(data.value)
    ? (data.value as string[]).join("；")
    : (data.value as string);

  return (
    <div
      style={{
        border: "2px solid #1890ff",
        borderRadius: 10,
        background: "#e6f7ff",
        padding: "12px 20px",
        minWidth: 200,
        textAlign: "center",
      }}
    >
      <Text type="secondary" style={{ fontSize: 11 }}>
        📚 教学意图
      </Text>
      <div style={{ marginTop: 4 }}>
        <Text strong style={{ fontSize: 14 }}>
          {valueStr || "等待输入…"}
        </Text>
      </div>
    </div>
  );
}

const NODE_TYPE_MAP: Record<string, React.ComponentType<NodeProps<DagNodeData>>> = {
  root: RootNode,
  slot_filled: GpsNode,
  slot_missing: GpsNode,
  dialogue: GpsNode,
};

// ── DAG 元信息面板 ────────────────────────────────────────────────────────────

interface DagMetaPanelProps {
  meta: DagMeta;
}

function DagMetaPanel({ meta }: DagMetaPanelProps) {
  const percent = Math.round(meta.completion * 100);

  return (
    <Card size="small" style={{ marginBottom: 8 }}>
      <Space size="large" wrap>
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>槽位完成度</Text>
          <Progress
            percent={percent}
            size="small"
            status={percent >= 100 ? "success" : "active"}
            style={{ marginTop: 2, marginBottom: 0 }}
          />
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>已填</Text>
          <div><Text strong>{meta.filled_count} / {meta.total_slots}</Text></div>
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>待填</Text>
          <div><Text type="warning">{meta.missing_count} 项</Text></div>
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>对话轮次</Text>
          <div><Text>{meta.dialogue_count} 轮</Text></div>
        </div>
      </Space>
    </Card>
  );
}

// ── 主组件 ─────────────────────────────────────────────────────────────────────

interface GpsDagProps {
  /** 从 GET /api/v1/gps/session/{session_id}/dag 获取的数据 */
  dagData: DagGraph;
  /** 是否在追问后高亮新填充的节点 */
  highlightNew?: boolean;
  height?: number | string;
}

export default function GpsDag({
  dagData,
  highlightNew = true,
  height = 380,
}: GpsDagProps) {
  // 转换节点：注入自定义类型
  const initNodes = useMemo(() => {
    return dagData.nodes.map((n) => {
      const nodeType = n.data?.type || "slot_filled";
      return {
        ...n,
        type: nodeType,
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        // 新填充节点带高亮动画
        className: n.data?.new_in_round && highlightNew ? "dag-node-new" : undefined,
      };
    });
  }, [dagData, highlightNew]);

  const initEdges = useMemo(() => {
    return dagData.edges.map((e) => ({
      ...e,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: e.animated ? "#52c41a" : "#bfbfbf",
      },
      style: {
        stroke: e.animated ? "#52c41a" : "#bfbfbf",
        strokeWidth: e.animated ? 2.5 : 1.5,
      },
      animated: e.animated || false,
    }));
  }, [dagData.edges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges);

  // 当 dagData 变化时更新（多轮对话场景）
  useEffect(() => {
    setNodes(initNodes);
    setEdges(initEdges);
  }, [initNodes, initEdges, setNodes, setEdges]);

  const nodeTypes = useMemo(() => NODE_TYPE_MAP, []);

  if (!dagData.nodes.length && !dagData.edges.length) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#fafafa",
          borderRadius: 8,
          border: "1px dashed #d9d9d9",
        }}
      >
        <Text type="secondary">开始对话后，GPS DAG 将实时可视化呈现</Text>
      </div>
    );
  }

  return (
    <div style={{ height }}>
      {dagData.meta && <DagMetaPanel meta={dagData.meta} />}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        style={{ background: "#fafafa", borderRadius: 8, border: "1px solid #f0f0f0" }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
