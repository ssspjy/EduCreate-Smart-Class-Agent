import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Alert, Button, Card, Form, Input, Typography, message } from "antd";
import { apiLogin } from "../services/api";

const { Title, Text } = Typography;

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || "/";

  const handleSubmit = async (values: { username: string; password: string }) => {
    setLoading(true);
    setError(null);
    try {
      await apiLogin(values.username, values.password);
      message.success("登录成功");
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page" style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <Card style={{ width: 420, maxWidth: "100%" }}>
        <Title level={3} style={{ marginTop: 0 }}>师创智课</Title>
        <Text type="secondary">教师工作台登录</Text>
        {error && <Alert type="error" showIcon message={error} style={{ marginTop: 16 }} />}
        <Form layout="vertical" onFinish={handleSubmit} style={{ marginTop: 20 }}>
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input autoComplete="username" placeholder="demo-teacher" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
