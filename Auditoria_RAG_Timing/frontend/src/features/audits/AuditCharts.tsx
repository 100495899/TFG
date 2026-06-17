import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { Summary, SummaryGroup } from "../../api/client";
import { EChart } from "../../components/EChart";

export const FREQUENCIES = ["high", "medium", "low"] as const;
export const LENGTHS = ["short", "medium", "long"] as const;
export const COLORS: Record<string, string> = {
  high: "#15803d",
  medium: "#ca8a04",
  low: "#dc2626"
};

type SharedChartProps = {
  fromZero: boolean;
};

function meanFor(group: SummaryGroup | undefined) {
  return group?.mean_ms ?? null;
}

function hasBoxPlotValues(group: SummaryGroup | undefined): group is SummaryGroup & {
  min_ms: number;
  p25_ms: number;
  median_ms: number;
  p75_ms: number;
  max_ms: number;
} {
  return Boolean(
    group
    && group.min_ms !== null
    && group.p25_ms !== null
    && group.median_ms !== null
    && group.p75_ms !== null
    && group.max_ms !== null
  );
}

function numericDomain(values: Array<number | null | undefined>, fromZero: boolean) {
  const usable = values.filter((value): value is number => value !== null && value !== undefined && Number.isFinite(value));
  if (!usable.length) return { min: 0, max: 1 };
  const dataMin = Math.min(...usable);
  const dataMax = Math.max(...usable);
  if (fromZero) return { min: 0, max: roundAxisMax(Math.max(dataMax * 1.08, 1)) };
  const range = Math.max(dataMax - dataMin, dataMax * 0.02, 1);
  const padding = range * 0.12;
  return {
    min: roundAxisMin(Math.max(0, dataMin - padding)),
    max: roundAxisMax(dataMax + padding)
  };
}

const axisStyle = {
  axisLine: { lineStyle: { color: "#cbd5e1" } },
  axisLabel: { color: "#64748b", fontSize: 11, formatter: formatAxisValue }
};

function roundAxisMin(value: number) {
  return Math.floor(value);
}

function roundAxisMax(value: number) {
  return Math.ceil(value);
}

function formatAxisValue(value: number | string) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  if (Math.abs(number) >= 100) return number.toFixed(0);
  if (Math.abs(number) >= 10) return number.toFixed(1).replace(/\.0$/, "");
  return number.toFixed(2).replace(/\.?0+$/, "");
}

export function FrequencyLengthBarChart({
  groups,
  fromZero
}: { groups: SummaryGroup[] } & SharedChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const values = groups.map((group) => meanFor(group));
    const domain = numericDomain(values, fromZero);
    return {
      animationDuration: 450,
      color: FREQUENCIES.map((frequency) => COLORS[frequency]),
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (value) => `${Number(value).toFixed(2)} ms`
      },
      legend: { top: 4, left: 0, textStyle: { color: "#475569" } },
      grid: { left: 58, right: 20, top: 58, bottom: 45 },
      xAxis: {
        type: "category",
        data: [...LENGTHS],
        name: "Query length",
        nameLocation: "middle",
        nameGap: 30,
        ...axisStyle
      },
      yAxis: {
        type: "value",
        min: domain.min,
        max: domain.max,
        name: "Mean TTFB (ms)",
        nameLocation: "middle",
        nameGap: 46,
        scale: !fromZero,
        splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } },
        ...axisStyle
      },
      series: FREQUENCIES.map((frequency) => ({
        name: frequency,
        type: "bar",
        barMaxWidth: 34,
        emphasis: { focus: "series" },
        data: LENGTHS.map((length) => meanFor(
          groups.find((group) => group.frequency === frequency && group.length === length)
        ))
      }))
    };
  }, [fromZero, groups]);

  return <EChart option={option} ariaLabel="Mean TTFB grouped by frequency and query length" />;
}

export function RequestScatterChart({
  points,
  includeOutliers,
  fromZero
}: {
  points: Summary["points"];
  includeOutliers: boolean;
} & SharedChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const visiblePoints = includeOutliers ? points : points.filter((point) => !point.is_outlier);
    const domain = numericDomain(visiblePoints.map((point) => point.ttfb_ms), fromZero);
    const requestIndexes = visiblePoints.map((point) => point.request_index);
    const minRequest = requestIndexes.length ? Math.min(...requestIndexes) : 0;
    const maxRequest = requestIndexes.length ? Math.max(...requestIndexes) : 1;

    return {
      animation: visiblePoints.length < 1500,
      color: FREQUENCIES.map((frequency) => COLORS[frequency]),
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const item = params as { data: [number, number, string, string, number] };
          const [requestIndex, ttfb, frequency, length, isOutlier] = item.data;
          return [
            `<strong>Request ${requestIndex}</strong>`,
            `${frequency} / ${length}`,
            `TTFB: ${ttfb.toFixed(2)} ms`,
            isOutlier ? "extreme outlier" : ""
          ].filter(Boolean).join("<br/>");
        }
      },
      legend: { top: 4, left: 0, textStyle: { color: "#475569" } },
      grid: { left: 58, right: 24, top: 58, bottom: 48 },
      dataZoom: [
        { type: "inside", xAxisIndex: 0, filterMode: "none" }
      ],
      xAxis: {
        type: "value",
        min: minRequest,
        max: maxRequest,
        name: "Request order",
        nameLocation: "middle",
        nameGap: 30,
        splitLine: { show: false },
        ...axisStyle
      },
      yAxis: {
        type: "value",
        min: domain.min,
        max: domain.max,
        name: "TTFB (ms)",
        nameLocation: "middle",
        nameGap: 46,
        scale: !fromZero,
        splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } },
        ...axisStyle
      },
      series: [
        ...FREQUENCIES.map((frequency) => ({
          name: frequency,
          type: "scatter" as const,
          symbolSize: 6,
          data: visiblePoints
            .filter((point) => point.frequency === frequency && !point.is_outlier)
            .map((point) => [point.request_index, point.ttfb_ms, point.frequency, point.length, 0])
        })),
        ...(includeOutliers ? [{
          name: "extreme outlier",
          type: "scatter" as const,
          symbol: "diamond",
          symbolSize: 9,
          itemStyle: { color: "#0f172a" },
          data: points
            .filter((point) => point.is_outlier)
            .map((point) => [point.request_index, point.ttfb_ms, point.frequency, point.length, 1])
        }] : [])
      ]
    };
  }, [fromZero, includeOutliers, points]);

  return <EChart option={option} ariaLabel="TTFB measurements plotted over request order" />;
}

export function LatencyBoxPlot({
  groups,
  points,
  includeOutliers,
  fromZero
}: {
  groups: SummaryGroup[];
  points: Summary["points"];
  includeOutliers: boolean;
} & SharedChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const orderedGroups = LENGTHS.flatMap((length) =>
      FREQUENCIES.map((frequency) =>
        groups.find((group) => group.frequency === frequency && group.length === length)
      )
    ).filter(hasBoxPlotValues);
    const values = orderedGroups.flatMap((group) => [group.min_ms, group.max_ms]);
    if (includeOutliers) values.push(...points.filter((point) => point.is_outlier).map((point) => point.ttfb_ms));
    const domain = numericDomain(values, fromZero);
    const categories = orderedGroups.map((group) => `${group.length}\n${group.frequency}`);

    return {
      animationDuration: 450,
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const item = params as {
            seriesName: string;
            data: { value: number[]; group?: SummaryGroup; point?: Summary["points"][number] };
          };
          if (item.data.point) {
            const point = item.data.point;
            return `<strong>Extreme outlier</strong><br/>${point.frequency} / ${point.length}<br/>TTFB: ${point.ttfb_ms.toFixed(2)} ms`;
          }
          const group = item.data.group;
          if (!group) return "";
          return [
            `<strong>${group.frequency} / ${group.length}</strong>`,
            `Maximum: ${group.max_ms?.toFixed(2)} ms`,
            `p75: ${group.p75_ms?.toFixed(2)} ms`,
            `Median: ${group.median_ms?.toFixed(2)} ms`,
            `p25: ${group.p25_ms?.toFixed(2)} ms`,
            `Minimum: ${group.min_ms?.toFixed(2)} ms`,
            `Valid samples: ${group.count}`,
            `Filtered outliers: ${group.outlier_count}`
          ].join("<br/>");
        }
      },
      grid: { left: 64, right: 24, top: 34, bottom: 62 },
      dataZoom: [
        { type: "inside", xAxisIndex: 0 }
      ],
      xAxis: {
        type: "category",
        data: categories,
        boundaryGap: true,
        axisLabel: {
          color: "#64748b",
          fontSize: 10,
          interval: 0,
          formatter: (value: string) => {
            const [length, frequency] = value.split("\n");
            return `${length}\n{${frequency}|${frequency}}`;
          },
          rich: Object.fromEntries(
            FREQUENCIES.map((frequency) => [
              frequency,
              { color: COLORS[frequency], fontWeight: 600 }
            ])
          )
        },
        axisLine: axisStyle.axisLine
      },
      yAxis: {
        type: "value",
        min: domain.min,
        max: domain.max,
        name: "TTFB (ms)",
        nameLocation: "middle",
        nameGap: 50,
        scale: !fromZero,
        splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" } },
        ...axisStyle
      },
      series: [
        {
          name: "Distribution",
          type: "boxplot",
          boxWidth: [12, 28],
          data: orderedGroups.map((group) => ({
            value: [group.min_ms, group.p25_ms, group.median_ms, group.p75_ms, group.max_ms],
            group,
            itemStyle: {
              color: `${COLORS[group.frequency ?? ""]}33`,
              borderColor: COLORS[group.frequency ?? ""],
              borderWidth: 1.5
            }
          }))
        },
        ...(includeOutliers ? [{
          name: "extreme outlier",
          type: "scatter" as const,
          symbol: "diamond",
          symbolSize: 8,
          itemStyle: { color: "#0f172a" },
          data: points
            .filter((point) => point.is_outlier)
            .map((point) => {
              const category = categories.indexOf(`${point.length}\n${point.frequency}`);
              return {
                value: [category, point.ttfb_ms],
                point
              };
            })
        }] : [])
      ]
    };
  }, [fromZero, groups, includeOutliers, points]);

  return <EChart option={option} className="h-[400px]" ariaLabel="TTFB box plots grouped by query length and frequency" />;
}

export function MeanLatencyHeatmap({
  groups,
  fromZero
}: {
  groups: SummaryGroup[];
} & SharedChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const data = FREQUENCIES.flatMap((frequency, y) =>
      LENGTHS.map((length, x) => {
        const group = groups.find((item) => item.frequency === frequency && item.length === length);
        return {
          value: [x, y, meanFor(group)],
          group
        };
      })
    );
    const values = data
      .map((item) => item.value[2])
      .filter((value): value is number => typeof value === "number");
    const dataMin = values.length ? Math.min(...values) : 0;
    const dataMax = values.length ? Math.max(...values) : 1;
    const range = Math.max(dataMax - dataMin, dataMax * 0.01, 1);
    const visualMin = fromZero ? 0 : roundAxisMin(Math.max(0, dataMin - range * 0.08));
    const visualMax = roundAxisMax(dataMax + range * 0.08);

    return {
      animationDuration: 450,
      tooltip: {
        formatter: (params: unknown) => {
          const item = params as { data: { group?: SummaryGroup } };
          const group = item.data.group;
          if (!group) return "No data";
          return [
            `<strong>${group.frequency} / ${group.length}</strong>`,
            `Mean: ${group.mean_ms?.toFixed(2)} ms`,
            `Median: ${group.median_ms?.toFixed(2)} ms`,
            `p95: ${group.p95_ms?.toFixed(2)} ms`,
            `Std. deviation: ${group.std_ms?.toFixed(2)} ms`,
            `Valid samples: ${group.count}`,
            `Errors: ${group.error_count}`,
            `Filtered outliers: ${group.outlier_count}`
          ].join("<br/>");
        }
      },
      grid: { left: 76, right: 90, top: 30, bottom: 46 },
      xAxis: {
        type: "category",
        data: [...LENGTHS],
        name: "Query length",
        nameLocation: "middle",
        nameGap: 30,
        splitArea: { show: true },
        ...axisStyle
      },
      yAxis: {
        type: "category",
        data: [...FREQUENCIES],
        splitArea: { show: true },
        axisLabel: {
          color: (value?: string | number) => COLORS[String(value)] ?? "#64748b",
          fontWeight: 600
        },
        axisLine: axisStyle.axisLine
      },
      visualMap: {
        min: visualMin,
        max: visualMax,
        calculable: false,
        orient: "vertical",
        right: 0,
        top: "middle",
        precision: 1,
        formatter: (value: unknown) => `${formatAxisValue(Number(value))} ms`,
        text: ["Higher", "Lower"],
        textStyle: { color: "#64748b", fontSize: 10 },
        inRange: {
          color: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]
        }
      },
      series: [{
        name: "Mean TTFB",
        type: "heatmap",
        data,
        label: {
          show: true,
          formatter: (params: unknown) => {
            const item = params as { value: [number, number, number | null] };
            return item.value[2] === null ? "-" : `${Number(item.value[2]).toFixed(1)} ms`;
          },
          color: "#ffffff",
          fontWeight: 600,
          textBorderColor: "#0f172a",
          textBorderWidth: 2
        },
        emphasis: {
          itemStyle: {
            borderColor: "#0f172a",
            borderWidth: 2,
            shadowBlur: 8,
            shadowColor: "rgba(15, 23, 42, 0.25)"
          }
        }
      }]
    };
  }, [fromZero, groups]);

  return <EChart option={option} ariaLabel="Mean TTFB heatmap by frequency and query length" />;
}
