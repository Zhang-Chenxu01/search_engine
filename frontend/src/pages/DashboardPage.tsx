import { Typography, Card, Row, Col, Statistic, Table, Tag, Progress, Spin, Alert } from "antd";
import {
  DashboardOutlined,
  DatabaseOutlined,
  SearchOutlined,
  FileTextOutlined,
  UserOutlined,
  FireOutlined,
  ClockCircleOutlined,
  BarChartOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import {
  getLogStats,
  getLogHotQueries,
  getLogRecent,
  getLogTypeDistribution,
  getLogDailyTrend,
} from "../services/api";
import type { HotQueryItem, RecentQueryItem, DailyTrendItem, TypeDistribution } from "../types";

const { Title, Paragraph, Text } = Typography;

const QUERY_TYPE_LABELS: Record<string, string> = {
  fulltext: "普通搜索",
  document: "文档搜索",
  phrase: "短语查询",
  wildcard: "通配查询",
};
const QUERY_TYPE_COLORS: Record<string, string> = {
  fulltext: "#1677ff",
  document: "#52c41a",
  phrase: "#faad14",
  wildcard: "#722ed1",
};

export default function DashboardPage() {
  // ── Fetch all data ──────────────────────────────────────────
  const stats = useQuery({ queryKey: ["logStats"], queryFn: getLogStats });
  const hot = useQuery({ queryKey: ["logHot"], queryFn: () => getLogHotQueries(10) });
  const recent = useQuery({ queryKey: ["logRecent"], queryFn: () => getLogRecent(20) });
  const dist = useQuery({ queryKey: ["logDist"], queryFn: getLogTypeDistribution });
  const trend = useQuery({ queryKey: ["logTrend"], queryFn: () => getLogDailyTrend(7) });

  const loading = stats.isLoading || hot.isLoading;

  if (stats.isError) {
    return <Alert type="error" message="加载统计数据失败" description={String(stats.error)} showIcon />;
  }

  const s = stats.data?.data;

  return (
    <div>
      <Title level={3}><DashboardOutlined /> 系统统计</Title>
      <Paragraph type="secondary">搜索引擎运行概况与查询日志分析。</Paragraph>

      {/* ── Stat cards ─────────────────────────────────────── */}
      <Spin spinning={loading}>
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="总查询次数" value={s?.total_queries ?? "-"} prefix={<SearchOutlined />} valueStyle={{ color: "#1677ff" }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="今日查询" value={s?.today_queries ?? "-"} prefix={<ClockCircleOutlined />} valueStyle={{ color: "#52c41a" }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="注册用户" value={s?.user_count ?? "-"} prefix={<UserOutlined />} valueStyle={{ color: "#722ed1" }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="文档搜索" value={s?.document_queries ?? "-"} prefix={<FileTextOutlined />} valueStyle={{ color: "#faad14" }} />
            </Card>
          </Col>
        </Row>
      </Spin>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {/* ── Hot queries ─────────────────────────────────── */}
        <Col xs={24} lg={12}>
          <Card
            title={<><FireOutlined style={{ color: "#ff4d4f" }} /> 热门查询词 Top 10</>}
            size="small"
            loading={hot.isLoading}
          >
            {hot.isError ? (
              <Alert type="error" message="加载失败" banner />
            ) : (
              <Table<HotQueryItem>
                dataSource={hot.data?.data ?? []}
                rowKey="query"
                pagination={false}
                size="small"
                columns={[
                  { title: "#", key: "rank", width: 40, render: (_, __, i) => i + 1 },
                  { title: "关键词", dataIndex: "query", key: "query" },
                  {
                    title: "次数",
                    dataIndex: "count",
                    key: "count",
                    width: 80,
                    render: (v: number) => <Tag color="blue">{v}</Tag>,
                  },
                ]}
                locale={{ emptyText: "暂无数据" }}
              />
            )}
          </Card>
        </Col>

        {/* ── Type distribution ───────────────────────────── */}
        <Col xs={24} lg={12}>
          <Card
            title={<><BarChartOutlined /> 查询类型分布</>}
            size="small"
            loading={dist.isLoading}
          >
            {dist.isError ? (
              <Alert type="error" message="加载失败" banner />
            ) : (
              <div style={{ padding: "8px 0" }}>
                {(["fulltext", "document", "phrase", "wildcard"] as const).map((k) => {
                  const d = (dist.data?.data as TypeDistribution | undefined);
                  const total = d
                    ? d.fulltext + d.document + d.phrase + d.wildcard
                    : 1;
                  const v = d ? d[k] : 0;
                  const pct = total > 0 ? Math.round((v / total) * 100) : 0;
                  return (
                    <Row key={k} align="middle" style={{ marginBottom: 12 }}>
                      <Col flex="100px">
                        <Tag color={QUERY_TYPE_COLORS[k]}>{QUERY_TYPE_LABELS[k]}</Tag>
                      </Col>
                      <Col flex="auto">
                        <Progress percent={pct} strokeColor={QUERY_TYPE_COLORS[k]} size="small" format={() => `${v} 次`} />
                      </Col>
                    </Row>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* ── Recent queries ──────────────────────────────── */}
        <Col xs={24} lg={12}>
          <Card
            title={<><ClockCircleOutlined /> 最近查询记录</>}
            size="small"
            loading={recent.isLoading}
          >
            {recent.isError ? (
              <Alert type="error" message="加载失败" banner />
            ) : (
              <Table<RecentQueryItem>
                dataSource={recent.data?.data ?? []}
                rowKey="id"
                pagination={false}
                size="small"
                columns={[
                  { title: "查询词", dataIndex: "query_text", key: "query_text", ellipsis: true, width: 120 },
                  {
                    title: "类型",
                    dataIndex: "query_type",
                    key: "query_type",
                    width: 80,
                    render: (v: string) => <Tag>{QUERY_TYPE_LABELS[v] || v}</Tag>,
                  },
                  { title: "结果", dataIndex: "result_count", key: "result_count", width: 50 },
                  {
                    title: "时间",
                    dataIndex: "created_at",
                    key: "created_at",
                    width: 100,
                    render: (v: string) => v ? dayjs(v).format("HH:mm:ss") : "-",
                  },
                ]}
                locale={{ emptyText: "暂无数据" }}
                scroll={{ x: 350 }}
              />
            )}
          </Card>
        </Col>

        {/* ── Daily trend ─────────────────────────────────── */}
        <Col xs={24} lg={12}>
          <Card
            title={<><RiseOutlined /> 最近 7 天查询趋势</>}
            size="small"
            loading={trend.isLoading}
          >
            {trend.isError ? (
              <Alert type="error" message="加载失败" banner />
            ) : (
              <Table<DailyTrendItem>
                dataSource={trend.data?.data ?? []}
                rowKey="date"
                pagination={false}
                size="small"
                columns={[
                  {
                    title: "日期",
                    dataIndex: "date",
                    key: "date",
                    width: 120,
                    render: (v: string) => dayjs(v).format("YYYY-MM-DD (ddd)"),
                  },
                  {
                    title: "查询次数",
                    dataIndex: "count",
                    key: "count",
                    width: 100,
                    render: (v: number) => <Tag color="blue">{v}</Tag>,
                  },
                  {
                    title: "趋势",
                    key: "bar",
                    render: (_, row) => {
                      const max = Math.max(...(trend.data?.data ?? []).map((d) => d.count), 1);
                      const pct = Math.round((row.count / max) * 100);
                      return (
                        <div style={{ width: "100%", background: "#f0f0f0", borderRadius: 4, height: 16 }}>
                          <div style={{ width: `${pct}%`, height: 16, borderRadius: 4, background: "#1677ff", minWidth: 2, transition: "width .3s" }} />
                        </div>
                      );
                    },
                  },
                ]}
                locale={{ emptyText: "暂无数据" }}
              />
            )}
          </Card>
        </Col>
      </Row>
      <div></div>
    </div>
  );
}
