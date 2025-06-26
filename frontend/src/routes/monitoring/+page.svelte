<script lang="ts">
  import ResourceMonitoringDashboard from "$lib/components/ResourceMonitoringDashboard.svelte";
  import { onMount } from "svelte";
  import { browser } from "$app/environment";

  onMount(() => {
    if (browser) {
      // Set page title
      document.title = "Resource Monitoring - Supervisor Agent";
    }
  });
</script>

<svelte:head>
  <title>Resource Monitoring - Supervisor Agent</title>
  <meta name="description" content="Real-time multi-provider performance analytics and resource monitoring dashboard" />
</svelte:head>

<ResourceMonitoringDashboard />