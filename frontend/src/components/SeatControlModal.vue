<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="sc-overlay" @click.self="$emit('close')">
        <div class="sc-modal">
          <div class="sc-header">
            <div class="sc-header-left">
              <Armchair :size="16" class="sc-header-icon" />
              <span class="sc-title">Seat Controls</span>
            </div>
            <button class="sc-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="sc-body">
            <!-- Tab toggle -->
            <div class="sc-tab-toggle">
              <button class="sc-tab-btn" :class="{ active: tab === 'comfort' }" @click="tab = 'comfort'">Comfort</button>
              <button class="sc-tab-btn" :class="{ active: tab === 'adjust' }" @click="tab = 'adjust'">Adjust</button>
              <button class="sc-tab-btn" :class="{ active: tab === 'rear' }" @click="tab = 'rear'">Rear</button>
            </div>

            <!-- Comfort tab (heat/ventilation) -->
            <template v-if="tab === 'comfort'">
              <!-- Mode toggle -->
              <div class="sc-mode-toggle">
                <button
                  class="sc-mode-btn"
                  :class="{ active: mode === 'heat' }"
                  @click="mode = 'heat'"
                >
                  <Flame :size="14" />
                  <span>Heating</span>
                </button>
                <button
                  class="sc-mode-btn"
                  :class="{ active: mode === 'vent' }"
                  @click="mode = 'vent'"
                >
                  <Wind :size="14" />
                  <span>Ventilation</span>
                </button>
              </div>

              <!-- Position selector -->
              <div class="sc-positions">
                <button
                  v-for="pos in positions"
                  :key="pos.value"
                  class="sc-pos-btn"
                  :class="{ selected: selectedPosition === pos.value }"
                  @click="selectedPosition = pos.value"
                >
                  <span class="sc-pos-label">{{ pos.label }}</span>
                  <span class="sc-pos-status">{{ getStatusLabel(pos.value) }}</span>
                </button>
              </div>

              <!-- Level selector -->
              <div class="sc-level">
                <span class="sc-level-label">Level</span>
                <div class="sc-level-btns">
                  <button
                    v-for="l in levels"
                    :key="l.value"
                    class="sc-level-btn"
                    :class="{ active: selectedLevel === l.value }"
                    @click="selectedLevel = l.value"
                  >{{ l.label }}</button>
                </div>
              </div>

              <!-- Current status -->
              <div v-if="seatComfort" class="sc-status">
                <div class="sc-status-row">
                  <span>Driver Heat</span>
                  <span class="sc-status-val">{{ seatComfort.driver_seat_heating ?? '—' }}</span>
                </div>
                <div class="sc-status-row">
                  <span>Driver Vent</span>
                  <span class="sc-status-val">{{ seatComfort.driver_seat_ventilation ?? '—' }}</span>
                </div>
                <div class="sc-status-row">
                  <span>Passenger Heat</span>
                  <span class="sc-status-val">{{ seatComfort.passenger_seat_heating ?? '—' }}</span>
                </div>
                <div class="sc-status-row">
                  <span>Passenger Vent</span>
                  <span class="sc-status-val">{{ seatComfort.passenger_seat_ventilation ?? '—' }}</span>
                </div>
                <div class="sc-status-row">
                  <span>Steering Wheel</span>
                  <span class="sc-status-val">{{ seatComfort.steering_wheel_heating ?? '—' }}</span>
                </div>
              </div>

              <!-- Apply -->
              <button
                class="sc-apply"
                :disabled="!!loadingAction"
                @click="apply"
              >
                <Loader v-if="loadingAction" :size="16" class="spinning" />
                <span v-else>Apply</span>
              </button>
            </template>

            <!-- Adjust tab (seat position) -->
            <template v-if="tab === 'adjust'">
              <div class="sc-section-label">Seat Position</div>
              <div class="sc-positions">
                <button
                  v-for="pos in adjustPositions"
                  :key="pos.value"
                  class="sc-pos-btn"
                  :class="{ selected: adjustSeatPos === pos.value }"
                  @click="adjustSeatPos = pos.value"
                >
                  <span class="sc-pos-label">{{ pos.label }}</span>
                </button>
              </div>

              <div class="sc-section-label">Adjustment</div>
              <div class="sc-adjust-grid">
                <button
                  v-for="adj in adjustActions"
                  :key="adj.key"
                  class="sc-adjust-btn"
                  :class="{ loading: loadingAction === adj.key }"
                  :disabled="!!loadingAction"
                  @click="doSeatAdjust(adj.key, adj.params)"
                >
                  <component :is="adj.icon" :size="14" />
                  <span>{{ adj.label }}</span>
                </button>
              </div>
            </template>

            <!-- Rear seats tab -->
            <template v-if="tab === 'rear'">
              <div class="sc-section-label">Rear Seat Control (C16)</div>
              <div class="sc-positions">
                <button
                  v-for="rs in rearSeatOptions"
                  :key="rs.value"
                  class="sc-pos-btn"
                  :class="{ selected: rearSeatInfo === rs.value }"
                  @click="rearSeatInfo = rs.value"
                >
                  <span class="sc-pos-label">{{ rs.label }}</span>
                </button>
              </div>
              <button
                class="sc-apply"
                :disabled="!!loadingAction || !rearSeatInfo"
                @click="doRearSeats"
              >
                <Loader v-if="loadingAction" :size="16" class="spinning" />
                <span v-else>Apply</span>
              </button>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { Armchair, Flame, Wind, Loader, ChevronUp, ChevronDown, ArrowLeft, ArrowRight, RotateCcw } from 'lucide-vue-next'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
  seatComfort: Object,
})

defineEmits(['close'])

const tab = ref('comfort')
const mode = ref('heat')
const selectedPosition = ref(1)
const selectedLevel = ref(0)
const loadingAction = ref(null)

const positions = [
  { value: 1, label: 'Driver' },
  { value: 2, label: 'Passenger' },
  { value: 5, label: 'Rear Left' },
  { value: 6, label: 'Rear Right' },
]

const levels = [
  { value: 0, label: 'Off' },
  { value: 1, label: 'Low' },
  { value: 2, label: 'Med' },
  { value: 3, label: 'High' },
]

// Seat adjust
const adjustSeatPos = ref(1)
const adjustPositions = [
  { value: 1, label: 'Driver' },
  { value: 2, label: 'Passenger' },
]

const adjustActions = [
  { key: 'forward', label: 'Forward', icon: ChevronUp, params: { direction: 'forward' } },
  { key: 'backward', label: 'Backward', icon: ChevronDown, params: { direction: 'backward' } },
  { key: 'up', label: 'Up', icon: ChevronUp, params: { direction: 'up' } },
  { key: 'down', label: 'Down', icon: ChevronDown, params: { direction: 'down' } },
  { key: 'recline-back', label: 'Recline Back', icon: ArrowRight, params: { direction: 'recline_back' } },
  { key: 'recline-forward', label: 'Recline Fwd', icon: ArrowLeft, params: { direction: 'recline_forward' } },
  { key: 'reset', label: 'Reset', icon: RotateCcw, params: { direction: 'reset' } },
]

// Rear seats
const rearSeatInfo = ref('fold')
const rearSeatOptions = [
  { value: 'fold', label: 'Fold' },
  { value: 'unfold', label: 'Unfold' },
  { value: 'heat_on', label: 'Heat On' },
  { value: 'heat_off', label: 'Heat Off' },
]

function getStatusLabel(pos) {
  if (!props.seatComfort) return '—'
  if (mode.value === 'heat') {
    if (pos === 1) return `H:${props.seatComfort.driver_seat_heating ?? '—'}`
    if (pos === 2) return `H:${props.seatComfort.passenger_seat_heating ?? '—'}`
  } else {
    if (pos === 1) return `V:${props.seatComfort.driver_seat_ventilation ?? '—'}`
    if (pos === 2) return `V:${props.seatComfort.passenger_seat_ventilation ?? '—'}`
  }
  return '—'
}

async function apply() {
  const action = mode.value === 'heat' ? 'seat-heat' : 'seat-ventilation'
  loadingAction.value = action
  try {
    await props.onExec({
      action,
      body: { position: selectedPosition.value, level: selectedLevel.value },
    })
  } finally {
    loadingAction.value = null
  }
}

async function doSeatAdjust(key, params) {
  loadingAction.value = key
  try {
    await props.onExec({
      action: 'seat-adjust',
      body: { position: adjustSeatPos.value, ...params },
    })
  } finally {
    loadingAction.value = null
  }
}

async function doRearSeats() {
  loadingAction.value = 'rear-seats'
  try {
    await props.onExec({
      action: 'rear-seats',
      body: { seat_info: rearSeatInfo.value },
    })
  } finally {
    loadingAction.value = null
  }
}
</script>

<style scoped>
.sc-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.sc-modal {
  background: var(--card); border-radius: 16px; padding: 0;
  width: 92vw; max-width: 420px;
  box-shadow: 0 12px 40px rgba(0,0,0,.4); overflow: hidden;
}
.sc-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,.06);
}
.sc-header-left { display: flex; align-items: center; gap: 8px; }
.sc-header-icon { color: var(--amber); }
.sc-title { font-size: 15px; font-weight: 600; color: var(--text); }
.sc-close {
  background: none; border: none; color: var(--muted); font-size: 22px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.sc-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }

.sc-tab-toggle {
  display: flex; gap: 4px; background: var(--bg); border-radius: 10px; padding: 3px;
}
.sc-tab-btn {
  flex: 1; padding: 7px 0; border: none; border-radius: 8px; cursor: pointer;
  background: transparent; color: var(--muted); font-size: 12px; font-weight: 500;
  transition: all .2s; text-align: center;
}
.sc-tab-btn.active { background: var(--card); color: var(--text); box-shadow: 0 2px 8px rgba(0,0,0,.2); }

.sc-section-label { font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }

.sc-adjust-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.sc-adjust-btn {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 12px 8px; border: 1px solid rgba(255,255,255,.08); border-radius: 10px;
  background: var(--bg); color: var(--text); cursor: pointer;
  transition: all .2s; font-size: 11px; font-weight: 500;
}
.sc-adjust-btn:hover { border-color: var(--amber); background: rgba(255,171,64,.06); }
.sc-adjust-btn.loading { opacity: 0.5; cursor: wait; }
.sc-adjust-btn:disabled { pointer-events: none; }

.sc-mode-toggle {
  display: flex; gap: 8px; background: var(--bg); border-radius: 10px; padding: 4px;
}
.sc-mode-btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 8px; border: none; border-radius: 8px; cursor: pointer;
  background: transparent; color: var(--muted); font-size: 13px; font-weight: 500;
  transition: all .2s;
}
.sc-mode-btn.active { background: var(--card); color: var(--text); box-shadow: 0 2px 8px rgba(0,0,0,.2); }

.sc-positions {
  display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
}
.sc-pos-btn {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 12px 8px; border: 1px solid rgba(255,255,255,.08); border-radius: 10px;
  background: var(--bg); color: var(--text); cursor: pointer;
  transition: all .2s; font-size: 13px;
}
.sc-pos-btn.selected { border-color: var(--amber); background: rgba(255,171,64,.08); }
.sc-pos-label { font-weight: 500; }
.sc-pos-status { font-size: 11px; color: var(--muted); }

.sc-level { display: flex; align-items: center; gap: 12px; }
.sc-level-label { font-size: 13px; color: var(--muted); white-space: nowrap; }
.sc-level-btns { display: flex; gap: 6px; flex: 1; }
.sc-level-btn {
  flex: 1; padding: 8px 0; border: 1px solid rgba(255,255,255,.08); border-radius: 8px;
  background: var(--bg); color: var(--muted); cursor: pointer;
  font-size: 12px; font-weight: 500; transition: all .2s; text-align: center;
}
.sc-level-btn.active { border-color: var(--amber); color: var(--text); background: rgba(255,171,64,.08); }

.sc-status {
  display: flex; flex-direction: column; gap: 4px;
  padding: 10px 12px; background: var(--bg); border-radius: 10px;
  font-size: 12px;
}
.sc-status-row { display: flex; justify-content: space-between; color: var(--muted); }
.sc-status-val { color: var(--text); font-weight: 500; }

.sc-apply {
  width: 100%; padding: 10px; border: none; border-radius: 10px;
  background: var(--amber); color: #000; font-weight: 600;
  font-size: 14px; cursor: pointer; transition: opacity .2s;
  display: flex; align-items: center; justify-content: center; gap: 6px;
}
.sc-apply:disabled { opacity: .5; cursor: not-allowed; }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 1s linear infinite; }
</style>
