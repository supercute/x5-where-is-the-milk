<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { Map, Plus } from '@lucide/vue'

const props = defineProps({
  store: { type: Object, required: true },
  shelves: { type: Array, default: () => [] },
  selectedId: { type: Number, default: null },
})

const emit = defineEmits(['select', 'move', 'add'])

const stage = ref(null)
const drag = ref(null)

const mapWidth = computed(() => props.store.map_width || 100)
const mapHeight = computed(() => props.store.map_height || 64)
const aspectRatio = computed(() => `${mapWidth.value} / ${mapHeight.value}`)

const entranceStyle = computed(() => ({
  left: `${(props.store.entrance_x / mapWidth.value) * 100}%`,
  top: `${(props.store.entrance_y / mapHeight.value) * 100}%`,
}))

function shelfStyle(shelf) {
  const active = drag.value && drag.value.shelfId === shelf.id
  const x = active ? drag.value.x : shelf.x
  const y = active ? drag.value.y : shelf.y
  return {
    left: `${(x / mapWidth.value) * 100}%`,
    top: `${(y / mapHeight.value) * 100}%`,
    width: `${(shelf.width / mapWidth.value) * 100}%`,
    height: `${(shelf.height / mapHeight.value) * 100}%`,
    '--shelf-color': shelf.color,
  }
}

function startDrag(event, shelf) {
  if (event.button !== 0) return
  emit('select', shelf.id)
  const rect = stage.value?.getBoundingClientRect()
  if (!rect) return

  event.preventDefault()
  drag.value = {
    shelfId: shelf.id,
    startClientX: event.clientX,
    startClientY: event.clientY,
    originX: shelf.x,
    originY: shelf.y,
    x: shelf.x,
    y: shelf.y,
    width: shelf.width,
    height: shelf.height,
    moved: false,
    rect,
  }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', stopDrag)
}

function onPointerMove(event) {
  if (!drag.value) return
  const state = drag.value
  const dx = ((event.clientX - state.startClientX) / state.rect.width) * mapWidth.value
  const dy = ((event.clientY - state.startClientY) / state.rect.height) * mapHeight.value
  if (Math.abs(event.clientX - state.startClientX) > 2 || Math.abs(event.clientY - state.startClientY) > 2) {
    state.moved = true
  }
  state.x = Math.round(Math.max(0, Math.min(state.originX + dx, mapWidth.value - state.width)))
  state.y = Math.round(Math.max(0, Math.min(state.originY + dy, mapHeight.value - state.height)))
}

function stopDrag() {
  const state = drag.value
  removeListeners()
  if (!state) return
  drag.value = null
  if (state.moved) {
    emit('move', { shelfId: state.shelfId, x: state.x, y: state.y })
  }
}

function removeListeners() {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', stopDrag)
}

onBeforeUnmount(removeListeners)

function selectShelf(id) {
  emit('select', id)
}

const selectedShelf = computed(
  () => props.shelves.find((shelf) => shelf.id === props.selectedId) || null,
)
</script>

<template>
  <section class="map-panel">
    <div class="map-heading">
      <div>
        <p class="eyebrow">Редактор зала</p>
        <h2>Карта магазина</h2>
        <p class="map-note">Перетаскивайте стеллажи. Точные размеры не нужны.</p>
      </div>
      <button class="primary-button" type="button" @click="$emit('add')">
        <Plus :size="16" />
        Стеллаж
      </button>
    </div>

    <div class="map-frame">
      <div
        ref="stage"
        class="map-stage"
        :style="{ aspectRatio }"
        @pointerdown.self="emit('select', null)"
      >
        <div class="floor-glow"></div>

        <div
          v-for="shelf in shelves"
          :key="shelf.id"
          class="map-shelf"
          :class="{
            selected: selectedId === shelf.id,
            dragging: drag && drag.shelfId === shelf.id,
            compact: shelf.width < 16 || shelf.height < 9,
            wide: shelf.width > 22,
          }"
          :style="shelfStyle(shelf)"
          role="button"
          tabindex="0"
          :aria-label="`Стеллаж ${shelf.name}, ${shelf.levels_count} полок`"
          @pointerdown="startDrag($event, shelf)"
          @keydown.enter.prevent="selectShelf(shelf.id)"
          @keydown.space.prevent="selectShelf(shelf.id)"
        >
          <span class="map-shelf-stripe"></span>
          <span class="map-shelf-name">{{ shelf.name }}</span>
          <span class="map-shelf-meta">{{ shelf.levels_count }} полок</span>
        </div>

        <div class="entrance" :style="entranceStyle">
          <span class="entrance-label">{{ store.entrance_label || 'Вход' }}</span>
          <span class="entrance-marker"></span>
        </div>

        <div v-if="!shelves.length" class="map-empty">
          <Map :size="24" />
          <strong>Пока пусто</strong>
          <span>Добавьте первый стеллаж и перетащите его на карте</span>
        </div>

        <span class="map-compass">Схема сверху</span>
      </div>

      <div class="map-footer">
        <div v-if="selectedShelf" class="selection-hint">
          <span class="selection-dot" :style="{ background: selectedShelf.color }"></span>
          <span>
            Выбран <strong>{{ selectedShelf.name }}</strong>
            <template v-if="selectedShelf.location_hint">
              · {{ selectedShelf.location_hint }}
            </template>
          </span>
        </div>
        <div v-else class="selection-hint muted">
          <span class="selection-dot neutral"></span>
          <span>Выберите стеллаж, чтобы настроить полки</span>
        </div>

        <div class="map-legend">
          <span><i class="legend-swatch"></i> стеллаж</span>
          <span><i class="legend-dot"></i> вход</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.map-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  padding: 24px 28px;
  overflow-y: auto;
}

.map-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.eyebrow {
  margin: 0 0 3px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 500;
}

h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 500;
  letter-spacing: 0;
}

.map-note {
  margin: 5px 0 0;
  color: var(--secondary);
  font-size: 12px;
}

.primary-button {
  flex: 0 0 auto;
}

.map-frame {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  min-height: 0;
  margin-top: 20px;
}

.map-stage {
  position: relative;
  width: 100%;
  min-height: 280px;
  max-height: 100%;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-card);
  background-color: var(--surface-raised);
  background-image:
    linear-gradient(rgb(94 103 94 / 8%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(94 103 94 / 8%) 1px, transparent 1px);
  background-size: 8.333% 12.5%;
  overflow: hidden;
  touch-action: none;
}

.floor-glow {
  position: absolute;
  inset: 5%;
  border: 1px dashed rgb(94 103 94 / 20%);
  border-radius: 8px;
  pointer-events: none;
}

.map-shelf {
  position: absolute;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 42px;
  min-height: 30px;
  padding: 6px 8px 6px 13px;
  border: 1px solid color-mix(in srgb, var(--shelf-color) 45%, var(--line-strong));
  border-radius: 6px;
  background: color-mix(in srgb, var(--shelf-color) 12%, var(--surface-raised));
  color: var(--ink);
  cursor: grab;
  text-align: left;
  user-select: none;
  transition:
    background-color 160ms var(--ease),
    border-color 160ms var(--ease),
    box-shadow 160ms var(--ease);
}

.map-shelf:hover {
  border-color: color-mix(in srgb, var(--shelf-color) 65%, var(--ink));
  background: color-mix(in srgb, var(--shelf-color) 18%, var(--surface-raised));
}

.map-shelf.selected {
  border-color: var(--ink);
  box-shadow: 0 0 0 2px var(--ink);
}

.map-shelf.dragging {
  z-index: 5;
  cursor: grabbing;
  box-shadow: 0 8px 20px rgb(30 36 30 / 14%);
}

.map-shelf-stripe {
  position: absolute;
  top: 7px;
  bottom: 7px;
  left: 5px;
  width: 3px;
  border-radius: 2px;
  background: var(--shelf-color);
}

.map-shelf-name {
  display: -webkit-box;
  overflow: hidden;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.1;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.map-shelf-meta {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  color: var(--secondary);
  font-size: 10px;
  font-weight: 400;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.map-shelf.compact {
  padding: 4px 5px 4px 11px;
}

.map-shelf.compact .map-shelf-name {
  font-size: 9px;
  line-height: 1.05;
}

.map-shelf.compact .map-shelf-meta {
  display: none;
}

.entrance {
  position: absolute;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  transform: translate(-50%, -100%);
  pointer-events: none;
}

.entrance-label {
  color: var(--accent-ink);
  font-size: 10px;
  font-weight: 500;
}

.entrance-marker {
  width: 10px;
  height: 10px;
  border: 2px solid var(--surface-raised);
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 1px 2px rgb(30 36 30 / 12%);
}

.map-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  color: var(--secondary);
  text-align: center;
  transform: translate(-50%, -50%);
}

.map-empty > svg {
  margin-bottom: 4px;
  color: var(--muted);
  stroke-width: 1.5;
}

.map-empty strong {
  color: var(--ink);
  font-size: 13px;
  font-weight: 500;
}

.map-empty span {
  max-width: 240px;
  font-size: 11px;
}

.map-compass {
  position: absolute;
  top: 12px;
  right: 14px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 400;
  pointer-events: none;
}

.map-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 12px;
}

.selection-hint {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: var(--secondary);
  font-size: 11px;
}

.selection-hint span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selection-hint strong {
  color: var(--ink);
  font-weight: 500;
}

.selection-hint.muted {
  color: var(--muted);
}

.selection-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.selection-dot.neutral {
  border: 1px solid var(--line-strong);
  background: transparent;
}

.map-legend {
  display: flex;
  flex: 0 0 auto;
  gap: 14px;
  color: var(--muted);
  font-size: 10px;
}

.map-legend span {
  display: flex;
  align-items: center;
  gap: 5px;
}

.legend-swatch {
  width: 12px;
  height: 7px;
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  background: var(--surface-raised);
}

.legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
}

@media (max-width: 1100px) {
  .map-panel {
    padding: 22px;
  }

  .map-stage {
    max-height: 480px;
  }
}

@media (max-width: 640px) {
  .map-heading {
    align-items: center;
  }

  h2 {
    font-size: 21px;
  }

  .map-note,
  .map-legend {
    display: none;
  }

  .map-shelf-meta {
    display: none;
  }

  .map-footer {
    margin-top: 10px;
  }
}
</style>
