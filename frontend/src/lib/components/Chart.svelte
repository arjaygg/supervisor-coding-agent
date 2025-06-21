<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { Chart, registerables } from "chart.js";
  import "chartjs-adapter-date-fns";

  // Register Chart.js components
  Chart.register(...registerables);

  export let type: "line" | "bar" | "doughnut" | "pie" = "line";
  export let data: any = { labels: [], datasets: [] };
  export let options: any = {};
  export let width: number = 400;
  export let height: number = 200;

  let canvas: HTMLCanvasElement;
  let chart: Chart | null = null;

  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: "rgb(156, 163, 175)", // gray-400
        },
      },
    },
    scales:
      type === "line" || type === "bar"
        ? {
            x: {
              ticks: {
                color: "rgb(156, 163, 175)", // gray-400
              },
              grid: {
                color: "rgb(55, 65, 81)", // gray-700
              },
            },
            y: {
              ticks: {
                color: "rgb(156, 163, 175)", // gray-400
              },
              grid: {
                color: "rgb(55, 65, 81)", // gray-700
              },
            },
          }
        : {},
  };

  onMount(() => {
    createChart();
  });

  onDestroy(() => {
    if (chart) {
      chart.destroy();
    }
  });

  function createChart() {
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Destroy existing chart if it exists
    if (chart) {
      chart.destroy();
    }

    chart = new Chart(ctx, {
      type,
      data,
      options: { ...defaultOptions, ...options },
    });
  }

  // Reactive updates
  $: if (chart && data) {
    chart.data = data;
    chart.update();
  }

  $: if (chart && options) {
    chart.options = { ...defaultOptions, ...options };
    chart.update();
  }
</script>

<div class="chart-container" style="width: {width}px; height: {height}px;">
  <canvas bind:this={canvas} />
</div>

<style>
  .chart-container {
    position: relative;
  }
</style>
