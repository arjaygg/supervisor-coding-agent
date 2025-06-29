<script lang="ts">
  import PredictiveAnalyticsDashboard from "$lib/components/PredictiveAnalyticsDashboard.svelte";
  import { onMount } from "svelte";
  import { browser } from "$app/environment";

  onMount(() => {
    if (browser) {
      // Set page title
      document.title = "Predictive Analytics - Supervisor Agent";
    }
  });
</script>

<svelte:head>
  <title>Predictive Analytics - Supervisor Agent</title>
  <meta name="description" content="AI-powered predictive analytics, trend forecasting, and optimization insights for multi-provider orchestration" />
</svelte:head>

<PredictiveAnalyticsDashboard />