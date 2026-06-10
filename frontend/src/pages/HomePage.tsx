import { useNavigate } from "react-router-dom";
import { Input, Typography, Card, Row, Col, Tag } from "antd";
import { SearchOutlined, FireOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getHotQueries } from "../services/api";

const { Title, Paragraph } = Typography;
const { Search } = Input;

export default function HomePage() {
  const navigate = useNavigate();

  const { data: hotData } = useQuery({
    queryKey: ["hotQueries"],
    queryFn: getHotQueries,
  });

  const onSearch = (value: string) => {
    if (value.trim()) {
      navigate(`/search?q=${encodeURIComponent(value.trim())}`);
    }
  };

  return (
    <div style={{ paddingTop: 60, textAlign: "center" }}>
      <Title level={1} style={{ fontSize: 42, marginBottom: 8 }}>
        南开搜索
      </Title>
      <Paragraph type="secondary" style={{ fontSize: 16, marginBottom: 32 }}>
        Nankai Search Engine — 南开大学新闻通知垂直搜索引擎
      </Paragraph>

      <Search
        placeholder="搜索南开大学新闻、通知、公告..."
        allowClear
        enterButton={<><SearchOutlined /> 搜索</>}
        size="large"
        onSearch={onSearch}
        style={{ maxWidth: 640, width: "100%" }}
      />

      {hotData?.data && hotData.data.length > 0 && (
        <Card
          title={<><FireOutlined style={{ color: "#ff4d4f" }} /> 热门搜索</>}
          style={{ maxWidth: 640, margin: "24px auto", textAlign: "left" }}
          size="small"
        >
          <Row gutter={[8, 8]}>
            {hotData.data.slice(0, 8).map((item) => (
              <Col key={item.query}>
                <Tag
                  color="blue"
                  style={{ cursor: "pointer", fontSize: 14, padding: "2px 10px" }}
                  onClick={() => onSearch(item.query)}
                >
                  {item.query}
                  <span style={{ marginLeft: 4, opacity: 0.6, fontSize: 12 }}>
                    {item.count}
                  </span>
                </Tag>
              </Col>
            ))}
          </Row>
        </Card>
      )}
    </div>
  );
}
