<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="sl-overlay" @click.self="$emit('close')">
        <div class="sl-modal">
          <div class="sl-header">
            <div class="sl-header-left">
              <Gauge :size="16" class="sl-header-icon" />
              <span class="sl-title">Speed Limit</span>
            </div>
            <button class="sl-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="sl-body">
            <div class="sl-value-display">
              <span class="sl-value">{{ speedValue }}</span>
              <span class="sl-unit">km/h</span>
            </div>

            <input
              type="range"
              min="30"
              max="200"
              step="5"
              v-model.number="speedValue"
              class="sl-slider"
            />

            <div class="sl-range-labels">
              <span>30</span>
              <span>200</span>
            </div>

            <button
              class="sl-apply"
              :disabled="!!loading"
              @click="apply"
            >
              <Loader v-if="loading" :size="16" class="spinning" />
              <span v-else>Set Speed Limit</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { Gauge, Loader } from 'lucide-vue-next'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
})

defineEmits(['close'])

const speedValue = ref(120)
const loading = ref(false)

async function apply() {
  loading.value = true
  try {
    await props.onExec({
      action: 'speed-limit',
      body: { value: String(speedValue.value) },
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.sl-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.sl-modal {
  background: var(--card); border-radius: 16px; padding: 0;
  width: 92vw; max-width: 380px;
  box-shadow: 0 12px 40px rgba(0,0,0,.4); overflow: hidden;
}
.sl-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,.06);
}
.sl-header-left { display: flex; align-items: center; gap: 8px; }
.sl-header-icon { color: #ff9100; }
.sl-title { font-size: 15px; font-weight: 600; color: var(--text); }
.sl-close {
  background: none; border: none; color: var(--muted); font-size: 22px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.sl-body { padding: 24px 20px; display: flex; flex-direction: column; gap: 16px; align-items: center; }
.sl-value-display { display: flex; align-items: baseline; gap: 4px; }
.sl-value { font-size: 48px; font-weight: 700; color: var(--text); }
.sl-unit { font-size: 16px; color: var(--muted); font-weight: 500; }
.sl-slider { width: 100%; accent-color: #ff9100; }
.sl-range-labels {
  display: flex; justify-content: space-between; width: 100%;
  font-size: 11px; color: var(--muted2);
}
.sl-apply {
  width: 100%; padding: 12px; border: none; border-radius: 10px;
  background: #ff9100; color: #000; font-weight: 600; font-size: 14px;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: opacity .2s;
}
.sl-apply:hover { opacity: 0.9; }
.sl-apply:disabled { opacity: 0.5; cursor: wait; }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

@keyframes lm-spin { to { transform: rotate(360deg); } }
.spinning { animation: lm-spin .7s linear infinite; }
</style>
