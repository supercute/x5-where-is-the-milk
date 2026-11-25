<script setup>
import { computed, ref } from 'vue'
import { ArrowLeftRight, Minus, Plus, Trash2, X } from '@lucide/vue'

const props = defineProps({
  shelf: { type: Object, default: null },
})

const emit = defineEmits(['save-field', 'set-levels', 'place', 'unplace', 'delete-shelf'])

const MIME = 'application/x-shelf-category'
const colors = ['#4F8EF7', '#0EA5E9', '#14B8A6', '#22C55E', '#84CC16', '#F59E0B', '#F97316', '#EF4444', '#EC4899', '#8B5CF6']

const dragOverLevel = ref(null)
const dropTargetId = ref(null)

const categoryCount = computed(
  () => props.shelf?.levels.reduce((sum, level) => sum + level.categories.length, 0) || 0,
)
const categoryCountLabel = computed(() => {
  const count = categoryCount.value
  const last = count % 10
  const lastTwo = count % 100
  let word = 'категорий'
  if (last === 1 && lastTwo !== 11) word = 'категория'
  else if ([2, 3, 4].includes(last) && ![12, 13, 14].includes(lastTwo)) {
    word = 'категории'
  }
  return `${count} ${word}`
})

function commitField(field, value) {
  if (!props.shelf) return
  const clean = typeof value === 'string' ? value.trim() : value
  if (field === 'name' && !clean) return
  if (props.shelf[field] === clean) return
  emit('save-field', { field, value: clean })
}

function setColor(color) {
  if (!props.shelf || props.shelf.color === color) return
  emit('save-field', { field: 'color', value: color })
}

function changeLevels(delta) {
  if (!props.shelf) return
  const next = Math.max(1, Math.min(15, props.shelf.levels_count + delta))
  if (next === props.shelf.levels_count) return
  if (next < props.shelf.levels_count) {
    const removed = props.shelf.levels.filter((level) => level.position >= next)
    const removedCategories = removed.reduce((sum, level) => sum + level.categories.length, 0)
    if (
      removedCategories > 0 &&
      !window.confirm(
        `На удаляемых полках ${removedCategories} кат. товаров. Они вернутся в палитру. Продолжить?`,
      )
    ) {
      return
    }
  }
  emit('set-levels', next)
}

function readPayload(event) {
  try {
    const raw = event.dataTransfer.getData(MIME)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function startCategoryDrag(event, category, level) {
  const payload = {
    categoryId: category.id,
    fromLevelId: level.id,
    fromPosition: category.position,
  }
  event.dataTransfer.setData(MIME, JSON.stringify(payload))
  event.dataTransfer.setData('text/plain', category.name)
  event.dataTransfer.effectAllowed = 'move'
}

function onDragEnd() {
  dragOverLevel.value = null
  dropTargetId.value = null
}

function onLevelDragOver(event, level) {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
  dragOverLevel.value = level.id
  dropTargetId.value = null
}

function onLevelDragLeave(event, level) {
  if (event.currentTarget.contains(event.relatedTarget)) return
  if (dragOverLevel.value === level.id) dragOverLevel.value = null
}

function onLevelDrop(event, level) {
  event.preventDefault()
  const payload = readPayload(event)
  dragOverLevel.value = null
  dropTargetId.value = null
  if (!payload) return
  emit('place', {
    categoryId: payload.categoryId,
    shelfLevelId: level.id,
    position: level.categories.length,
  })
}

function onCategoryDragOver(event, level, category) {
  event.preventDefault()
  event.stopPropagation()
  event.dataTransfer.dropEffect = 'move'
  dragOverLevel.value = level.id
  dropTargetId.value = category.id
}

function onCategoryDragLeave(event) {
  if (event.currentTarget.contains(event.relatedTarget)) return
  dropTargetId.value = null
}

function onCategoryDrop(event, level, category, targetIndex) {
  event.preventDefault()
  event.stopPropagation()
  const payload = readPayload(event)
  dragOverLevel.value = null
  dropTargetId.value = null
  if (!payload || payload.categoryId === category.id) return

  let position = targetIndex
  if (
    payload.fromLevelId === level.id &&
    payload.fromPosition !== null &&
    payload.fromPosition < targetIndex
  ) {
    position -= 1
  }
  emit('place', {
    categoryId: payload.categoryId,
    shelfLevelId: level.id,
    position,
  })
}

function removeFromShelf(category) {
  emit('unplace', category.id)
}

function confirmDelete() {
  if (!props.shelf) return
  if (
    window.confirm(
      `Удалить стеллаж «${props.shelf.name}»? Категории с его полок вернутся в палитру.`,
    )
  ) {
    emit('delete-shelf')
  }
}

function categoryStyle(category) {
  return {
    '--cat-color': category.color,
  }
}
</script>

<template>
  <aside class="inspector">
    <div v-if="!shelf" class="inspector-empty">
      <div class="empty-illustration">
        <span class="empty-shelf-row"></span>
        <span class="empty-shelf-row"></span>
        <span class="empty-shelf-row"></span>
        <span class="empty-shelf-row"></span>
      </div>
      <p class="eyebrow">Редактор стеллажа</p>
      <h2>Выберите стеллаж</h2>
      <p>
        Нажмите на стеллаж на карте, чтобы увидеть его полки и расставить
        категории товаров.
      </p>
      <div class="empty-steps">
        <span><b>1</b> Создайте стеллаж</span>
        <span><b>2</b> Задайте число полок</span>
        <span><b>3</b> Перетащите категории</span>
      </div>
    </div>

    <template v-else>
      <div class="inspector-heading">
        <div>
          <p class="eyebrow">Редактор стеллажа</p>
          <h2>{{ shelf.name }}</h2>
        </div>
        <button class="icon-button danger" type="button" title="Удалить стеллаж" @click="confirmDelete">
          <Trash2 :size="16" />
        </button>
      </div>

      <div class="form-grid">
        <label>
          <span>Название</span>
          <input
            :value="shelf.name"
            maxlength="120"
            @change="commitField('name', $event.target.value)"
            @keydown.enter.prevent="$event.target.blur()"
          />
        </label>
        <label>
          <span>Ориентир для покупателя</span>
          <input
            :value="shelf.location_hint"
            maxlength="300"
            placeholder="Например, справа от входа"
            @change="commitField('location_hint', $event.target.value)"
            @keydown.enter.prevent="$event.target.blur()"
          />
        </label>
      </div>

      <div class="settings-row">
        <div class="levels-control">
          <div>
            <span class="label">Количество полок</span>
            <small>Сверху вниз</small>
          </div>
          <div class="stepper">
            <button type="button" :disabled="shelf.levels_count <= 1" @click="changeLevels(-1)">
              <Minus :size="14" />
            </button>
            <strong>{{ shelf.levels_count }}</strong>
            <button type="button" :disabled="shelf.levels_count >= 15" @click="changeLevels(1)">
              <Plus :size="14" />
            </button>
          </div>
        </div>

        <div class="color-control">
          <span class="label">Цвет стеллажа</span>
          <div class="swatches">
            <button
              v-for="color in colors"
              :key="color"
              type="button"
              class="swatch"
              :class="{ active: shelf.color === color }"
              :style="{ background: color }"
              :aria-label="`Цвет ${color}`"
              @click="setColor(color)"
            ></button>
          </div>
        </div>
      </div>

      <div class="front-section">
        <div class="front-section-heading">
          <div>
            <span class="label">Вид спереди</span>
            <small>Перетаскивайте категории на полки и меняйте порядок слева направо</small>
          </div>
          <span class="placed-count">{{ categoryCountLabel }}</span>
        </div>

        <div class="shelf-front" :style="{ '--shelf-color': shelf.color }">
          <div class="front-crown">
            <span>{{ shelf.name }}</span>
            <span>Верх</span>
          </div>

          <div class="front-levels">
            <div
              v-for="level in shelf.levels"
              :key="level.id"
              class="front-level"
              :class="{ 'drag-over': dragOverLevel === level.id }"
              @dragover="onLevelDragOver($event, level)"
              @dragleave="onLevelDragLeave($event, level)"
              @drop="onLevelDrop($event, level)"
            >
              <div class="level-index">
                <span class="level-tab">{{ level.position + 1 }}</span>
              </div>

              <div class="level-items">
                <div
                  v-for="(category, index) in level.categories"
                  :key="category.id"
                  class="placed-category"
                  :class="{ 'drop-before': dropTargetId === category.id }"
                  :style="categoryStyle(category)"
                  draggable="true"
                  @dragstart="startCategoryDrag($event, category, level)"
                  @dragend="onDragEnd"
                  @dragover="onCategoryDragOver($event, level, category)"
                  @dragleave="onCategoryDragLeave"
                  @drop="onCategoryDrop($event, level, category, index)"
                >
                  <span class="category-color"></span>
                  <span class="placed-name">{{ category.name }}</span>
                  <button
                    class="remove-category"
                    type="button"
                    :title="`Убрать «${category.name}» с полки`"
                    @click.stop="removeFromShelf(category)"
                  >
                    <X :size="12" />
                  </button>
                </div>

                <div v-if="!level.categories.length" class="empty-level">
                  <Plus :size="12" />
                  Перетащите категорию сюда
                </div>
              </div>
            </div>
          </div>

          <div class="front-base"></div>
        </div>

        <p class="front-hint">
          <ArrowLeftRight :size="14" />
          Порядок блоков подсказывает агенту, что товар находится слева, в центре или справа.
        </p>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.inspector {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 20px;
  border-left: 1px solid var(--line);
  background: var(--surface);
  overflow-y: auto;
}

.inspector-empty {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 12px;
  text-align: center;
}

.empty-illustration {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 96px;
  padding: 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
}

.empty-shelf-row {
  height: 7px;
  border-radius: 2px;
  background: var(--surface-sunken);
}

.empty-shelf-row:nth-child(2) {
  width: 74%;
}

.empty-shelf-row:nth-child(3) {
  width: 86%;
}

.inspector-empty .eyebrow {
  margin-top: 24px;
}

.inspector-empty h2 {
  margin: 4px 0 8px;
  font-size: 21px;
  font-weight: 500;
  letter-spacing: 0;
}

.inspector-empty > p:not(.eyebrow) {
  max-width: 250px;
  margin: 0;
  color: var(--secondary);
  font-size: 12px;
  line-height: 1.55;
}

.empty-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 250px;
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  color: var(--secondary);
  font-size: 11px;
  text-align: left;
}

.empty-steps span {
  display: flex;
  align-items: center;
  gap: 8px;
}

.empty-steps b {
  display: grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 400;
}

.inspector-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.eyebrow {
  margin: 0 0 3px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 500;
}

h2 {
  margin: 0;
  overflow: hidden;
  font-size: 21px;
  font-weight: 500;
  letter-spacing: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.danger {
  flex: 0 0 auto;
  color: var(--muted);
}

.danger:hover {
  border-color: #e2cbc6;
  background: var(--danger-soft);
  color: var(--danger);
}

.form-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 20px;
}

.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--secondary);
  font-size: 11px;
  font-weight: 500;
}

.form-grid input {
  width: 100%;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  outline: 0;
  background: var(--surface-raised);
  color: var(--ink);
  font: inherit;
  font-size: 12px;
  font-weight: 400;
  transition:
    border-color 160ms var(--ease),
    box-shadow 160ms var(--ease);
}

.form-grid input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.settings-row {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 20px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  background: var(--surface-raised);
}

.levels-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.label {
  display: block;
  color: var(--secondary);
  font-size: 11px;
  font-weight: 500;
}

.levels-control small,
.front-section-heading small {
  display: block;
  margin-top: 2px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 400;
  line-height: 1.4;
}

.stepper {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}

.stepper button {
  display: grid;
  width: 30px;
  height: 30px;
  padding: 0;
  place-items: center;
  border: 0;
  background: transparent;
  color: var(--secondary);
  cursor: pointer;
}

.stepper button:hover:not(:disabled) {
  background: var(--surface-sunken);
  color: var(--ink);
}

.stepper button:disabled {
  color: var(--line-strong);
  cursor: default;
}

.stepper button svg {
  stroke-width: 1.5;
}

.stepper strong {
  min-width: 26px;
  color: var(--ink);
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 400;
  text-align: center;
}

.color-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.swatches {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.swatch {
  width: 17px;
  height: 17px;
  padding: 0;
  border: 2px solid var(--surface-raised);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 0 0 1px var(--line);
}

.swatch.active {
  box-shadow: 0 0 0 2px var(--ink);
}

.front-section {
  margin-top: 22px;
}

.front-section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.front-section-heading > div {
  min-width: 0;
}

.placed-count {
  flex: 0 0 auto;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.shelf-front {
  position: relative;
  border: 1px solid color-mix(in srgb, var(--shelf-color) 45%, var(--line-strong));
  border-radius: var(--radius-card);
  background: var(--surface-raised);
  overflow: hidden;
}

.front-crown {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 28px;
  padding: 0 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--shelf-color) 30%, var(--line));
  background: color-mix(in srgb, var(--shelf-color) 8%, var(--surface-raised));
  color: var(--secondary);
  font-size: 10px;
  font-weight: 500;
}

.front-crown span:last-child {
  color: var(--muted);
  font-size: 10px;
  font-weight: 400;
}

.front-levels {
  display: flex;
  flex-direction: column;
}

.front-level {
  display: flex;
  min-height: 48px;
  border-bottom: 1px solid color-mix(in srgb, var(--shelf-color) 26%, var(--line));
  background: var(--surface-raised);
  transition:
    background-color 160ms var(--ease),
    box-shadow 160ms var(--ease);
}

.front-level:last-child {
  border-bottom: 0;
}

.front-level.drag-over {
  background: var(--accent-soft);
  box-shadow: inset 0 0 0 1px var(--accent);
}

.level-index {
  display: flex;
  flex: 0 0 38px;
  align-items: center;
  justify-content: center;
  border-right: 1px solid var(--line);
}

.level-tab {
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 4px;
  background: var(--surface);
  color: var(--secondary);
  font-family: var(--mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.level-items {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 4px;
  min-width: 0;
  padding: 6px 8px;
  overflow-x: auto;
  scrollbar-width: thin;
}

.empty-level {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--muted);
  font-size: 10px;
  white-space: nowrap;
}

.empty-level > svg {
  stroke-width: 1.5;
}

.placed-category {
  position: relative;
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;
  height: 28px;
  max-width: 150px;
  padding: 0 5px 0 7px;
  border: 1px solid color-mix(in srgb, var(--cat-color) 40%, var(--line));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--cat-color) 10%, var(--surface-raised));
  color: var(--ink);
  cursor: grab;
  user-select: none;
}

.placed-category:active {
  cursor: grabbing;
}

.placed-category.drop-before::before {
  position: absolute;
  top: -3px;
  bottom: -3px;
  left: -3px;
  width: 2px;
  border-radius: 2px;
  background: var(--accent);
  content: '';
}

.category-color {
  flex: 0 0 auto;
  width: 3px;
  height: 15px;
  border-radius: 2px;
  background: var(--cat-color);
}

.placed-name {
  overflow: hidden;
  font-size: 10px;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-category {
  display: grid;
  flex: 0 0 18px;
  width: 18px;
  height: 18px;
  padding: 0;
  place-items: center;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  opacity: 0;
  transition:
    background-color 160ms var(--ease),
    color 160ms var(--ease),
    opacity 160ms var(--ease);
}

.placed-category:hover .remove-category,
.remove-category:focus-visible {
  opacity: 1;
}

.remove-category:hover {
  background: var(--surface-sunken);
  color: var(--ink);
}

.remove-category svg {
  stroke-width: 1.5;
}

.front-base {
  height: 5px;
  border-top: 1px solid color-mix(in srgb, var(--shelf-color) 32%, var(--line));
  background: color-mix(in srgb, var(--shelf-color) 9%, var(--surface));
}

.front-hint {
  display: flex;
  gap: 6px;
  margin: 12px 0 0;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.5;
}

.front-hint > svg {
  flex: 0 0 auto;
  margin-top: 1px;
  color: var(--secondary);
  stroke-width: 1.5;
}

@media (max-width: 1100px) {
  .inspector {
    border-top: 1px solid var(--line);
    border-left: 0;
  }
}

@media (max-width: 640px) {
  .inspector {
    padding: 18px 16px;
  }

  .settings-row {
    gap: 14px;
    padding: 12px;
  }

  .color-control {
    align-items: flex-start;
    flex-direction: column;
  }

  .swatches {
    justify-content: flex-start;
  }
}
</style>
