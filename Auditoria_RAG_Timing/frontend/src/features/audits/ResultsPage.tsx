import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useParams } from "react-router-dom";
import { api, ResultFilters } from "../../api/client";
import { Button, Card, Input, Select } from "../../components/ui";
import {
  COLORS,
  FREQUENCIES,
  FrequencyLengthBarChart,
  LatencyBoxPlot,
  LENGTHS,
  MeanLatencyHeatmap,
  RequestScatterChart
} from "./AuditCharts";

function milliseconds(value: number | null) {
  return value === null ? "-" : `${value.toFixed(2)} ms`;
}

function duration(value: number | null) {
  if (value === null) return "-";
  if (value < 60) return `${value.toFixed(1)} s`;
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
}

function EvidenceBadge({ value }: { value: string }) {
  const styles: Record<string, string> = {
    strong: "bg-red-100 text-red-800",
    moderate: "bg-amber-100 text-amber-800",
    weak: "bg-sky-100 text-sky-800",
    insufficient: "bg-slate-100 text-slate-600"
  };
  return <span className={`inline-flex rounded px-2 py-1 text-xs font-medium ${styles[value] ?? styles.insufficient}`}>{value}</span>;
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card className="min-h-[112px]">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{detail}</div>
    </Card>
  );
}

export function ResultsPage() {
  const { id } = useParams();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ResultFilters>({});
  const [includeOutliers, setIncludeOutliers] = useState(false);
  const [fromZero, setFromZero] = useState(false);
  const results = useQuery({
    queryKey: ["audit-results", id, page, filters],
    queryFn: () => api.auditResults(id!, page, filters),
    enabled: Boolean(id),
    placeholderData: (previousData) => previousData
  });
  const summary = useQuery({
    queryKey: ["audit-summary", id],
    queryFn: () => api.auditSummary(id!),
    enabled: Boolean(id)
  });

  const items = results.data?.items ?? [];
  const report = summary.data;
  const points = report?.points ?? [];
  const pageCount = Math.max(Math.ceil((results.data?.total ?? 0) / (results.data?.page_size ?? 100)), 1);

  function setFilter(key: keyof ResultFilters, value: string) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  }

  async function download(type: "summary" | "raw") {
    if (!id) return;
    const blob = await api.downloadAuditCsv(id, type);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = type === "summary" ? `audit_${id}_summary.csv` : `audit_${id}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (summary.isLoading || (results.isLoading && !results.data)) {
    return <div className="grid min-h-64 place-items-center text-sm text-slate-500">Building audit report...</div>;
  }
  if (summary.error || results.error || !report) {
    const error = summary.error ?? results.error;
    return <Card><p className="text-sm text-red-700">{error instanceof Error ? error.message : "The report could not be loaded."}</p></Card>;
  }

  return (
    <div className="space-y-4">
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Audit report</h1>
          <p className="mt-1 text-sm text-slate-500">
            {report.metadata.target_name} · {report.metadata.dataset_name}
          </p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>Seed {report.metadata.random_seed}</span>
            <span>{report.metadata.calibration_requests} calibration requests</span>
            <span>Status {report.metadata.status}</span>
            <span>Duration {duration(report.metadata.duration_seconds)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => download("raw")}><Download size={15} className="mr-2 inline" />Raw CSV</Button>
          <Button onClick={() => download("summary")}><Download size={15} className="mr-2 inline" />Summary CSV</Button>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="Successful samples"
          value={`${report.metadata.successful_requests}/${report.metadata.total_requests}`}
          detail={`${report.metadata.error_requests} errors`}
        />
        <MetricCard label="Mean TTFB" value={milliseconds(report.overall.mean_ms)} detail={`Median ${milliseconds(report.overall.median_ms)}`} />
        <MetricCard label="TTFB p95" value={milliseconds(report.overall.p95_ms)} detail={`Std. deviation ${milliseconds(report.overall.std_ms)}`} />
        <MetricCard
          label="Mean full response"
          value={milliseconds(report.overall_full_response.mean_ms)}
          detail={`Median ${milliseconds(report.overall_full_response.median_ms)}`}
        />
        <MetricCard
          label="Filtered outliers"
          value={String(report.overall.outlier_count)}
          detail="Lower and upper 1% filtered"
        />
      </section>

      <Card className="flex flex-wrap items-center justify-between gap-4 py-3">
        <div>
          <div className="text-xs font-medium uppercase text-slate-500">Chart controls</div>
          <p className="mt-1 text-xs text-slate-500">Charts use mean TTFB as the primary comparison metric.</p>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-600">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={includeOutliers} onChange={(event) => setIncludeOutliers(event.target.checked)} />
            Include extreme outliers
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={fromZero} onChange={(event) => setFromZero(event.target.checked)} />
            Start axes at zero
          </label>
        </div>
      </Card>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Mean TTFB by frequency and length</h2>
          <p className="mt-1 text-xs text-slate-500">Grouped comparison with a data-focused vertical scale.</p>
          <FrequencyLengthBarChart groups={report.by_frequency_length} fromZero={fromZero} />
        </Card>
        <Card>
          <h2 className="font-semibold">TTFB over request order</h2>
          <p className="mt-1 text-xs text-slate-500">Zoomable request timeline across the complete audit.</p>
          <RequestScatterChart points={points} includeOutliers={includeOutliers} fromZero={fromZero} />
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <h2 className="font-semibold">Latency distribution</h2>
          <p className="mt-1 text-xs text-slate-500">Native boxplots with quartiles, median, whiskers and optional extreme outliers.</p>
          <LatencyBoxPlot
            groups={report.by_frequency_length}
            points={points}
            includeOutliers={includeOutliers}
            fromZero={fromZero}
          />
        </Card>
        <Card>
          <h2 className="font-semibold">Mean-latency heatmap</h2>
          <p className="mt-1 text-xs text-slate-500">Perceptually uniform color mapping with an explicit numeric scale.</p>
          <MeanLatencyHeatmap
            groups={report.by_frequency_length}
            fromZero={fromZero}
          />
        </Card>
      </section>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">Descriptive statistics</h2>
          </div>
          <div className="text-xs text-slate-500">Primary metric: TTFB</div>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-slate-500">
                <th className="py-2">Frequency</th>
                <th>Length</th>
                <th>Valid n</th>
                <th>Mean</th>
                <th>Median</th>
                <th>Std</th>
                <th>p25</th>
                <th>p75</th>
                <th>p95</th>
                <th>Range</th>
                <th>Outliers</th>
                <th>Errors</th>
              </tr>
            </thead>
            <tbody>
              {report.by_frequency_length.map((group) => (
                <tr key={`${group.frequency}-${group.length}`} className="border-b border-slate-100">
                  <td className="py-2 font-medium" style={{ color: COLORS[group.frequency ?? ""] }}>{group.frequency}</td>
                  <td>{group.length}</td>
                  <td>{group.count}</td>
                  <td>{milliseconds(group.mean_ms)}</td>
                  <td>{milliseconds(group.median_ms)}</td>
                  <td>{milliseconds(group.std_ms)}</td>
                  <td>{milliseconds(group.p25_ms)}</td>
                  <td>{milliseconds(group.p75_ms)}</td>
                  <td>{milliseconds(group.p95_ms)}</td>
                  <td>{milliseconds(group.min_ms)} - {milliseconds(group.max_ms)}</td>
                  <td>{group.outlier_count}</td>
                  <td>{group.error_count} ({(group.error_rate * 100).toFixed(1)}%)</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold">Statistical comparisons by frequency</h2>
        <p className="mt-1 text-xs text-slate-500">
          The p-value comes from Welch&apos;s test. Lower values indicate stronger evidence of a temporal difference.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-slate-500">
                <th className="py-2">Groups</th>
                <th>Mean difference</th>
                <th>Median difference</th>
                <th>P-value</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {report.comparisons.map((comparison) => (
                <tr key={`${comparison.group_a}-${comparison.group_b}`} className="border-b border-slate-100">
                  <td className="py-2">{comparison.group_a} vs {comparison.group_b}</td>
                  <td>{milliseconds(comparison.mean_difference_ms)}</td>
                  <td>{milliseconds(comparison.median_difference_ms)}</td>
                  <td>{comparison.p_value?.toExponential(2) ?? "-"}</td>
                  <td><EvidenceBadge value={comparison.evidence} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Raw requests</h2>
            <p className="mt-1 text-xs text-slate-500">Unmodified measurements retained for traceability and future classification.</p>
            {results.isFetching && <p className="mt-1 text-xs text-slate-500">Updating filters...</p>}
          </div>
          <div className="grid w-full gap-2 sm:grid-cols-2 lg:flex lg:w-auto">
            <Select value={filters.frequency ?? ""} onChange={(event) => setFilter("frequency", event.target.value)}>
              <option value="">All frequencies</option>
              {FREQUENCIES.map((frequency) => <option key={frequency} value={frequency}>{frequency}</option>)}
            </Select>
            <Select value={filters.length ?? ""} onChange={(event) => setFilter("length", event.target.value)}>
              <option value="">All lengths</option>
              {LENGTHS.map((length) => <option key={length} value={length}>{length}</option>)}
            </Select>
            <Select value={filters.is_error ?? ""} onChange={(event) => setFilter("is_error", event.target.value)}>
              <option value="">All outcomes</option>
              <option value="false">success</option>
              <option value="true">error</option>
            </Select>
            <Input className="lg:w-32" value={filters.status_code ?? ""} onChange={(event) => setFilter("status_code", event.target.value)} placeholder="HTTP status" />
          </div>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[1040px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-slate-500">
                <th className="py-2">#</th>
                <th>Frequency</th>
                <th>Length</th>
                <th>TTFB</th>
                <th>Full response</th>
                <th>Size</th>
                <th>Status</th>
                <th>Query</th>
              </tr>
            </thead>
            <tbody>
              {items.map((result) => (
                <tr key={result.id} className="border-b border-slate-100">
                  <td className="py-2">{result.request_index}</td>
                  <td style={{ color: COLORS[result.frequency_tag] }}>{result.frequency_tag}</td>
                  <td>{result.length_tag}</td>
                  <td>{milliseconds(result.ttfb_ms)}</td>
                  <td>{milliseconds(result.full_response_ms)}</td>
                  <td>{result.response_size_bytes === null ? "-" : `${result.response_size_bytes} B`}</td>
                  <td>{result.status_code ?? result.error_type ?? "-"}</td>
                  <td className="max-w-[420px] truncate" title={result.query_text}>{result.query_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</Button>
          <span className="text-sm text-slate-500">Page {page} of {pageCount} · {results.data?.total ?? 0} results</span>
          <Button variant="secondary" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)}>Next</Button>
        </div>
      </Card>
    </div>
  );
}
