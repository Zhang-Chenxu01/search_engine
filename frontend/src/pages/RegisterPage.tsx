import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  Form,
  Input,
  Button,
  Select,
  Card,
  Typography,
  message,
  Space,
} from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { register } from "../services/api";

const { Title, Text } = Typography;

const ROLE_OPTIONS = [
  { value: "undergraduate", label: "本科生" },
  { value: "graduate", label: "研究生" },
  { value: "teacher", label: "教师" },
  { value: "job_seeker", label: "求职者" },
  { value: "visitor", label: "访客" },
];

export default function RegisterPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: {
    username: string;
    password: string;
    role: string;
    college: string;
    interests: string;
  }) => {
    setLoading(true);
    try {
      const interests = values.interests
        ? values.interests.split(/[,，\s]+/).filter(Boolean)
        : [];
      const res = await register({ ...values, interests });
      if (res.code === 0) {
        message.success("注册成功，请登录");
        navigate("/login");
      } else {
        message.error(res.message);
      }
    } catch {
      message.error("注册请求失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 440, margin: "40px auto" }}>
      <Card>
        <Title level={3} style={{ textAlign: "center", marginBottom: 24 }}>
          用户注册
        </Title>
        <Form
          layout="vertical"
          onFinish={onFinish}
          initialValues={{ role: "visitor", college: "" }}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名（2-64 字符）"
              size="large"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 6, message: "密码至少 6 位" },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码（至少 6 位）"
              size="large"
            />
          </Form.Item>
          <Form.Item name="role" label="身份">
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="college" label="学院">
            <Input placeholder="例如：计算机学院" />
          </Form.Item>
          <Form.Item
            name="interests"
            label="兴趣标签"
            extra="用逗号或空格分隔，例如：AI, 实习, 招聘"
          >
            <Input placeholder="AI, 实习, 招聘" />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              block
              size="large"
              loading={loading}
            >
              注册
            </Button>
          </Form.Item>
        </Form>
        <Space style={{ width: "100%", justifyContent: "center" }}>
          <Text type="secondary">已有账号？</Text>
          <Link to="/login">返回登录</Link>
        </Space>
      </Card>
    </div>
  );
}
