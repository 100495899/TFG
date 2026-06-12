import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api, ResultFilters, SummaryGroup } from "../../api/client";
import { Button, Card, Input, Select } from "../../components/ui";

const FREQUENCIES = ["high", "medium", "low"] as const;
const LENGTHS = ["short", "medium", "long"] as const;
const COLORS: Record<string, string> = {
  high: "#15803d",
  medium: "#ca8a04",
  low: "#dc2626"
};

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

function BoxPlot({ groups }: { groups: SummaryGroup[] }) {
  const usable = groups.filter((group) => group.min_ms !== null && group.max_ms !== null);
  const globalMax = Math.max(...usable.map((group) => group.max_ms ?? 0), 1);
  const width = 760;
  const left = 112;
  const plotWidth = 620;
  const rowHeight = 32;
  const height = Math.max(usable.length * rowHeight + 38, 120);
  const x = (value: number | null) => left + ((value ?? 0) / globalMax) * plotWidth;

  if (!usable.length) return <div className="grid h-64 place-items-center text-sm text-slate-500">No valid measurements</div>;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[680px] w-full" role="img" aria-label="TTFB box plots by frequency and length">
        {usable.map((group, index) => {
          const y = 24 + index * rowHeight;
          const color = COLORS[group.frequency ?? ""] ?? "#475569";
          return (
            <g key={`${group.frequency}-${group.length}`}>
              <text x="0" y={y + 4} fontSize="11" fill="#475569">{group.frequency} / {group.length}</text>
              <line x1={x(group.min_ms)} x2={x(group.max_ms)} y1={y} y2={y} stroke="#94a3b8" strokeWidth="1.5" />
              <line x1={x(group.min_ms)} x2={x(group.min_ms)} y1={y - 5} y2={y + 5} stroke="#64748b" />
              <line x1={x(group.max_ms)} x2={x(group.max_ms)} y1={y - 5} y2={y + 5} stroke="#64748b" />
              <rect
                x={x(group.p25_ms)}
                y={y - 8}
                width={Math.max(x(group.p75_ms) - x(group.p25_ms), 1)}
                height="16"
                fill={color}
                fillOpacity="0.28"
                stroke={color}
              />
              <line x1={x(group.median_ms)} x2={x(group.median_ms)} y1={y - 8} y2={y + 8} stroke={color} strokeWidth="2.5" />
            </g>
          );
        })}
        {[0, 0.25, 0.5, 0.75, 1].map((position) => (
          <g key={position}>
            <line
              x1={left + plotWidth * position}
              x2={left + plotWidth * position}
              y1="8"
              y2={height - 24}
              stroke="#e2e8f0"
              strokeDasharray="3 3"
            />
            <text x={left + plotWidth * position} y={height - 5} fontSize="10" textAnchor="middle" fill="#64748b">
              {(globalMax * position).toFixed(0)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function Heatmap({ groups }: { groups: SummaryGroup[] }) {
  const values = groups.flatMap((group) => group.mean_ms === null ? [] : [group.mean_ms]);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  const legendIntensities = [0.12, 0.31, 0.5, 0.69, 0.87];

  return (
    <div>
      <div className="grid grid-cols-[80px_repeat(3,minmax(84px,1fr))] gap-1 text-sm">
        <div />
        {LENGTHS.map((length) => <div key={length} className="pb-2 text-center text-xs font-medium text-slate-500">{length}</div>)}
        {FREQUENCIES.flatMap((frequency) => [
          <div key={`${frequency}-label`} className="flex items-center text-xs font-medium text-slate-600">{frequency}</div>,
          ...LENGTHS.map((length) => {
            const group = groups.find((item) => item.frequency === frequency && item.length === length);
            const value = group?.mean_ms;
            const intensity = value === null || value === undefined ? 0 : 0.12 + ((value - min) / Math.max(max - min, 1)) * 0.75;
            return (
              <div
                key={`${frequency}-${length}`}
                className="grid min-h-16 place-items-center border border-slate-200 text-center"
                style={{ backgroundColor: `rgba(15, 23, 42, ${intensity})`, color: intensity > 0.48 ? "white" : "#0f172a" }}
              >
                <div>
                  <div className="font-semibold">{value === null || value === undefined ? "-" : value.toFixed(1)}</div>
                  <div className="text-[10px] opacity-75">ms</div>
                </div>
              </div>
            );
          })
        ])}
      </div>
      <div className="mt-5">
        <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
          <span>Lower mean · {min.toFixed(1)} ms</span>
          <span>Higher mean · {max.toFixed(1)} ms</span>
        </div>
        <div className="grid h-3 grid-cols-5 overflow-hidden border border-slate-200">
          {legendIntensities.map((intensity) => (
            <div key={intensity} style={{ backgroundColor: `rgba(15, 23, 42, ${intensity})` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ResultsPage() {
  const { id } = useParams();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ResultFilters>({});
  const results = useQuery({
    queryKey: ["audit-results", id, page, filters],
    queryFn: () => api.auditResults(id!, page, filters),
    enabled: Boolean(id)
  });
  const summary = useQuery({
    queryKey: ["audit-summary", id],
    queryFn: () => api.auditSummary(id!),
    enabled: Boolean(id)
  });

  const items = results.data?.items ?? [];
  const report = summary.data;
  const lengthBars = LENGTHS.map((length) => ({
    length,
    ...Object.fromEntries(
      FREQUENCIES.map((frequency) => [
        frequency,
        report?.by_frequency_length.find((group) => group.frequency === frequency && group.length === length)?.mean_ms ?? null
      ])
    )
  }));
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

  if (summary.isLoading || results.isLoading) {
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
        <MetricCard label="Median TTFB" value={milliseconds(report.overall.median_ms)} detail={`Mean ${milliseconds(report.overall.mean_ms)}`} />
        <MetricCard label="TTFB p95" value={milliseconds(report.overall.p95_ms)} detail={`Std. deviation ${milliseconds(report.overall.std_ms)}`} />
        <MetricCard
          label="Median full response"
          value={milliseconds(report.overall_full_response.median_ms)}
          detail={`Mean ${milliseconds(report.overall_full_response.mean_ms)}`}
        />
        <MetricCard
          label="Filtered outliers"
          value={String(report.overall.outlier_count)}
          detail="Upper 1% filtered"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Mean TTFB by frequency and length</h2>
          <p className="mt-1 text-xs text-slate-500">Comparison of the nine groups.</p>
          <ResponsiveContainer width="100%" height={310}>
            <BarChart data={lengthBars} margin={{ top: 20, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="length" />
              <YAxis unit=" ms" />
              <Tooltip formatter={(value: number) => [`${Number(value).toFixed(2)} ms`, "Mean TTFB"]} />
              <Legend />
              {FREQUENCIES.map((frequency) => <Bar key={frequency} dataKey={frequency} fill={COLORS[frequency]} />)}
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h2 className="font-semibold">TTFB over request order</h2>
          <p className="mt-1 text-xs text-slate-500">All successful requests, independent of table pagination.</p>
          <ResponsiveContainer width="100%" height={310}>
            <ScatterChart margin={{ top: 20, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="request_index" name="Request" type="number" />
              <YAxis dataKey="ttfb_ms" name="TTFB" unit=" ms" />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} />
              <Legend />
              {FREQUENCIES.map((frequency) => (
                <Scatter
                  key={frequency}
                  name={frequency}
                  data={points.filter((point) => point.frequency === frequency && !point.is_outlier)}
                  fill={COLORS[frequency]}
                />
              ))}
              <Scatter name="p99 outlier" data={points.filter((point) => point.is_outlier)} fill="#0f172a" shape="cross" />
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <h2 className="font-semibold">Latency distribution</h2>
          <p className="mt-1 text-xs text-slate-500">Whiskers show min/max; boxes show p25-p75 and the central line is the median.</p>
          <BoxPlot groups={report.by_frequency_length} />
        </Card>
        <Card>
          <h2 className="font-semibold">Mean-latency heatmap</h2>
          <p className="mt-1 mb-5 text-xs text-slate-500">Darker cells indicate greater mean TTFB.</p>
          <Heatmap groups={report.by_frequency_length} />
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
          The p-value comes from Welch&apos;s test. Effect size expresses the standardized magnitude of the timing difference.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-slate-500">
                <th className="py-2">Groups</th>
                <th>Mean difference</th>
                <th>Median difference</th>
                <th>P-value</th>
                <th>Effect size</th>
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
                  <td>{comparison.effect_size?.toFixed(2) ?? "-"}</td>
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
            <Input className="lg:w-28" value={filters.status_code ?? ""} onChange={(event) => setFilter("status_code", event.target.value)} placeholder="HTTP" />
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
