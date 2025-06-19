<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/utils/api';

  let settings = {
    general: {
      autoRefresh: true,
      refreshInterval: 5000,
      theme: 'dark',
      notifications: true
    },
    api: {
      timeout: 30000,
      retryAttempts: 3,
      rateLimitEnabled: true
    },
    tasks: {
      defaultPriority: 5,
      maxRetries: 3,
      batchSize: 10
    }
  };

  let systemInfo = null;
  let loading = true;
  let saving = false;
  let saveMessage = '';

  onMount(async () => {
    await loadSystemInfo();
    loadUserSettings();
    loading = false;
  });

  async function loadSystemInfo() {
    try {
      const response = await api.get('/health/detailed');
      systemInfo = response.data;
    } catch (err) {
      console.error('Error loading system info:', err);
    }
  }

  function loadUserSettings() {
    // Load settings from localStorage
    const saved = localStorage.getItem('supervisor-agent-settings');
    if (saved) {
      try {
        const parsedSettings = JSON.parse(saved);
        settings = { ...settings, ...parsedSettings };
      } catch (err) {
        console.error('Error parsing saved settings:', err);
      }
    }
  }

  async function saveSettings() {
    saving = true;
    saveMessage = '';
    
    try {
      // Save to localStorage
      localStorage.setItem('supervisor-agent-settings', JSON.stringify(settings));
      
      // Here you could also save to backend if needed
      // await api.post('/settings', settings);
      
      saveMessage = 'Settings saved successfully';
      setTimeout(() => {
        saveMessage = '';
      }, 3000);
    } catch (err) {
      saveMessage = 'Error saving settings';
      console.error('Error saving settings:', err);
    } finally {
      saving = false;
    }
  }

  function resetToDefaults() {
    settings = {
      general: {
        autoRefresh: true,
        refreshInterval: 5000,
        theme: 'dark',
        notifications: true
      },
      api: {
        timeout: 30000,
        retryAttempts: 3,
        rateLimitEnabled: true
      },
      tasks: {
        defaultPriority: 5,
        maxRetries: 3,
        batchSize: 10
      }
    };
    saveSettings();
  }

  function formatUptime(timestamp) {
    if (!timestamp) return 'Unknown';
    const uptime = Date.now() - new Date(timestamp).getTime();
    const hours = Math.floor(uptime / (1000 * 60 * 60));
    const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
  }
</script>

<svelte:head>
  <title>Settings - Supervisor Coding Agent</title>
</svelte:head>

<div class="container mx-auto px-4 py-8">
  <div class="mb-8">
    <h1 class="text-3xl font-bold text-white mb-2">Settings</h1>
    <p class="text-gray-400">Configure system preferences and view system information</p>
  </div>

  {#if loading}
    <div class="flex items-center justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      <span class="ml-3 text-gray-400">Loading settings...</span>
    </div>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <!-- Settings Panel -->
      <div class="space-y-6">
        <!-- General Settings -->
        <div class="settings-section">
          <h2 class="section-title">General</h2>
          <div class="space-y-4">
            <label class="setting-item">
              <span class="setting-label">Auto Refresh</span>
              <input 
                type="checkbox" 
                bind:checked={settings.general.autoRefresh}
                class="setting-checkbox"
              />
            </label>
            
            <label class="setting-item">
              <span class="setting-label">Refresh Interval (ms)</span>
              <input 
                type="number" 
                bind:value={settings.general.refreshInterval}
                min="1000"
                max="60000"
                step="1000"
                class="setting-input"
              />
            </label>
            
            <label class="setting-item">
              <span class="setting-label">Theme</span>
              <select bind:value={settings.general.theme} class="setting-select">
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="auto">Auto</option>
              </select>
            </label>
            
            <label class="setting-item">
              <span class="setting-label">Notifications</span>
              <input 
                type="checkbox" 
                bind:checked={settings.general.notifications}
                class="setting-checkbox"
              />
            </label>
          </div>
        </div>

        <!-- API Settings -->
        <div class="settings-section">
          <h2 class="section-title">API Configuration</h2>
          <div class="space-y-4">
            <label class="setting-item">
              <span class="setting-label">Timeout (ms)</span>
              <input 
                type="number" 
                bind:value={settings.api.timeout}
                min="5000"
                max="300000"
                step="5000"
                class="setting-input"
              />
            </label>
            
            <label class="setting-item">
              <span class="setting-label">Retry Attempts</span>
              <input 
                type="number" 
                bind:value={settings.api.retryAttempts}
                min="0"
                max="10"
                class="setting-input"
              />
            </label>
            
            <label class="setting-item">
              <span class="setting-label">Rate Limiting</span>
              <input 
                type="checkbox" 
                bind:checked={settings.api.rateLimitEnabled}
                class="setting-checkbox"
              />
            </label>
          </div>
        </div>

        <!-- Task Settings -->
        <div class="settings-section">
          <h2 class="section-title">Task Defaults</h2>
          <div class="space-y-4">
            <label class="setting-item">
              <span class="setting-label">Default Priority</span>
              <input 
                type="number" 
                bind:value={settings.tasks.defaultPriority}
                min="1"
                max="10"
                class="setting-input"
              />
            </label>
            
            <label class="setting-item">
              <span class="setting-label">Max Retries</span>
              <input 
                type="number" 
                bind:value={settings.tasks.maxRetries}
                min="0"
                max="10"
                class="setting-input"
              />
            </label>
            
            <label class="setting-item">
              <span class="setting-label">Batch Size</span>
              <input 
                type="number" 
                bind:value={settings.tasks.batchSize}
                min="1"
                max="100"
                class="setting-input"
              />
            </label>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-4">
          <button 
            on:click={saveSettings}
            disabled={saving}
            class="btn-primary"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
          
          <button 
            on:click={resetToDefaults}
            class="btn-outline"
          >
            Reset to Defaults
          </button>
        </div>

        {#if saveMessage}
          <div class="p-3 rounded-lg {saveMessage.includes('Error') ? 'bg-red-900/20 border border-red-500/50 text-red-400' : 'bg-green-900/20 border border-green-500/50 text-green-400'}">
            {saveMessage}
          </div>
        {/if}
      </div>

      <!-- System Information -->
      <div class="space-y-6">
        <div class="settings-section">
          <h2 class="section-title">System Information</h2>
          
          {#if systemInfo}
            <div class="space-y-3">
              <div class="info-item">
                <span class="info-label">Version</span>
                <span class="info-value">{systemInfo.version || '1.0.0'}</span>
              </div>
              
              <div class="info-item">
                <span class="info-label">Status</span>
                <span class="info-value capitalize {systemInfo.status === 'healthy' ? 'text-green-400' : 'text-yellow-400'}">
                  {systemInfo.status || 'Unknown'}
                </span>
              </div>
              
              <div class="info-item">
                <span class="info-label">Uptime</span>
                <span class="info-value">{formatUptime(systemInfo.timestamp)}</span>
              </div>
              
              {#if systemInfo.components}
                <div class="mt-4">
                  <h3 class="text-sm font-medium text-gray-400 mb-2">Components</h3>
                  <div class="space-y-2">
                    {#each Object.entries(systemInfo.components) as [component, status]}
                      <div class="flex justify-between items-center">
                        <span class="text-gray-300 capitalize">{component}</span>
                        <span class="text-sm {status.status === 'healthy' ? 'text-green-400' : 'text-red-400'}">
                          {status.status || 'Unknown'}
                        </span>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {:else}
            <div class="text-gray-500">System information unavailable</div>
          {/if}
        </div>

        <!-- Help & Documentation -->
        <div class="settings-section">
          <h2 class="section-title">Help & Documentation</h2>
          <div class="space-y-3">
            <a href="/docs" class="help-link">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span>Documentation</span>
            </a>
            
            <a href="https://github.com/arjaygg/supervisor-coding-agent" target="_blank" class="help-link">
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              <span>GitHub Repository</span>
            </a>
            
            <div class="help-link cursor-default">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>API Version: v1</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

