import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { api, ResultFilters } from "../../api/client";
import { Button, Card, Input, Select } from "../../components/ui";

const COLORS: Record<string, string> = {
  high: "#16a34a",
  medium: "#ca8a04",
  low: "#dc2626"
};

export function ResultsPage() {
  const { id } = useParams();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ResultFilters>({});
  const results = useQuery({
    queryKey: ["audit-results", id, page, filters],
    queryFn: () => api.auditResults(id!, page, filters),
    enabled: Boolean(id)
  });
  const summary = useQuery({ queryKey: ["audit-summary", id], queryFn: () => api.auditSummary(id!), enabled: Boolean(id) });
  const items = results.data?.items ?? [];
  const scatter = items.map((r) => ({ x: r.request_index, y: r.ttfb_ms ?? 0, frequency: r.frequency_tag }));
  const bars = summary.data?.groups.map((g) => ({ name: g.frequency, mean: g.mean_ms ?? 0 })) ?? [];

  function setFilter(key: keyof ResultFilters, value: string) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  }

  function download(format: "csv" | "json") {
    if (!id) return;
    fetch(api.exportUrl(id, format), { credentials: "include" })
      .then((response) => {
        if (!response.ok) throw new Error("Export failed");
        return response.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_${id}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      });
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h1 className="text-2xl font-semibold">Results</h1>
        <div className="flex gap-2">
          <Button onClick={() => download("csv")}>CSV</Button>
          <Button onClick={() => download("json")}>JSON</Button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <h2 className="font-semibold mb-2">Mean TTFB by frequency</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={bars}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="mean" fill="#111827" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card>
          <h2 className="font-semibold mb-2">TTFB over request order</h2>
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="x" name="request" />
              <YAxis dataKey="y" name="ttfb" />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} />
              {["high", "medium", "low"].map((frequency) => (
                <Scatter key={frequency} name={frequency} data={scatter.filter((point) => point.frequency === frequency)} fill={COLORS[frequency]} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <Card>
        <h2 className="font-semibold mb-3">Statistical summary</h2>
        <p className="text-sm text-slate-500 mb-3">
          Evidence labels are experimental. Treat them as timing-signal strength indicators, not as a binary vulnerable/not vulnerable verdict.
        </p>
        <div className="grid grid-cols-4 gap-3">
          {(summary.data?.groups ?? []).map((group) => (
            <div key={group.frequency} className="border border-slate-200 rounded p-3">
              <div className="font-medium">{group.frequency}</div>
              <div className="text-sm text-slate-500">n={group.count}</div>
              <div className="text-sm">mean {group.mean_ms?.toFixed(2) ?? "-"} ms</div>
              <div className="text-sm">median {group.median_ms?.toFixed(2) ?? "-"} ms</div>
              <div className="text-sm">p95 {group.p95_ms?.toFixed(2) ?? "-"} ms</div>
              <div className="text-sm">errors {(group.error_rate * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <h2 className="font-semibold mb-3">Comparisons</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">Groups</th>
              <th>Mean diff</th>
              <th>Median diff</th>
              <th>Welch p</th>
              <th>Mann-Whitney p</th>
              <th>Cohen d</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {(summary.data?.comparisons ?? []).map((comparison) => (
              <tr key={`${comparison.group_a}-${comparison.group_b}`} className="border-b border-slate-100">
                <td className="py-2">{comparison.group_a} vs {comparison.group_b}</td>
                <td>{comparison.mean_difference_ms?.toFixed(2) ?? "-"}</td>
                <td>{comparison.median_difference_ms?.toFixed(2) ?? "-"}</td>
                <td>{comparison.welch_p_value?.toExponential(2) ?? "-"}</td>
                <td>{comparison.mann_whitney_p_value?.toExponential(2) ?? "-"}</td>
                <td>{comparison.cohens_d?.toFixed(2) ?? "-"}</td>
                <td>{comparison.evidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card>
        <div className="flex items-center justify-between gap-3 mb-3">
          <h2 className="font-semibold">Requests</h2>
          <div className="flex gap-2">
            <Select value={filters.frequency ?? ""} onChange={(event) => setFilter("frequency", event.target.value)}>
              <option value="">All frequencies</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </Select>
            <Select value={filters.length ?? ""} onChange={(event) => setFilter("length", event.target.value)}>
              <option value="">All lengths</option>
              <option value="short">short</option>
              <option value="medium">medium</option>
              <option value="long">long</option>
            </Select>
            <Select value={filters.is_error ?? ""} onChange={(event) => setFilter("is_error", event.target.value)}>
              <option value="">All outcomes</option>
              <option value="false">success</option>
              <option value="true">error</option>
            </Select>
            <Input className="w-28" value={filters.status_code ?? ""} onChange={(event) => setFilter("status_code", event.target.value)} placeholder="HTTP" />
          </div>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">#</th>
              <th>Frequency</th>
              <th>Length</th>
              <th>TTFB</th>
              <th>Full</th>
              <th>Status</th>
              <th>Query</th>
            </tr>
          </thead>
          <tbody>
            {items.map((result) => (
              <tr key={result.id} className="border-b border-slate-100">
                <td className="py-2">{result.request_index}</td>
                <td>{result.frequency_tag}</td>
                <td>{result.length_tag}</td>
                <td>{result.ttfb_ms?.toFixed(2) ?? "-"}</td>
                <td>{result.full_response_ms?.toFixed(2) ?? "-"}</td>
                <td>{result.status_code ?? result.error_type ?? "-"}</td>
                <td className="max-w-[420px] truncate">{result.query_text}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex justify-between mt-3">
          <Button disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</Button>
          <span className="text-sm text-slate-500">Page {page} - {results.data?.total ?? 0} total</span>
          <Button disabled={(results.data?.items.length ?? 0) < 100} onClick={() => setPage((current) => current + 1)}>Next</Button>
        </div>
      </Card>
    </div>
  );
}
