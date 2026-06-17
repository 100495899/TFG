import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import type { EChartsOption } from "echarts";
import {
  BarChart,
  BoxplotChart,
  HeatmapChart,
  ScatterChart
} from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";

echarts.use([
  BarChart,
  BoxplotChart,
  HeatmapChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  SVGRenderer
]);

type EChartProps = {
  option: EChartsOption;
  className?: string;
  ariaLabel: string;
};

export function EChart({ option, className = "h-[340px]", ariaLabel }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = echarts.init(container, undefined, { renderer: "svg" });
    chart.setOption(option, { notMerge: true });

    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    echarts.getInstanceByDom(container)?.setOption(option, { notMerge: true });
  }, [option]);

  return <div ref={containerRef} className={`w-full ${className}`} role="img" aria-label={ariaLabel} />;
}
