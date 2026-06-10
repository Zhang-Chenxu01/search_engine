import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Layout,
  Menu,
  Button,
  Space,
  Avatar,
  Dropdown,
  Typography,
} from "antd";
import {
  HomeOutlined,
  SearchOutlined,
  FileTextOutlined,
  HistoryOutlined,
  DashboardOutlined,
  UserOutlined,
  LoginOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import type { UserInfo } from "../types";
import { getMe } from "../services/api";

const { Header, Content, Footer } = Layout;
const { Text } = Typography;

export default function MainLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then((res) => {
        if (res.code === 0 && res.data) setUser(res.data);
      })
      .catch(() => localStorage.removeItem("access_token"))
      .finally(() => setLoading(false));
  }, [location.pathname]);

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    setUser(null);
    navigate("/");
  };

  const selectedKey = (() => {
    const p = location.pathname;
    if (p === "/") return "home";
    if (p.startsWith("/search")) return "search";
    if (p.startsWith("/documents")) return "documents";
    if (p.startsWith("/history")) return "history";
    if (p.startsWith("/dashboard")) return "dashboard";
    return "";
  })();

  const menuItems = [
    { key: "home", icon: <HomeOutlined />, label: <Link to="/">首页</Link> },
    {
      key: "search",
      icon: <SearchOutlined />,
      label: <Link to="/search">网页搜索</Link>,
    },
    {
      key: "documents",
      icon: <FileTextOutlined />,
      label: <Link to="/documents">文档搜索</Link>,
    },
    {
      key: "history",
      icon: <HistoryOutlined />,
      label: <Link to="/history">查询历史</Link>,
    },
    {
      key: "dashboard",
      icon: <DashboardOutlined />,
      label: <Link to="/dashboard">系统统计</Link>,
    },
  ];

  const userMenuItems = user
    ? [
        {
          key: "profile",
          label: (
            <span>
              {user.username}
              <Text type="secondary" style={{ marginLeft: 8 }}>
                {user.role}
              </Text>
            </span>
          ),
          disabled: true,
        },
        { type: "divider" as const },
        {
          key: "logout",
          icon: <LogoutOutlined />,
          label: "退出登录",
          onClick: handleLogout,
        },
      ]
    : [
        {
          key: "login",
          icon: <LoginOutlined />,
          label: "登录 / 注册",
          onClick: () => navigate("/login"),
        },
      ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          background: "#001529",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Link
            to="/"
            style={{
              color: "#fff",
              fontSize: 18,
              fontWeight: 700,
              marginRight: 16,
              whiteSpace: "nowrap",
            }}
          >
            南开搜索
          </Link>
          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[selectedKey]}
            items={menuItems}
            style={{ flex: 1, minWidth: 480 }}
          />
        </div>
        <Space>
          {!loading && (
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button
                type="text"
                icon={<Avatar size="small" icon={<UserOutlined />} />}
                style={{ color: "#fff" }}
              >
                {user ? user.username : "未登录"}
              </Button>
            </Dropdown>
          )}
        </Space>
      </Header>
      <Content style={{ padding: "24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        <Outlet />
      </Content>
      <Footer style={{ textAlign: "center", color: "#999" }}>
        南开大学搜索引擎 · Nankai Search Engine © 2026
      </Footer>
    </Layout>
  );
}
