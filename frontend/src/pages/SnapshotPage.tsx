import { useParams } from "react-router-dom";
import { Typography, Spin, Alert, Card } from "antd";
import { CameraOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getSnapshotByPageId } from "../services/api";

const { Title } = Typography;

export default function SnapshotPage() {
  const { id } = useParams<{ id: string }>();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["snapshot", id],
    queryFn: () => getSnapshotByPageId(Number(id)),
    enabled: !!id,
  });

  return (
    <div>
      <Title level={3}>
        <CameraOutlined /> 网页快照 #{id}
      </Title>

      {isLoading && (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin size="large" />
        </div>
      )}

      {isError && (
        <Alert
          type="error"
          message="加载快照失败"
          description={String(error)}
          showIcon
        />
      )}

      {data && (
        <Card
          size="small"
          styles={{ body: { padding: 0 } }}
          style={{ border: "1px solid #d9d9d9" }}
        >
          <iframe
            srcDoc={data}
            title="网页快照"
            sandbox="allow-same-origin"
            style={{
              width: "100%",
              height: "80vh",
              border: "none",
            }}
          />
        </Card>
      )}
    </div>
  );
}
