import { useParams, Link, useNavigate } from "react-router-dom";
import {
  Typography,
  Descriptions,
  Tag,
  Button,
  Space,
  Spin,
  Alert,
  Card,
  Result,
} from "antd";
import {
  DownloadOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileOutlined,
  LinkOutlined,
  ArrowLeftOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { getDocumentDetail } from "../services/api";

const { Title, Text, Paragraph } = Typography;

function fileTypeIcon(ft: string) {
  switch (ft) {
    case "pdf":  return <FilePdfOutlined style={{ color: "#ff4d4f", fontSize: 48 }} />;
    case "docx": return <FileWordOutlined style={{ color: "#1677ff", fontSize: 48 }} />;
    case "xlsx": return <FileExcelOutlined style={{ color: "#52c41a", fontSize: 48 }} />;
    default:     return <FileOutlined style={{ fontSize: 48 }} />;
  }
}

function fileTypeColor(ft: string) {
  switch (ft) {
    case "pdf":  return "red";
    case "docx": return "blue";
    case "xlsx": return "green";
    default:     return "default";
  }
}

function parseStatusTag(status: string) {
  switch (status) {
    case "done":
      return (
        <Tag icon={<CheckCircleOutlined />} color="success">
          已完成
        </Tag>
      );
    case "pending":
      return (
        <Tag icon={<ClockCircleOutlined />} color="warning">
          待处理
        </Tag>
      );
    case "failed":
      return (
        <Tag icon={<ExclamationCircleOutlined />} color="error">
          解析失败
        </Tag>
      );
    default:
      return <Tag>{status}</Tag>;
  }
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["documentDetail", id],
    queryFn: () => getDocumentDetail(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <Spin size="large" tip="加载文档详情..." />
      </div>
    );
  }

  if (isError) {
    return (
      <Result
        status="error"
        title="加载文档失败"
        subTitle={String(error)}
        extra={
          <Button onClick={() => navigate("/documents")}>
            返回文档搜索
          </Button>
        }
      />
    );
  }

  if (!data || data.code !== 0 || !data.data) {
    return (
      <Result
        status="404"
        title="文档未找到"
        subTitle="该文档可能已被删除或尚未索引"
        extra={
          <Button onClick={() => navigate("/documents")}>
            返回文档搜索
          </Button>
        }
      />
    );
  }

  const doc = data.data;

  return (
    <div>
      {/* Header */}
      <Space style={{ marginBottom: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(-1)}
        >
          返回
        </Button>
      </Space>

      {/* File info card */}
      <Card style={{ marginBottom: 16 }}>
        <Space align="start" size={16}>
          {fileTypeIcon(doc.file_type)}
          <div style={{ flex: 1 }}>
            <Title level={4} style={{ marginTop: 0, marginBottom: 8 }}>
              {doc.file_name}
            </Title>
            <Space size={8} wrap style={{ marginBottom: 12 }}>
              <Tag color={fileTypeColor(doc.file_type)}>
                {doc.file_type?.toUpperCase() || "未知"}
              </Tag>
              {parseStatusTag(doc.parse_status)}
            </Space>
            <Space size={16} wrap>
              <a href={doc.file_url} target="_blank" rel="noopener noreferrer">
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                >
                  下载文件
                </Button>
              </a>
              <Link to="/documents">
                <Button>搜索更多文档</Button>
              </Link>
            </Space>
          </div>
        </Space>
      </Card>

      {/* Metadata */}
      <Card title="文档元数据" size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2 }} size="small" bordered>
          <Descriptions.Item label="文档 ID">{doc.id}</Descriptions.Item>
          <Descriptions.Item label="文件类型">
            <Tag color={fileTypeColor(doc.file_type)}>
              {doc.file_type?.toUpperCase() || "未知"}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="解析状态" span={2}>
            {parseStatusTag(doc.parse_status)}
          </Descriptions.Item>
          <Descriptions.Item label="文档 URL" span={2}>
            <a
              href={doc.file_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ wordBreak: "break-all" }}
            >
              <LinkOutlined /> {doc.file_url}
            </a>
          </Descriptions.Item>
          {doc.parent_title && (
            <>
              <Descriptions.Item label="所属网页" span={2}>
                <Text strong>{doc.parent_title}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="网页链接" span={2}>
                <a
                  href={doc.parent_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ wordBreak: "break-all" }}
                >
                  <LinkOutlined /> {doc.parent_url}
                </a>
              </Descriptions.Item>
            </>
          )}
          {doc.parent_page_id && (
            <Descriptions.Item label="网页 ID">
              <Link to={`/snapshot/${doc.parent_page_id}`}>
                {doc.parent_page_id}（查看快照）
              </Link>
            </Descriptions.Item>
          )}
          <Descriptions.Item label="抓取时间">
            {doc.crawl_time
              ? dayjs(doc.crawl_time).format("YYYY-MM-DD HH:mm:ss")
              : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="入库时间">
            {doc.created_at
              ? dayjs(doc.created_at).format("YYYY-MM-DD HH:mm:ss")
              : "—"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Text preview */}
      <Card
        title={
          <Space>
            <span>文本预览</span>
            {doc.text_total_length > 0 && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                （共 {doc.text_total_length.toLocaleString()} 字符，展示前 2000 字符）
              </Text>
            )}
          </Space>
        }
        size="small"
      >
        {doc.text_preview ? (
          <Paragraph
            style={{
              whiteSpace: "pre-wrap",
              background: "#fafafa",
              padding: 16,
              borderRadius: 6,
              maxHeight: 500,
              overflow: "auto",
              fontFamily:
                "'SF Mono', 'Fira Code', 'Consolas', monospace",
              fontSize: 13,
              lineHeight: 1.8,
              marginBottom: 0,
            }}
          >
            {doc.text_preview}
          </Paragraph>
        ) : doc.parse_status === "pending" ? (
          <Alert
            type="info"
            message="文档尚未解析"
            description="该文档的文本内容尚未提取，请等待系统后台完成解析后刷新页面。"
            showIcon
          />
        ) : doc.parse_status === "failed" ? (
          <Alert
            type="warning"
            message="文本解析失败"
            description="系统无法从该文件中提取文本内容。您仍可下载原始文件查看。"
            showIcon
          />
        ) : (
          <Text type="secondary">暂无文本预览</Text>
        )}
      </Card>
    </div>
  );
}
