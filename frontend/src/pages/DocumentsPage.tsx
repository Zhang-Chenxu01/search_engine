import { useSearchParams, Link } from "react-router-dom";
import {
  Input,
  List,
  Typography,
  Tag,
  Space,
  Empty,
  Spin,
  Card,
  Select,
  Button,
  Row,
  Col,
} from "antd";
import {
  SearchOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileExcelOutlined,
  FileOutlined,
  DownloadOutlined,
  EyeOutlined,
  LinkOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { searchDocuments } from "../services/api";
import type { DocumentSearchItem } from "../types";

const { Text, Paragraph } = Typography;

const FILE_TYPES = [
  { value: "", label: "全部" },
  { value: "pdf", label: "PDF" },
  { value: "docx", label: "DOCX" },
  { value: "xlsx", label: "XLSX" },
];

function fileTypeIcon(ft: string) {
  switch (ft) {
    case "pdf":  return <FilePdfOutlined style={{ color: "#ff4d4f" }} />;
    case "docx": return <FileWordOutlined style={{ color: "#1677ff" }} />;
    case "xlsx": return <FileExcelOutlined style={{ color: "#52c41a" }} />;
    default:     return <FileOutlined />;
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

export default function DocumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") || "";
  const page = Number(searchParams.get("page") || 1);
  const file_type = searchParams.get("file_type") || undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["documents", q, page, file_type],
    queryFn: () =>
      searchDocuments({ q, page, page_size: 10, file_type }),
    enabled: q.length > 0,
  });

  const onSearch = (value: string) => {
    if (value.trim()) {
      setSearchParams({ q: value.trim() });
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 24, textAlign: "center" }}>
        <Input.Search
          defaultValue={q}
          placeholder="搜索附件文档（PDF、Word、Excel 等）..."
          allowClear
          enterButton={<><SearchOutlined /> 搜索文档</>}
          size="large"
          onSearch={onSearch}
          style={{ maxWidth: 640 }}
        />
        <Space style={{ marginTop: 12 }}>
          <Select
            value={file_type || ""}
            onChange={(v) => {
              const params: Record<string, string> = { q, page: "1" };
              if (v) params.file_type = v;
              setSearchParams(params);
            }}
            style={{ width: 120 }}
            options={FILE_TYPES.map((ft) => ({
              value: ft.value,
              label: (
                <Space size={4}>
                  {ft.value ? fileTypeIcon(ft.value) : null}
                  {ft.label}
                </Space>
              ),
            }))}
          />
        </Space>
      </div>

      {!q ? (
        <Empty
          image={<FileOutlined style={{ fontSize: 64, color: "#bfbfbf" }} />}
          description={
            <span>
              输入关键词搜索附件文档
              <br />
              <Text type="secondary">支持 PDF、DOCX、XLSX 格式</Text>
            </span>
          }
        />
      ) : isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin size="large" tip="搜索中..." />
        </div>
      ) : data && data.total > 0 ? (
        <>
          <Text type="secondary" style={{ marginBottom: 16, display: "block" }}>
            找到约 {data.total} 个文档
            {file_type && (
              <Tag color={fileTypeColor(file_type)} style={{ marginLeft: 8 }}>
                {file_type.toUpperCase()}
              </Tag>
            )}
          </Text>
          <List
            itemLayout="vertical"
            dataSource={data.data ?? []}
            renderItem={(item: DocumentSearchItem) => (
              <Card
                style={{ marginBottom: 12 }}
                size="small"
                hoverable
              >
                <Row align="middle" wrap={false}>
                  <Col flex="auto">
                    <Space align="start" size={12}>
                      <span style={{ fontSize: 24, marginTop: 4 }}>
                        {fileTypeIcon(item.file_type)}
                      </span>
                      <div>
                        <a
                          href={item.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontSize: 16, fontWeight: 500 }}
                          dangerouslySetInnerHTML={{ __html: item.file_name || "(无标题)" }}
                        />
                        <div style={{ marginTop: 4 }}>
                          <Space size={4} wrap>
                            <Tag color={fileTypeColor(item.file_type)}>
                              {item.file_type?.toUpperCase() || "未知"}
                            </Tag>
                            {item.parent_title && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                来自：
                                <a
                                  href={item.parent_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  <LinkOutlined /> {item.parent_title.substring(0, 50)}
                                </a>
                              </Text>
                            )}
                          </Space>
                        </div>
                        {item.snippet && (
                          <Paragraph
                            style={{ marginTop: 8, marginBottom: 0, color: "#555" }}
                          >
                            <div
                              dangerouslySetInnerHTML={{ __html: item.snippet }}
                            />
                          </Paragraph>
                        )}
                        {item.crawl_time && (
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            抓取时间：{dayjs(item.crawl_time).format("YYYY-MM-DD HH:mm")}
                          </Text>
                        )}
                      </div>
                    </Space>
                  </Col>
                  <Col flex="160px" style={{ textAlign: "right" }}>
                    <Space direction="vertical" size={8}>
                      <Link to={`/documents/${item.attachment_id}`}>
                        <Button
                          type="link"
                          icon={<EyeOutlined />}
                          size="small"
                        >
                          查看详情
                        </Button>
                      </Link>
                      <a
                        href={item.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Button
                          type="primary"
                          icon={<DownloadOutlined />}
                          size="small"
                          ghost
                        >
                          下载
                        </Button>
                      </a>
                    </Space>
                  </Col>
                </Row>
              </Card>
            )}
          />
        </>
      ) : (
        <Card style={{ textAlign: "center", padding: 48 }}>
          <Empty
            image={<FileOutlined style={{ fontSize: 64, color: "#bfbfbf" }} />}
            description={
              <div>
                <Paragraph style={{ fontSize: 16, marginBottom: 8 }}>
                  未找到相关文档
                </Paragraph>
                <Text type="secondary">
                  可以尝试更换关键词，或
                  <Link to={`/search?q=${encodeURIComponent(q)}`}>
                    搜索普通网页
                  </Link>
                </Text>
              </div>
            }
          />
        </Card>
      )}
    </div>
  );
}
