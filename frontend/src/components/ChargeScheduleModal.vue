<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="cs-overlay" @click.self="$emit('close')">
        <div class="cs-modal">
          <div class="cs-header">
            <div class="cs-header-left">
              <CalendarClock :size="16" class="cs-header-icon" />
              <span class="cs-title">Charge Schedule</span>
            </div>
            <button class="cs-close" @click="$emit('close')">&times;</button>
          </div>

          <div class="cs-body">
            <!-- Current status -->
            <div v-if="chargePlan" class="cs-current">
              <div class="cs-current-title">Current Schedule</div>
              <div class="cs-current-grid">
                <div class="cs-current-item">
                  <span class="cs-current-label">Status</span>
                  <span class="cs-current-val" :class="{ 'cs-on': chargePlan.enabled === 1 }">
                    {{ chargePlan.enabled === 1 ? 'Active' : 'Inactive' }}
                  </span>
                </div>
                <div class="cs-current-item" v-if="chargePlan.start">
                  <span class="cs-current-label">Start</span>
                  <span class="cs-current-val">{{ chargePlan.start }}</span>
                </div>
                <div class="cs-current-item" v-if="chargePlan.end">
                  <span class="cs-current-label">End</span>
                  <span class="cs-current-val">{{ chargePlan.end }}</span>
                </div>
                <div class="cs-current-item" v-if="chargePlan.cycles">
                  <span class="cs-current-label">Days</span>
                  <span class="cs-current-val">{{ formatCycles(chargePlan.cycles) }}</span>
                </div>
              </div>
            </div>

            <!-- Enable toggle -->
            <div class="cs-row">
              <span class="cs-label">Enabled</span>
              <button class="cs-toggle" :class="{ on: enabled }" @click="enabled = !enabled">
                <span class="cs-toggle-dot" />
              </button>
            </div>

            <!-- SOC Limit -->
            <div class="cs-field">
              <div class="cs-field-header">
                <span class="cs-label">Charge Limit</span>
                <span class="cs-field-val">{{ socLimit }}%</span>
              </div>
              <input type="range" min="20" max="100" step="5" v-model.number="socLimit" class="cs-slider" />
            </div>

            <!-- Time pickers -->
            <div class="cs-time-row">
              <div class="cs-time-field">
                <span class="cs-label">Start Time</span>
                <input type="time" v-model="startTime" class="cs-input" />
              </div>
              <div class="cs-time-field">
                <span class="cs-label">End Time</span>
                <input type="time" v-model="endTime" class="cs-input" />
              </div>
            </div>

            <!-- Days of week -->
            <div class="cs-field">
              <span class="cs-label">Days</span>
              <div class="cs-days">
                <button
                  v-for="d in dayOptions"
                  :key="d.value"
                  class="cs-day-btn"
                  :class="{ active: selectedDays.has(d.value) }"
                  @click="toggleDay(d.value)"
                >{{ d.short }}</button>
              </div>
            </div>

            <!-- Repeat mode -->
            <div class="cs-row">
              <span class="cs-label">Repeat Weekly</span>
              <button class="cs-toggle" :class="{ on: circulation === 1 }" @click="circulation = circulation === 1 ? 0 : 1">
                <span class="cs-toggle-dot" />
              </button>
            </div>

            <!-- Auto recharge -->
            <div class="cs-row">
              <span class="cs-label">Auto Recharge</span>
              <button class="cs-toggle" :class="{ on: recharge === 1 }" @click="recharge = recharge === 1 ? 0 : 1">
                <span class="cs-toggle-dot" />
              </button>
            </div>

            <!-- Apply -->
            <button
              class="cs-apply"
              :disabled="!!loading || !startTime || !endTime || selectedDays.size === 0"
              @click="apply"
            >
              <Loader v-if="loading" :size="16" class="spinning" />
              <span v-else>{{ enabled ? 'Set Schedule' : 'Disable Schedule' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { CalendarClock, Loader } from 'lucide-vue-next'
import { api } from '../composables/useApi'

const props = defineProps({
  visible: Boolean,
  onExec: Function,
  chargePlan: Object,
  currentSoc: Number,
  vin: String,
})

defineEmits(['close'])

const enabled = ref(true)
const socLimit = ref(80)
const startTime = ref('23:00')
const endTime = ref('07:00')
const circulation = ref(1)
const recharge = ref(0)
const loading = ref(false)
const cloudSchedule = ref(null)

const selectedDays = reactive(new Set([1, 2, 3, 4, 5, 6, 7]))

const dayOptions = [
  { value: 1, short: 'Mon' },
  { value: 2, short: 'Tue' },
  { value: 3, short: 'Wed' },
  { value: 4, short: 'Thu' },
  { value: 5, short: 'Fri' },
  { value: 6, short: 'Sat' },
  { value: 7, short: 'Sun' },
]

function toggleDay(val) {
  if (selectedDays.has(val)) selectedDays.delete(val)
  else selectedDays.add(val)
}

function formatCycles(cycles) {
  if (!cycles) return '—'
  const map = { 1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun' }
  return cycles.split(',').map(d => map[d.trim()] || d).join(', ')
}

// Sync from current plan when modal opens, then try cloud
watch(() => props.visible, async (val) => {
  if (!val) return
  // First populate from vehicle status (immediate)
  if (props.chargePlan) {
    applyPlan(props.chargePlan)
  }
  // Then try to fetch richer data from cloud
  if (props.vin) {
    try {
      const cloud = await api('GET', `/api/vehicles/${props.vin}/charge-schedule`)
      cloudSchedule.value = cloud
      if (cloud && Object.keys(cloud).length > 0) {
        applyCloudSchedule(cloud)
      }
    } catch (err) {
      console.error('Failed to fetch charge schedule from cloud:', err)
    }
  }
})

function applyPlan(p) {
  enabled.value = p.enabled === 1
  if (p.soc_setting != null) socLimit.value = p.soc_setting
  else if (props.currentSoc != null) socLimit.value = props.currentSoc
  if (p.start) startTime.value = p.start
  if (p.end) endTime.value = p.end
  circulation.value = p.circulation ?? 1
  recharge.value = p.recharge ?? 0
  selectedDays.clear()
  if (p.cycles) {
    p.cycles.split(',').forEach(d => {
      const n = parseInt(d.trim())
      if (n >= 1 && n <= 7) selectedDays.add(n)
    })
  } else {
    for (let i = 1; i <= 7; i++) selectedDays.add(i)
  }
}

function applyCloudSchedule(c) {
  // Cloud schedule fields: chargeEnable/charge_enable, chargesoc, starttime, endtime, cycles, circulation, recharge
  const en = c.chargeEnable ?? c.charge_enable
  if (en != null) enabled.value = en === 1 || en === '1' || en === true
  const soc = c.chargesoc ?? c.charge_soc
  if (soc != null) socLimit.value = parseInt(soc, 10) || 80
  const st = c.starttime ?? c.start_time
  if (st) startTime.value = st
  const et = c.endtime ?? c.end_time
  if (et) endTime.value = et
  if (c.circulation != null) circulation.value = parseInt(c.circulation, 10) || 0
  if (c.recharge != null) recharge.value = parseInt(c.recharge, 10) || 0
  const cy = c.cycles
  if (cy) {
    selectedDays.clear()
    String(cy).split(',').forEach(d => {
      const n = parseInt(d.trim())
      if (n >= 1 && n <= 7) selectedDays.add(n)
    })
  }
}

async function apply() {
  loading.value = true
  try {
    const cycles = Array.from(selectedDays).sort().join(',')
    await props.onExec({
      action: 'charge-schedule',
      body: {
        enabled: enabled.value,
        soc_limit: socLimit.value,
        start_time: startTime.value,
        end_time: endTime.value,
        cycles,
        circulation: circulation.value,
        recharge: recharge.value,
      },
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cs-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(0,0,0,.55); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.cs-modal {
  background: var(--card); border-radius: 16px; padding: 0;
  width: 92vw; max-width: 440px;
  box-shadow: 0 12px 40px rgba(0,0,0,.4); overflow: hidden;
  max-height: 90vh; overflow-y: auto;
}
.cs-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,.06);
  position: sticky; top: 0; background: var(--card); z-index: 1;
}
.cs-header-left { display: flex; align-items: center; gap: 8px; }
.cs-header-icon { color: #00e676; }
.cs-title { font-size: 15px; font-weight: 600; color: var(--text); }
.cs-close {
  background: none; border: none; color: var(--muted); font-size: 22px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.cs-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }

/* Current status */
.cs-current {
  background: var(--bg); border-radius: 12px; padding: 14px;
}
.cs-current-title {
  font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase;
  letter-spacing: 0.06em; margin-bottom: 10px;
}
.cs-current-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.cs-current-item { display: flex; flex-direction: column; gap: 2px; }
.cs-current-label { font-size: 11px; color: var(--muted2); }
.cs-current-val { font-size: 14px; font-weight: 600; color: var(--text); }
.cs-current-val.cs-on { color: #00e676; }

/* Form */
.cs-label { font-size: 13px; font-weight: 500; color: var(--text); }
.cs-row {
  display: flex; align-items: center; justify-content: space-between;
}
.cs-field { display: flex; flex-direction: column; gap: 8px; }
.cs-field-header { display: flex; justify-content: space-between; align-items: center; }
.cs-field-val { font-size: 15px; font-weight: 700; color: var(--text); }
.cs-slider { width: 100%; accent-color: #00e676; }

.cs-time-row { display: flex; gap: 12px; }
.cs-time-field { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.cs-input {
  padding: 10px 12px; border: 1px solid rgba(255,255,255,.1); border-radius: 10px;
  background: var(--bg); color: var(--text); font-size: 14px;
  outline: none; transition: border-color .2s;
}
.cs-input:focus { border-color: #00e676; }

/* Days */
.cs-days { display: flex; gap: 6px; }
.cs-day-btn {
  flex: 1; padding: 8px 0; border: 1px solid rgba(255,255,255,.08); border-radius: 8px;
  background: var(--bg); color: var(--muted); cursor: pointer;
  font-size: 11px; font-weight: 600; transition: all .2s; text-align: center;
}
.cs-day-btn.active {
  border-color: #00e676; color: #00e676;
  background: rgba(0,230,118,.08);
}

/* Toggle */
.cs-toggle {
  width: 44px; height: 24px; border-radius: 12px; border: none;
  background: rgba(255,255,255,.1); cursor: pointer;
  position: relative; transition: background .2s;
  padding: 0;
}
.cs-toggle.on { background: #00e676; }
.cs-toggle-dot {
  position: absolute; top: 3px; left: 3px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #fff; transition: transform .2s;
  box-shadow: 0 1px 3px rgba(0,0,0,.3);
}
.cs-toggle.on .cs-toggle-dot { transform: translateX(20px); }

/* Apply */
.cs-apply {
  width: 100%; padding: 12px; border: none; border-radius: 10px;
  background: #00e676; color: #000; font-weight: 600; font-size: 14px;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: opacity .2s;
}
.cs-apply:hover { opacity: 0.9; }
.cs-apply:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-enter-active, .modal-leave-active { transition: opacity .2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

@keyframes lm-spin { to { transform: rotate(360deg); } }
.spinning { animation: lm-spin .7s linear infinite; }
</style>
