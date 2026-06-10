/** Unified API response wrapper. */
export interface ApiResponse<T = unknown> {
  code: number;
  data: T;
  message: string;
}

/** Paginated response. */
export interface PaginatedData<T> {
  total: number;
  page: number;
  page_size: number;
  data: T[];
}

/** A single search result. */
export interface SearchResultItem {
  page_id: number;
  url: string;
  title: string;
  snippet: string;
  source_site: string;
  category: string;
  publish_time: string | null;
  snapshot_path: string;
  bm25_score: number | null;
  vsm_score: number;
  pagerank_score: number;
  personalization_score: number;
  final_score: number | null;
  highlight?: Record<string, string[]>;
}

/** User info. */
export interface UserInfo {
  id: number;
  username: string;
  role: string;
  college: string;
  interests: string[];
  created_at: string;
}

/** Login response. */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

/** Query suggestion item. */
export interface SuggestItem {
  query: string;
  count: number;
}

/** Hot query item. */
export interface HotItem {
  query: string;
  count: number;
}

/** Document search result item. */
export interface DocumentSearchItem {
  attachment_id: number;
  file_name: string;
  file_type: string;
  file_url: string;
  parent_title: string;
  parent_url: string;
  parent_page_id: number | null;
  snippet: string;
  crawl_time: string | null;
  score: number | null;
  highlight?: Record<string, string[]>;
}

/** Document detail. */
export interface DocumentDetail {
  id: number;
  file_name: string;
  file_type: string;
  file_url: string;
  local_path: string | null;
  parent_page_id: number | null;
  parent_url: string;
  parent_title: string;
  parse_status: string;
  crawl_time: string | null;
  created_at: string | null;
  text_preview: string;
  text_total_length: number;
}

/** Snapshot HTML content (served as text/html). */

/** Log statistics. */
export interface LogStats {
  total_queries: number;
  today_queries: number;
  user_count: number;
  fulltext_queries: number;
  document_queries: number;
  phrase_queries: number;
  wildcard_queries: number;
}

export interface HotQueryItem {
  query: string;
  count: number;
}

export interface RecentQueryItem {
  id: number;
  query_text: string;
  query_type: string;
  user_id: number | null;
  result_count: number;
  created_at: string | null;
}

export interface TypeDistribution {
  fulltext: number;
  document: number;
  phrase: number;
  wildcard: number;
}

export interface DailyTrendItem {
  date: string;
  count: number;
}

/** Search params. */
export interface SearchParams {
  q: string;
  page?: number;
  page_size?: number;
  source_site?: string;
  category?: string;
}
