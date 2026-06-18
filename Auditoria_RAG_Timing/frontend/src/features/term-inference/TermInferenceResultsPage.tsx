import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import type { EChartsOption } from "echarts";
import { useParams } from "react-router-dom";
import { api, TermInferenceResult } from "../../api/client";
import { EChart } from "../../components/EChart";
import { Button, Card } from "../../components/ui";

const CLASS_STYLES: Record<string, string> = {
  likely_present: "bg-green-100 text-green-800",
  likely_absent: "bg-red-100 text-red-800",
  inconclusive: "bg-slate-100 text-slate-700"
};

function ms(value: number | null) {
  return value === null ? "-" : `${value.toFixed(2)} ms`;
}

function ClassificationBadge({ value }: { value: string | null }) {
  const label = value ?? "pending";
  return <span className={`inline-flex rounded px-2 py-1 text-xs font-medium ${CLASS_STYLES[label] ?? "bg-slate-100 text-slate-600"}`}>{label}</span>;
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{detail}</div>
    </Card>
  );
}

function TermInferenceChart({
  results,
  profile,
  fromZero
}: {
  results: TermInferenceResult[];
  profile: { high_mean_ms: number; medium_mean_ms: number | null; low_mean_ms: number; threshold_ms: number };
  fromZero: boolean;
}) {
  const terms = results.filter((result) => !result.is_control);
  const option = useMemo<EChartsOption>(() => {
    const values = terms.flatMap((result) => result.observed_mean_ttfb_ms === null ? [] : [result.observed_mean_ttfb_ms]);
    values.push(profile.high_mean_ms, profile.low_mean_ms, profile.threshold_ms);
    if (profile.medium_mean_ms !== null) values.push(profile.medium_mean_ms);
    const min = fromZero ? 0 : Math.max(0, Math.floor(Math.min(...values) - 5));
    const max = Math.ceil(Math.max(...values) + 5);
    return {
      animationDuration: 450,
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const item = params as { data: [number, number, string, string, number] };
          const [, value, term, classification, count] = item.data;
          return `<strong>${term}</strong><br/>${classification}<br/>Mean TTFB: ${value.toFixed(2)} ms<br/>Valid probes: ${count}`;
        }
      },
      grid: { left: 64, right: 32, top: 28, bottom: 88 },
      xAxis: {
        type: "category",
        data: terms.map((result) => result.term),
        axisLabel: { color: "#64748b", rotate: 35, interval: 0 },
        axisLine: { lineStyle: { color: "#cbd5e1" } }
      },
      yAxis: {
        type: "value",
        min,
        max,
        name: "Mean TTFB (ms)",
        nameLocation: "middle",
        nameGap: 48,
        axisLabel: { color: "#64748b", formatter: (value: number) => value.toFixed(0) },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
      },
      series: [{
        type: "scatter",
        symbolSize: 11,
        itemStyle: {
          color: (params: { data?: unknown }) => {
            const data = params.data as [number, number, string, string, number] | undefined;
            const classification = data?.[3];
            if (classification === "likely_present") return "#15803d";
            if (classification === "likely_absent") return "#dc2626";
            return "#64748b";
          }
        },
        data: terms
          .flatMap((result, index) => result.observed_mean_ttfb_ms === null ? [] : [[
            index,
            result.observed_mean_ttfb_ms,
            result.term,
            result.classification ?? "pending",
            result.valid_measurements
          ]]),
        markLine: {
          symbol: "none",
          label: { formatter: "{b}", color: "#475569" },
          lineStyle: { type: "dashed" },
          data: [
            { name: "high", yAxis: profile.high_mean_ms, lineStyle: { color: "#15803d" } },
            ...(profile.medium_mean_ms === null ? [] : [{ name: "medium", yAxis: profile.medium_mean_ms, lineStyle: { color: "#ca8a04" } }]),
            { name: "low", yAxis: profile.low_mean_ms, lineStyle: { color: "#dc2626" } },
            { name: "threshold", yAxis: profile.threshold_ms, lineStyle: { color: "#0f172a", width: 2 } }
          ]
        }
      }]
    };
  }, [fromZero, profile, terms]);

  return <EChart option={option} className="h-[420px]" ariaLabel="Term inference observed means compared with calibration references" />;
}

function classifyMean(mean: number, profile: { threshold_ms: number; gray_zone_ms: number }) {
  const lowerBound = profile.threshold_ms - profile.gray_zone_ms;
  const upperBound = profile.threshold_ms + profile.gray_zone_ms;
  if (mean < lowerBound) return "likely_present";
  if (mean > upperBound) return "likely_absent";
  return "inconclusive";
}

function DecisionConvergenceChart({
  results,
  measurements,
  profile,
  fromZero
}: {
  results: TermInferenceResult[];
  measurements: Array<{ result_id: string; request_index: number; ttfb_ms: number | null; is_error: boolean }>;
  profile: { threshold_ms: number; gray_zone_ms: number };
  fromZero: boolean;
}) {
  const terms = results.filter((result) => !result.is_control && result.classification !== null);
  const option = useMemo<EChartsOption>(() => {
    const measurementMap = new Map<string, number[]>();
    for (const result of terms) {
      const values = measurements
        .filter((measurement) => measurement.result_id === result.id && !measurement.is_error && measurement.ttfb_ms !== null)
        .sort((left, right) => left.request_index - right.request_index)
        .map((measurement) => measurement.ttfb_ms as number);
      measurementMap.set(result.id, values);
    }

    const maxCount = Math.max(0, ...Array.from(measurementMap.values()).map((values) => values.length));
    const points: Array<[number, number, number, number]> = [];
    for (let probeCount = 1; probeCount <= maxCount; probeCount += 1) {
      let evaluable = 0;
      let matching = 0;
      for (const result of terms) {
        const values = measurementMap.get(result.id) ?? [];
        if (values.length < probeCount || result.classification === null) continue;
        const mean = values.slice(0, probeCount).reduce((sum, value) => sum + value, 0) / probeCount;
        const partialClassification = classifyMean(mean, profile);
        evaluable += 1;
        if (partialClassification === result.classification) matching += 1;
      }
      if (evaluable > 0) {
        points.push([probeCount, (matching / evaluable) * 100, matching, evaluable]);
      }
    }

    const yValues = points.map((point) => point[1]);
    const minY = yValues.length ? Math.min(...yValues) : 0;
    const maxY = yValues.length ? Math.max(...yValues) : 100;
    const yMin = fromZero ? 0 : Math.max(0, Math.floor(minY / 5) * 5 - 5);
    const yMax = fromZero ? 105 : Math.min(105, Math.ceil(maxY / 5) * 5 + 5);
    const xMin = fromZero ? 0 : 0.5;
    const xMax = Math.max(2, maxCount + 0.5);

    return {
      animationDuration: 450,
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const item = Array.isArray(params) ? params[0] as { data: [number, number, number, number] } : null;
          if (!item) return "";
          const [probeCount, agreement, matching, evaluable] = item.data;
          return `<strong>${probeCount} probes per term</strong><br/>Agreement: ${agreement.toFixed(1)}%<br/>${matching}/${evaluable} terms match final decision`;
        }
      },
      grid: { left: 64, right: 28, top: 28, bottom: 54 },
      graphic: points.length ? [] : [{
        type: "text",
        left: "center",
        top: "middle",
        style: {
          text: "No convergence data available yet",
          fill: "#64748b",
          fontSize: 13
        }
      }],
      dataZoom: [
        { type: "inside", xAxisIndex: 0, filterMode: "none" },
        { type: "inside", yAxisIndex: 0, filterMode: "none" }
      ],
      xAxis: {
        type: "value",
        min: xMin,
        max: xMax,
        minInterval: 1,
        name: "Queries per term",
        nameLocation: "middle",
        nameGap: 32,
        axisLabel: { color: "#64748b", formatter: (value: number) => value.toFixed(0) },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
      },
      yAxis: {
        type: "value",
        min: yMin,
        max: yMax,
        name: "Decision agreement (%)",
        nameLocation: "middle",
        nameGap: 46,
        axisLabel: { color: "#64748b", formatter: (value: number) => `${value.toFixed(0)}%` },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } }
      },
      series: [{
        name: "Agreement",
        type: "line",
        smooth: true,
        showSymbol: true,
        symbol: "circle",
        symbolSize: 8,
        lineStyle: { color: "#0f172a", width: 3 },
        itemStyle: { color: "#0f172a" },
        areaStyle: { color: "rgba(15, 23, 42, 0.08)" },
        data: points
      }]
    };
  }, [fromZero, measurements, profile, terms]);

  return <EChart option={option} className="h-[360px]" ariaLabel="Decision convergence by number of term inference queries" />;
}

export function TermInferenceResultsPage() {
  const { id } = useParams();
  const [fromZero, setFromZero] = useState(false);
  const report = useQuery({
    queryKey: ["term-inference-results", id],
    queryFn: () => api.termInferenceResults(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.session.status;
      return status && ["PENDING", "RUNNING", "ABORT_REQUESTED"].includes(status) ? 2000 : false;
    }
  });

  async function download() {
    if (!id) return;
    const blob = await api.downloadTermInferenceCsv(id);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `term_inference_${id}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (report.isLoading) {
    return <div className="grid min-h-64 place-items-center text-sm text-slate-500">Loading term inference...</div>;
  }
  if (report.isError || !report.data) {
    return <Card><p className="text-sm text-red-700">{report.error instanceof Error ? report.error.message : "Could not load term inference."}</p></Card>;
  }

  const data = report.data;
  const termResults = data.results.filter((result) => !result.is_control);
  const resultById = new Map(data.results.map((result) => [result.id, result]));
  const present = termResults.filter((result) => result.classification === "likely_present").length;
  const absent = termResults.filter((result) => result.classification === "likely_absent").length;
  const inconclusive = termResults.filter((result) => result.classification === "inconclusive").length;

  return (
    <div className="space-y-4">
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Term inference report</h1>
          <p className="mt-1 text-sm text-slate-500">{data.session.source_label} · status {data.session.status}</p>
        </div>
        <Button onClick={download}><Download size={15} className="mr-2 inline" />Export CSV</Button>
      </section>
      {data.session.warning_message && <Card><p className="text-sm text-amber-700">{data.session.warning_message}</p></Card>}
      {data.session.error_message && <Card><p className="text-sm text-red-700">{data.session.error_message}</p></Card>}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Terms" value={String(termResults.length)} detail={`${data.results.filter((result) => result.is_control).length} controls`} />
        <MetricCard label="Likely present" value={String(present)} detail="Faster than the calibrated threshold" />
        <MetricCard label="Likely absent" value={String(absent)} detail="Slower than the calibrated threshold" />
        <MetricCard label="Inconclusive" value={String(inconclusive)} detail="Inside uncertainty band or insufficient signal" />
        <MetricCard label="Threshold" value={ms(data.profile.threshold_ms)} detail={`Gray zone ±${data.profile.gray_zone_ms.toFixed(2)} ms`} />
      </section>

      <Card className="flex flex-wrap items-center justify-between gap-4 py-3">
        <div>
          <div className="text-xs font-medium uppercase text-slate-500">Chart controls</div>
          <p className="mt-1 text-xs text-slate-500">Charts compare observed TTFB against the calibrated decision threshold.</p>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-600">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={fromZero}
              onChange={(event) => setFromZero(event.target.checked)}
            />
            Start axes at zero
          </label>
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold">Observed term means</h2>
        <p className="mt-1 text-xs text-slate-500">
          Reference lines come from short high, medium and low calibration groups. Medium is explanatory only.
        </p>
        <TermInferenceChart results={data.results} profile={data.profile} fromZero={fromZero} />
      </Card>

      <Card>
        <h2 className="font-semibold">Decision convergence</h2>
        <p className="mt-1 text-xs text-slate-500">
          Shows how many queries per term are needed before partial classifications match the final decision.
        </p>
        <DecisionConvergenceChart
          results={data.results}
          measurements={data.measurements}
          profile={data.profile}
          fromZero={fromZero}
        />
      </Card>

      <Card>
        <h2 className="font-semibold">Term decisions</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[960px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-slate-500">
                <th className="py-2">Term</th>
                <th>Type</th>
                <th>Classification</th>
                <th>Mean TTFB</th>
                <th>Std</th>
                <th>Valid/total</th>
                <th>Distance</th>
                <th>Closest ref</th>
                <th>Errors</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((result) => (
                <tr key={result.id} className="border-b border-slate-100">
                  <td className="py-2 font-medium">{result.term}</td>
                  <td>{result.is_control ? "control" : "term"}</td>
                  <td><ClassificationBadge value={result.classification} /></td>
                  <td>{ms(result.observed_mean_ttfb_ms)}</td>
                  <td>{ms(result.observed_std_ttfb_ms)}</td>
                  <td>{result.valid_measurements}/{result.total_measurements}</td>
                  <td>{ms(result.distance_to_threshold_ms)}</td>
                  <td>{result.closest_reference ?? "-"}</td>
                  <td>{result.error_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <h2 className="font-semibold">Probe timeline</h2>
        <p className="mt-1 text-xs text-slate-500">
          Chronological sequence of term probes and interleaved negative controls stored during this inference.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[1120px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-slate-500">
                <th className="py-2">#</th>
                <th>Round</th>
                <th>Term</th>
                <th>Type</th>
                <th>TTFB</th>
                <th>Full response</th>
                <th>Size</th>
                <th>Status</th>
                <th>Query</th>
              </tr>
            </thead>
            <tbody>
              {data.measurements.map((measurement) => {
                const result = resultById.get(measurement.result_id);
                return (
                  <tr key={measurement.id} className="border-b border-slate-100">
                    <td className="py-2">{measurement.request_index}</td>
                    <td>{measurement.round_number}</td>
                    <td className="font-medium">{result?.term ?? "-"}</td>
                    <td>{result?.is_control ? "control" : "term"}</td>
                    <td>{ms(measurement.ttfb_ms)}</td>
                    <td>{ms(measurement.full_response_ms)}</td>
                    <td>{measurement.response_size_bytes === null ? "-" : `${measurement.response_size_bytes} B`}</td>
                    <td>{measurement.status_code ?? measurement.error_type ?? "-"}</td>
                    <td className="max-w-[420px] truncate" title={measurement.query_text}>{measurement.query_text}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
