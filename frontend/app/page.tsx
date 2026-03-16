'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { ArticleRow, DatasetPreview, JobPayload } from '../types';

const canonicalFields = ['url', 'title', 'source', 'date', 'author', 'brand', 'tags'];

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<JobPayload | null>(null);
  const [articles, setArticles] = useState<ArticleRow[]>([]);
  const [detail, setDetail] = useState<any>(null);

  const failures = useMemo(() => articles.filter((a) => a.status === 'failed'), [articles]);

  async function upload() {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    const res = await api('/datasets/upload', { method: 'POST', body: fd });
    const payload = await res.json();
    setDatasetId(payload.dataset_id);
    await loadPreview(payload.dataset_id);
  }

  async function loadPreview(id: number) {
    const res = await api(`/datasets/${id}`);
    const p = await res.json();
    setPreview(p);
    setMapping(p.dataset.mapping || {});
  }

  async function saveMapping() {
    if (!datasetId) return;
    await api(`/datasets/${datasetId}/mapping`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mapping }),
    });
    await loadPreview(datasetId);
  }

  async function runExtraction() {
    if (!datasetId || !startDate || !endDate) return;
    const res = await api(`/datasets/${datasetId}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start_date: new Date(startDate).toISOString(), end_date: new Date(endDate).toISOString() }),
    });
    const payload = await res.json();
    setJobId(payload.job_id);
  }

  async function refreshJob() {
    if (!jobId) return;
    const res = await api(`/jobs/${jobId}`);
    const payload = await res.json();
    setJob(payload);
    const articlesRes = await api(`/jobs/${jobId}/articles`);
    setArticles(await articlesRes.json());
  }

  async function loadDetail(fetchId: number) {
    const res = await api(`/articles/${fetchId}`);
    setDetail(await res.json());
  }

  useEffect(() => {
    if (!jobId) return;
    refreshJob();
    const t = setInterval(refreshJob, 4000);
    return () => clearInterval(t);
  }, [jobId]);

  return (
    <div className="container">
      <h1>Media Content Analyzer</h1>
      <div className="card">
        <h3>1) Upload CSV</h3>
        <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button onClick={upload}>Upload</button>
      </div>

      {preview && (
        <>
          <div className="card">
            <h3>2) Column Mapping</h3>
            <div className="grid">
              {canonicalFields.map((field) => (
                <label key={field}>
                  {field}
                  <select value={mapping[field] || ''} onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}>
                    <option value="">-- none --</option>
                    {preview.dataset.columns.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <button onClick={saveMapping}>Save Mapping</button>
          </div>

          <div className="card">
            <h3>3) Date Range & Run Extraction</h3>
            <div className="row">
              <label>Start<input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label>
              <label>End<input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label>
            </div>
            <button onClick={runExtraction}>Run Extraction</button>
          </div>

          <div className="card">
            <h3>Dataset Preview</h3>
            <table>
              <thead><tr>{preview.dataset.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
              {preview.rows.slice(0, 10).map((r, idx) => (
                <tr key={idx}>{preview.dataset.columns.map((c) => <td key={c}>{r[c]}</td>)}</tr>
              ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {job && (
        <>
          <div className="card">
            <h3>4) Job Progress Dashboard</h3>
            <p>Status: <b>{job.job.status}</b></p>
            <p>{job.job.processed_rows} / {job.job.total_rows} processed | ✅ {job.job.success_count} | ❌ {job.job.failure_count}</p>
            <details><summary>Logs</summary><pre>{job.job.logs.map((l) => `${l.ts} ${l.message}`).join('\n')}</pre></details>
          </div>

          <div className="card">
            <h3>5) Article Results Table</h3>
            <table>
              <thead><tr><th>Title</th><th>Status</th><th>Theme</th><th>Sentiment</th><th>URL</th><th/></tr></thead>
              <tbody>{articles.map((a) => (
                <tr key={a.fetch_id}>
                  <td>{a.title}</td>
                  <td className={a.status === 'success' ? 'status-success' : 'status-failed'}>{a.status}</td>
                  <td>{a.primary_theme}</td>
                  <td>{a.sentiment}</td>
                  <td>{a.final_url || a.original_url}</td>
                  <td><button onClick={() => loadDetail(a.fetch_id)}>View</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>

          <div className="card">
            <h3>6) Failure Log</h3>
            <table><thead><tr><th>URL</th><th>Reason</th></tr></thead><tbody>
              {failures.map((f) => <tr key={f.fetch_id}><td>{f.original_url}</td><td>{f.failure_reason}</td></tr>)}
            </tbody></table>
          </div>

          <div className="card">
            <h3>7) Batch Analysis Dashboard</h3>
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
          <h3>8) Article Detail</h3>
          <h4>Metadata</h4>
          <pre>{JSON.stringify(detail.metadata, null, 2)}</pre>
          <h4>URL Audit</h4>
          <pre>{JSON.stringify(detail.url_info, null, 2)}</pre>
          <h4>Extracted Text</h4>
          <textarea rows={12} value={detail.article_text || ''} readOnly />
          <h4>Structured AI Analysis</h4>
          <pre>{JSON.stringify(detail.analysis, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
