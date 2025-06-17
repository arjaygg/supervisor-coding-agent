<script lang="ts">
  export let connected: boolean;
  
  $: statusColor = connected ? 'bg-green-500' : 'bg-red-500';
  $: ariaLabel = connected ? 'Connected to server' : 'Disconnected from server';
</script>

<div 
  class="w-3 h-3 rounded-full {statusColor} animate-pulse"
  class:animate-pulse={connected}
  role="status"
  aria-label={ariaLabel}
  data-testid="status-indicator"
></div>