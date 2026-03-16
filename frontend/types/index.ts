export type DatasetPreview = {
  dataset: { id: number; columns: string[]; mapping: Record<string, string> };
  rows: Record<string, string>[];
};

export type JobPayload = {
  job: {
    id: number;
    status: string;
    total_rows: number;
    processed_rows: number;
    success_count: number;
    failure_count: number;
    logs: { ts: string; message: string }[];
  };
  report: Record<string, unknown> | null;
};

export type ArticleRow = {
  fetch_id: number;
  row_id: number;
  original_url: string;
  final_url: string;
  status: string;
  failure_reason: string;
  title: string;
  text_length: number;
  primary_theme: string;
  sentiment: string;
};
