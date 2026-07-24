<script setup lang="ts">
import { ref, watch } from 'vue'
import { showToast } from 'vant'
import type { ScheduleEvent } from '@/api/schedule'

interface Props {
  modelValue: boolean
  event?: ScheduleEvent | null
  defaultDate?: string | null
}
const props = defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean]; saved: [event: ScheduleEvent] }>()

import scheduleApi from '@/api/schedule'

const form = ref({
  title: '',
  event_type: 'game' as 'game' | 'training' | 'internal' | 'other',
  start_date: '',
  end_date: '',
  description: '',
})

const saving = ref(false)
const showStartPicker = ref(false)
const showEndPicker = ref(false)

function todayDateString() {
  return new Date().toISOString().slice(0, 10)
}

function formatDate(value: Date) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function toNativeDate(value?: string | null) {
  return value ? new Date(`${value}T12:00:00`) : new Date()
}

watch([() => props.modelValue, () => props.event?.id, () => props.defaultDate], ([isOpen]) => {
  if (!isOpen) return
  if (props.event) {
    form.value = {
      title: props.event.title,
      event_type: props.event.event_type,
      start_date: props.event.start_date,
      end_date: props.event.end_date,
      description: props.event.description ?? '',
    }
  } else {
    const seedDate = props.defaultDate || todayDateString()
    form.value = { title: '', event_type: 'game', start_date: seedDate, end_date: seedDate, description: '' }
  }
}, { immediate: true })

function openStartCalendar() {
  showStartPicker.value = true
}

function openEndCalendar() {
  showEndPicker.value = true
}

function onStartConfirm(value: Date | Date[]) {
  const chosen = Array.isArray(value) ? (value[0] ?? new Date()) : value
  const picked = formatDate(chosen)
  form.value.start_date = picked
  if (!form.value.end_date || form.value.end_date < picked) {
    form.value.end_date = picked
  }
  showStartPicker.value = false
}
function onEndConfirm(value: Date | Date[]) {
  const chosen = Array.isArray(value) ? (value[0] ?? new Date()) : value
  const picked = formatDate(chosen)
  form.value.end_date = picked
  if (form.value.start_date > picked) {
    form.value.start_date = picked
  }
  showEndPicker.value = false
}

async function save() {
  if (!form.value.title.trim()) return showToast('请填写标题')
  if (!form.value.start_date || !form.value.end_date) return showToast('请选择日期')
  saving.value = true
  try {
    let ev: ScheduleEvent
    if (props.event?.id) {
      ev = await scheduleApi.updateEvent(props.event.id, form.value)
    } else {
      ev = await scheduleApi.createEvent(form.value)
    }
    showToast(props.event?.id ? '已更新 ✓' : '已创建 ✓')
    emit('saved', ev)
    emit('update:modelValue', false)
  } catch (e: any) {
    showToast(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <van-popup
    :show="modelValue"
    @update:show="emit('update:modelValue', $event)"
    position="bottom"
    round
    class="schedule-sheet-popup"
    :style="{ maxHeight: '85vh', overflowY: 'auto' }"
  >
    <div class="form-popup">
      <div class="popup-header">
        <span>{{ event?.id ? '编辑活动' : '新建活动' }}</span>
        <van-icon name="cross" @click="emit('update:modelValue', false)" />
      </div>

      <van-cell-group inset>
        <van-field v-model="form.title" label="标题" placeholder="请填写活动标题" required />

        <van-field name="event_type" label="类型">
          <template #input>
            <van-radio-group v-model="form.event_type" direction="horizontal">
              <van-radio name="game">🏆 外战</van-radio>
              <van-radio name="internal">🆚 内战</van-radio>
              <van-radio name="training">🏋️ 训练</van-radio>
              <van-radio name="other">📌 其他</van-radio>
            </van-radio-group>
          </template>
        </van-field>

        <van-field
          v-model="form.start_date"
          label="开始日期"
          readonly
          is-link
          @click="openStartCalendar"
        />
        <van-field
          v-model="form.end_date"
          label="结束日期"
          readonly
          is-link
          @click="openEndCalendar"
        />
        <van-field v-model="form.description" label="描述" type="textarea" rows="2" placeholder="可选" />
      </van-cell-group>

      <div style="margin: 16px">
        <van-button round block type="primary" :loading="saving" @click="save">
          {{ event?.id ? '保存修改' : '创建活动' }}
        </van-button>
      </div>
    </div>

    <van-calendar
      v-model:show="showStartPicker"
      :default-date="toNativeDate(form.start_date || props.defaultDate)"
      color="#1e88e5"
      @confirm="onStartConfirm"
    />
    <van-calendar
      v-model:show="showEndPicker"
      :default-date="toNativeDate(form.end_date || form.start_date || props.defaultDate)"
      color="#43a047"
      @confirm="onEndConfirm"
    />
  </van-popup>
</template>

<style scoped>
.form-popup {
  padding: 0 0 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #eef6ff 100%);
}
.popup-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 16px 14px; font-size: 16px; font-weight: 700; color: #0f2742;
  border-bottom: 1px solid #dbe7f3;
  margin-bottom: 10px;
}
:deep(.schedule-sheet-popup) {
  background: linear-gradient(180deg, #fbfdff 0%, #eef6ff 100%) !important;
  color: #102238 !important;
}
:deep(.schedule-sheet-popup .van-cell-group),
:deep(.schedule-sheet-popup .van-cell),
:deep(.schedule-sheet-popup .van-field) {
  background: #ffffff !important;
  color: #102238 !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
:deep(.schedule-sheet-popup .van-field__label),
:deep(.schedule-sheet-popup .van-field__control),
:deep(.schedule-sheet-popup .van-radio__label),
:deep(.schedule-sheet-popup .van-cell__title),
:deep(.schedule-sheet-popup .van-cell__value) {
  color: #102238 !important;
}
:deep(.schedule-sheet-popup .van-field__control::placeholder) {
  color: #8aa0b6 !important;
}
:deep(.schedule-sheet-popup .van-radio-group) {
  gap: 8px;
  flex-wrap: wrap;
}
:deep(.schedule-sheet-popup .van-radio) {
  padding: 6px 8px;
  border-radius: 999px;
  background: #f3f8ff;
}
:deep(.schedule-sheet-popup .van-button) {
  font-weight: 600;
  border-radius: 12px;
  box-shadow: none;
}
:deep(.schedule-sheet-popup .van-button--primary) {
  background: #0a84ff;
  border: none;
  color: #fff;
}
:deep(.van-calendar) {
  background: #f8fbff;
  color: #102238;
}
:deep(.van-calendar__header) {
  background: #f8fbff;
  color: #102238;
}
:deep(.van-calendar__title),
:deep(.van-calendar__subtitle),
:deep(.van-calendar__weekday),
:deep(.van-calendar__month-title),
:deep(.van-calendar__day) {
  color: #102238;
}
:deep(.van-calendar__selected-day) {
  background: #1e88e5;
  color: #fff;
}
:deep(.van-calendar__confirm) {
  background: #1e88e5;
  border: none;
}
</style>
