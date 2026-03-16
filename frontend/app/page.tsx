'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { ArticleRow, DatasetPreview, JobPayload } from '../types';

const canonicalFields = ['url', 'title', 'source', 'date', 'author', 'brand', 'tags'];

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [urlsText, setUrlsText] = useState('');
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<JobPayload | null>(null);
  const [articles, setArticles] = useState<ArticleRow[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [manualText, setManualText] = useState('');
  const [notes, setNotes] = useState('');
  const [excludeReason, setExcludeReason] = useState('');

  const failures = useMemo(() => articles.filter((a) => a.text_source === 'missing'), [articles]);

  async function uploadCsv() {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    const res = await api('/datasets/upload', { method: 'POST', body: fd });
    const payload = await res.json();
    setDatasetId(payload.dataset_id);
    await loadPreview(payload.dataset_id);
  }

  async function intakeUrls() {
    const urls = urlsText.split('\n').map((x) => x.trim()).filter(Boolean);
    if (!urls.length) return;
    const res = await api('/datasets/intake-urls', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'pasted_urls', urls }),
    });
    const payload = await res.json();
    setDatasetId(payload.dataset_id);
    await loadPreview(payload.dataset_id);
  }

  async function loadPreview(id: number) {
    const p = await (await api(`/datasets/${id}`)).json();
    setPreview(p);
    setMapping(p.dataset.mapping || {});
  }

  async function saveMapping() {
    if (!datasetId) return;
    await api(`/datasets/${datasetId}/mapping`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mapping }) });
    await loadPreview(datasetId);
  }

  async function runExtraction() {
    if (!datasetId) return;
    const body: Record<string, string> = {};
    if (startDate && endDate) {
      body.start_date = new Date(startDate).toISOString();
      body.end_date = new Date(endDate).toISOString();
    }
    const payload = await (await api(`/datasets/${datasetId}/jobs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json();
    setJobId(payload.job_id);
  }

  async function refreshJob() {
    if (!jobId) return;
    setJob(await (await api(`/jobs/${jobId}`)).json());
    setArticles(await (await api(`/jobs/${jobId}/articles`)).json());
  }

  async function loadDetail(rowId: number) {
    const d = await (await api(`/rows/${rowId}`)).json();
    setDetail({ rowId, ...d });
    setManualText(d.manual_article_text || '');
    setNotes(d.review_notes || '');
    setExcludeReason(d.exclusion_reason || '');
  }

  async function saveReview(included: boolean) {
    if (!detail) return;
    await api(`/rows/${detail.rowId}/review`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ included, exclusion_reason: included ? null : excludeReason, manual_article_text: manualText, review_notes: notes }),
    });
    await loadDetail(detail.rowId);
    await refreshJob();
  }

  async function runFinalAnalysis() {
    if (!jobId) return;
    await api(`/jobs/${jobId}/analyze`, { method: 'POST' });
    await refreshJob();
  }

  useEffect(() => {
    if (!jobId) return;
    refreshJob();
    const t = setInterval(refreshJob, 4000);
    return () => clearInterval(t);
  }, [jobId]);

  return (
    <div className="container">
      <h1>Post-Curation Media Analyzer</h1>
      <div className="card">
        <h3>1) Intake cleaned article list</h3>
        <div className="grid">
          <div>
            <h4>CSV upload</h4>
            <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <button onClick={uploadCsv}>Upload CSV</button>
          </div>
          <div>
            <h4>Paste URLs</h4>
            <textarea rows={8} placeholder="One URL per line" value={urlsText} onChange={(e) => setUrlsText(e.target.value)} />
            <button onClick={intakeUrls}>Create records from pasted URLs</button>
          </div>
        </div>
      </div>

      {preview && (
        <>
          <div className="card">
            <h3>2) Column mapping (for CSV)</h3>
            <div className="grid">
              {canonicalFields.map((field) => (
                <label key={field}>{field}
                  <select value={mapping[field] || ''} onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}>
                    <option value="">-- none --</option>
                    {preview.dataset.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
              ))}
            </div>
            <button onClick={saveMapping}>Save Mapping</button>
          </div>

          <div className="card">
            <h3>3) Auto extraction</h3>
            <div className="row">
              <label>Start (optional)<input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
              <label>End (optional)<input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
            </div>
            <button onClick={runExtraction}>Run extraction pipeline</button>
          </div>
        </>
      )}

      {job && (
        <>
          <div className="card">
            <h3>4) Extraction + corpus readiness</h3>
            <p>Status: <b>{job.job.status}</b> | Processed: {job.job.processed_rows}/{job.job.total_rows}</p>
            <p>Included: {job.corpus_counts.included_rows} | Excluded: {job.corpus_counts.excluded_rows} | Included with usable text: {job.corpus_counts.included_with_usable_text} | Included missing text: {job.corpus_counts.included_missing_text}</p>
            <button onClick={runFinalAnalysis}>Run analysis on final included corpus</button>
          </div>

          <div className="card">
            <h3>5) Review table</h3>
            <table>
              <thead><tr><th>Include</th><th>URL</th><th>Extract</th><th>Text source</th><th>Len</th><th>Failure</th><th/></tr></thead>
              <tbody>
                {articles.map((a) => (
                  <tr key={a.row_id}>
                    <td>{a.included ? 'included' : 'excluded'}</td>
                    <td>{a.final_url || a.original_url}</td>
                    <td>{a.extraction_status}</td>
                    <td>{a.text_source}</td>
                    <td>{a.text_length}</td>
                    <td>{a.failure_reason || '-'}</td>
                    <td><button onClick={() => loadDetail(a.row_id)}>Review/Edit</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3>6) Missing text queue</h3>
            <p>{failures.length} rows currently missing usable text.</p>
          </div>

          <div className="card">
            <h3>7) Batch analysis</h3>
            <pre>{JSON.stringify(job.report || {}, null, 2)}</pre>
            <div className="row">
              <a href={`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api'}/jobs/${job.job.id}/export/enriched.csv`} target="_blank">Export enriched CSV</a>
              <a href={`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api'}/jobs/${job.job.id}/export/failures.csv`} target="_blank">Export failures CSV</a>
              <a href={`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api'}/jobs/${job.job.id}/export/aggregate.json`} target="_blank">Export aggregate JSON</a>
              <a href={`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api'}/jobs/${job.job.id}/export/report.md`} target="_blank">Export markdown report</a>
            </div>
          </div>
        </>
      )}

      {detail && (
        <div className="card">
          <h3>Article review</h3>
          <pre>{JSON.stringify(detail.url_info, null, 2)}</pre>
          <label>Manual text override (use when extraction failed/incomplete)</label>
          <textarea rows={10} value={manualText} onChange={(e) => setManualText(e.target.value)} />
          <label>Review notes</label>
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          <label>Exclusion reason</label>
          <input value={excludeReason} onChange={(e) => setExcludeReason(e.target.value)} />
          <div className="row">
            <button onClick={() => saveReview(true)}>Include / Restore</button>
            <button onClick={() => saveReview(false)}>Exclude / Remove</button>
          </div>
          <h4>Current text</h4>
          <textarea rows={10} value={detail.article_text || ''} readOnly />
          <h4>Analysis</h4>
          <pre>{JSON.stringify(detail.analysis, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
