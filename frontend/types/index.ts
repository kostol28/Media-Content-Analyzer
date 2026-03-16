export type DatasetPreview = {
  dataset: { id: number; columns: string[]; mapping: Record<string, string>; intake_type: string };
  rows: Record<string, string | boolean>[];
};

export type JobPayload = {
  job: {
    id: number;
    dataset_id: number;
    status: string;
    total_rows: number;
    processed_rows: number;
    success_count: number;
    failure_count: number;
    logs: { ts: string; message: string }[];
  };
  corpus_counts: {
    total_rows: number;
    included_rows: number;
    excluded_rows: number;
    included_with_usable_text: number;
    included_missing_text: number;
  };
  report: Record<string, unknown> | null;
};

export type ArticleRow = {
  row_id: number;
  original_url: string;
  final_url: string | null;
  included: boolean;
  exclusion_reason: string | null;
  extraction_status: string;
  failure_reason: string | null;
  title: string | null;
  text_length: number;
  text_source: 'extracted' | 'manual' | 'missing';
  review_notes: string | null;
};
