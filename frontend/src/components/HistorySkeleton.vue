<template>
  <div class="skeleton-container">
    <!-- KPI cards skeleton -->
    <div v-if="showKpi" class="summary-grid">
      <div v-for="i in 10" :key="i" class="summary-card skeleton-card">
        <div class="skeleton-line skeleton-value"></div>
        <div class="skeleton-line skeleton-label"></div>
      </div>
    </div>

    <!-- Charts skeleton -->
    <div v-if="showCharts" class="charts-skeleton">
      <div class="skeleton-section-title"></div>
      <div class="charts-grid">
        <div v-for="i in chartCount" :key="i" class="chart-card skeleton-chart-card">
          <div class="skeleton-line skeleton-chart-header"></div>
          <div class="skeleton-chart-area">
            <svg viewBox="0 0 300 100" preserveAspectRatio="none" class="skeleton-wave">
              <path d="M0,60 C50,40 100,80 150,50 C200,20 250,70 300,45" fill="none" stroke="currentColor" stroke-width="2"/>
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  showKpi: { type: Boolean, default: true },
  showCharts: { type: Boolean, default: true },
  chartCount: { type: Number, default: 4 },
})
</script>

<style scoped>
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
@media (min-width: 768px) {
  .summary-grid { grid-template-columns: repeat(5, 1fr); }
}

.summary-card.skeleton-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.skeleton-line {
  border-radius: 6px;
  background: var(--skeleton);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.skeleton-value {
  width: 60%;
  height: 22px;
}

.skeleton-label {
  width: 80%;
  height: 12px;
}

.skeleton-section-title {
  width: 160px;
  height: 14px;
  border-radius: 4px;
  background: var(--skeleton);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  margin-bottom: 8px;
}

.charts-skeleton {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
@media (min-width: 768px) {
  .charts-grid { grid-template-columns: 1fr 1fr; }
}

.skeleton-chart-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
}

.skeleton-chart-header {
  width: 55%;
  height: 14px;
  margin-bottom: 14px;
}

.skeleton-chart-area {
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--elevated);
}

.skeleton-wave {
  width: 80%;
  height: 60%;
  color: var(--muted);
  opacity: 0.6;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@keyframes pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.7; }
}
</style>
