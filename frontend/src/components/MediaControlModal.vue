<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="mc-overlay" @click.self="$emit('close')">
        <div class="mc-modal">
          <div class="mc-header">
            <div class="mc-header-left">
              <Music :size="16" class="mc-header-icon" />
              <span class="mc-title">Media Control</span>
            </div>
            <button class="mc-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="mc-body">
            <!-- Mode toggle -->
            <div class="mc-mode-toggle">
              <button
                class="mc-mode-btn"
                :class="{ active: mode === 'music' }"
                @click="mode = 'music'"
              >
                <Music :size="14" />
                <span>Music</span>
              </button>
              <button
                class="mc-mode-btn"
                :class="{ active: mode === 'video' }"
                @click="mode = 'video'"
              >
                <Video :size="14" />
                <span>Video</span>
              </button>
            </div>

            <!-- Playback controls -->
            <div class="mc-controls">
              <button
                v-for="op in operations"
                :key="op.action"
                class="mc-ctrl-btn"
                :class="{ loading: loadingAction === op.action }"
                :disabled="!!loadingAction"
                @click="doAction(op.action)"
              >
                <Loader v-if="loadingAction === op.action" :size="20" class="spinning" />
                <component v-else :is="op.icon" :size="20" />
                <span class="mc-ctrl-label">{{ op.label }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { Music, Video, Play, Pause, SkipForward, SkipBack, Loader } from 'lucide-vue-next'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
})

defineEmits(['close'])

const mode = ref('music')
const loadingAction = ref(null)

const operations = [
  { action: 'previous', icon: SkipBack, label: 'Previous' },
  { action: 'play', icon: Play, label: 'Play' },
  { action: 'pause', icon: Pause, label: 'Pause' },
  { action: 'next', icon: SkipForward, label: 'Next' },
]

async function doAction(operation) {
  const action = mode.value  // 'music' or 'video'
  loadingAction.value = operation
  try {
    await props.onExec({
      action,
      body: { operation },
    })
  } finally {
    loadingAction.value = null
  }
}
</script>

<style scoped>
.mc-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.mc-modal {
  background: var(--card); border-radius: 16px; padding: 0;
  width: 92vw; max-width: 380px;
  box-shadow: 0 12px 40px rgba(0,0,0,.4); overflow: hidden;
}
.mc-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,.06);
}
.mc-header-left { display: flex; align-items: center; gap: 8px; }
.mc-header-icon { color: #7c6aff; }
.mc-title { font-size: 15px; font-weight: 600; color: var(--text); }
.mc-close {
  background: none; border: none; color: var(--muted); font-size: 22px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.mc-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }

.mc-mode-toggle {
  display: flex; gap: 8px; background: var(--bg); border-radius: 10px; padding: 4px;
}
.mc-mode-btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 8px; border: none; border-radius: 8px; cursor: pointer;
  background: transparent; color: var(--muted); font-size: 13px; font-weight: 500;
  transition: all .2s;
}
.mc-mode-btn.active { background: var(--card); color: var(--text); box-shadow: 0 2px 8px rgba(0,0,0,.2); }

.mc-controls {
  display: flex; justify-content: center; gap: 12px;
}
.mc-ctrl-btn {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 16px 18px; border: 1px solid rgba(255,255,255,.08); border-radius: 12px;
  background: var(--elevated); color: var(--text); cursor: pointer;
  transition: all .15s; min-width: 64px;
}
.mc-ctrl-btn:hover { transform: scale(1.05); border-color: #7c6aff44; }
.mc-ctrl-btn:active { transform: scale(0.95); }
.mc-ctrl-btn.loading { opacity: 0.6; cursor: wait; }
.mc-ctrl-btn:disabled { pointer-events: none; }
.mc-ctrl-label { font-size: 10px; color: var(--muted); font-weight: 500; }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

@keyframes lm-spin { to { transform: rotate(360deg); } }
.spinning { animation: lm-spin .7s linear infinite; }
</style>
