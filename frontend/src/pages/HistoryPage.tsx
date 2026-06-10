import { Typography, Card, Empty, Table, Tag } from "antd";
import { HistoryOutlined } from "@ant-design/icons";

const { Title, Paragraph } = Typography;

const mockColumns = [
  { title: "查询词", dataIndex: "query_text", key: "query_text" },
  { title: "类型", dataIndex: "query_type", key: "query_type", width: 80 },
  { title: "结果数", dataIndex: "result_count", key: "result_count", width: 80 },
  { title: "时间", dataIndex: "created_at", key: "created_at", width: 160 },
];

export default function HistoryPage() {
  return (
    <div>
      <Title level={3}>
        <HistoryOutlined /> 查询历史
      </Title>
      <Paragraph type="secondary">
        查看系统全部查询记录，支持分析热门搜索趋势。
      </Paragraph>
      <Card>
        <Empty
          description={
            <span>
              暂无查询记录。
              <br />
              此页面后续将接入后端 <Tag>/api/logs</Tag> 接口展示实时查询历史。
            </span>
          }
        >
          <Table columns={mockColumns} dataSource={[]} />
        </Empty>
      </Card>
    </div>
  );
}
