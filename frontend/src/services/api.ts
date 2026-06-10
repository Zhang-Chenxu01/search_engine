import axios from "axios";
import type {
  ApiResponse,
  DailyTrendItem,
  DocumentDetail,
  DocumentSearchItem,
  HotItem,
  HotQueryItem,
  LogStats,
  PaginatedData,
  RecentQueryItem,
  SearchResultItem,
  SuggestItem,
  TokenResponse,
  TypeDistribution,
  UserInfo,
} from "../types";

const client = axios.create({
  baseURL: "/api",
  timeout: 15_000,
});

// ── Bearer token interceptor ─────────────────────────────────

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Auth ─────────────────────────────────────────────────────

export async function register(payload: {
  username: string;
  password: string;
  role?: string;
  college?: string;
  interests?: string[];
}) {
  const { data } = await client.post<ApiResponse<UserInfo>>(
    "/auth/register",
    payload,
  );
  return data;
}

export async function login(payload: { username: string; password: string }) {
  const { data } = await client.post<ApiResponse<TokenResponse>>(
    "/auth/login",
    payload,
  );
  if (data.code === 0 && data.data) {
    localStorage.setItem("access_token", data.data.access_token);
  }
  return data;
}

export async function getMe() {
  const { data } = await client.get<ApiResponse<UserInfo>>("/auth/me");
  return data;
}

// ── Search ───────────────────────────────────────────────────

export async function searchPages(params: {
  q: string;
  page?: number;
  page_size?: number;
  source_site?: string;
  category?: string;
}) {
  const { data } = await client.get<ApiResponse<SearchResultItem[]> & PaginatedData<SearchResultItem>>(
    "/search/pages",
    { params },
  );
  return data;
}

export async function searchPhrase(params: {
  q: string;
  page?: number;
  page_size?: number;
  source_site?: string;
  category?: string;
}) {
  const { data } = await client.get<ApiResponse<SearchResultItem[]> & PaginatedData<SearchResultItem>>(
    "/search/phrase",
    { params },
  );
  return data;
}

// ── Recommend ────────────────────────────────────────────────

export async function getSuggestions(q: string) {
  const { data } = await client.get<ApiResponse<SuggestItem[]>>(
    "/recommend/suggest",
    { params: { q } },
  );
  return data;
}

export async function getHotQueries() {
  const { data } = await client.get<ApiResponse<HotItem[]>>("/recommend/hot");
  return data;
}

export async function getRelatedPages(q: string) {
  const { data } = await client.get<ApiResponse<SearchResultItem[]> & PaginatedData<SearchResultItem>>(
    "/recommend/related",
    { params: { q } },
  );
  return data;
}

// ── Snapshot ─────────────────────────────────────────────────

export async function getSnapshotByPageId(pageId: number) {
  const { data } = await client.get<string>(`/snapshots/by-page/${pageId}`);
  return data;
}

// ── Documents ────────────────────────────────────────────────

export async function searchDocuments(params: {
  q: string;
  file_type?: string;
  page?: number;
  page_size?: number;
}) {
  const { data } = await client.get<
    ApiResponse<DocumentSearchItem[]> & PaginatedData<DocumentSearchItem>
  >("/documents/search", { params });
  return data;
}

export async function getDocumentDetail(id: number) {
  const { data } = await client.get<ApiResponse<DocumentDetail>>(
    `/documents/${id}`,
  );
  return data;
}

// ── Logs ─────────────────────────────────────────────────────

export async function getLogStats() {
  const { data } = await client.get<ApiResponse<LogStats>>("/logs/stats");
  return data;
}

export async function getLogHotQueries(limit = 10) {
  const { data } = await client.get<ApiResponse<HotQueryItem[]>>(
    "/logs/hot-queries",
    { params: { limit } },
  );
  return data;
}

export async function getLogRecent(limit = 20) {
  const { data } = await client.get<ApiResponse<RecentQueryItem[]>>(
    "/logs/recent",
    { params: { limit } },
  );
  return data;
}

export async function getLogTypeDistribution() {
  const { data } = await client.get<ApiResponse<TypeDistribution>>(
    "/logs/query-type-distribution",
  );
  return data;
}

export async function getLogDailyTrend(days = 7) {
  const { data } = await client.get<ApiResponse<DailyTrendItem[]>>(
    "/logs/daily-trend",
    { params: { days } },
  );
  return data;
}

// ── History (stub) ───────────────────────────────────────────

export { client };
