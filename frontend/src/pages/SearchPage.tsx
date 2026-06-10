import { useSearchParams } from "react-router-dom";
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
} from "antd";
import { SearchOutlined, LinkOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { searchPages } from "../services/api";
import type { SearchResultItem } from "../types";

const { Text, Paragraph } = Typography;

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") || "";
  const page = Number(searchParams.get("page") || 1);
  const category = searchParams.get("category") || undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["search", q, page, category],
    queryFn: () =>
      searchPages({ q, page, page_size: 10, category }),
    enabled: q.length > 0,
  });

  const onSearch = (value: string) => {
    setSearchParams(value.trim() ? { q: value.trim() } : {});
  };

  return (
    <div>
      <div style={{ marginBottom: 24, textAlign: "center" }}>
        <Input.Search
          defaultValue={q}
          placeholder="输入搜索关键词..."
          allowClear
          enterButton={<><SearchOutlined /> 搜索</>}
          size="large"
          onSearch={onSearch}
          style={{ maxWidth: 640 }}
        />
        <Space style={{ marginTop: 12 }}>
          <Select
            allowClear
            placeholder="分类筛选"
            value={category}
            onChange={(v) => {
              const params: Record<string, string> = { q, page: "1" };
              if (v) params.category = v;
              setSearchParams(params);
            }}
            style={{ width: 160 }}
            options={[
              { value: "ywsd", label: "要闻速递" },
              { value: "mtnk", label: "媒体南开" },
              { value: "zhxw", label: "综合新闻" },
              { value: "nkrw", label: "南开人物" },
            ]}
          />
        </Space>
      </div>

      {!q ? (
        <Empty description="请输入搜索关键词" />
      ) : isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : (
        <>
          <Text type="secondary" style={{ marginBottom: 16, display: "block" }}>
            找到约 {data?.total ?? 0} 条结果
          </Text>
          <List
            itemLayout="vertical"
            dataSource={data?.data ?? []}
            renderItem={(item: SearchResultItem) => (
              <Card
                style={{ marginBottom: 12 }}
                size="small"
                hoverable
                onClick={() => window.open(item.url, "_blank")}
              >
                <List.Item style={{ border: "none", padding: 0 }}>
                  <List.Item.Meta
                    title={
                      <Space>
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          dangerouslySetInnerHTML={{ __html: item.title }}
                          style={{ fontSize: 16 }}
                        />
                      </Space>
                    }
                    description={
                      <div>
                        <div
                          style={{
                            color: "#555",
                            marginBottom: 8,
                            lineHeight: 1.6,
                          }}
                          dangerouslySetInnerHTML={{
                            __html: item.snippet || item.title,
                          }}
                        />
                        <Space size={8} wrap>
                          <Tag color="blue">{item.category}</Tag>
                          <Tag>{item.source_site}</Tag>
                          {item.publish_time && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {dayjs(item.publish_time).format("YYYY-MM-DD")}
                            </Text>
                          )}
                          <Space size={2}>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              ES: {item.es_score?.toFixed(1)}
                            </Text>
                            {item.preference_score > 0 && (
                              <Text style={{ fontSize: 11, color: "#52c41a" }}>
                                +{item.preference_score.toFixed(1)}
                              </Text>
                            )}
                            <Text style={{ fontSize: 11, fontWeight: 600 }}>
                              ={item.final_score?.toFixed(1)}
                            </Text>
                          </Space>
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ fontSize: 12 }}
                          >
                            <LinkOutlined /> {item.url.substring(0, 60)}...
                          </a>
                        </Space>
                      </div>
                    }
                  />
                </List.Item>
              </Card>
            )}
          />
        </>
      )}
    </div>
  );
}
