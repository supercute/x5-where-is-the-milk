<script setup>
import { computed, reactive, ref } from 'vue'
import { GripVertical, Info, Package, Plus, Search, Trash2, X } from '@lucide/vue'

const props = defineProps({
  categories: { type: Array, default: () => [] },
  placedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
})

const emit = defineEmits(['create', 'delete'])

const search = ref('')
const formOpen = ref(false)
const error = ref('')
const form = reactive({
  name: '',
  aliases: '',
  color: '#F59E0B',
})

const colors = [
  '#F59E0B',
  '#F97316',
  '#EF4444',
  '#EC4899',
  '#8B5CF6',
  '#4F8EF7',
  '#0EA5E9',
  '#14B8A6',
  '#22C55E',
  '#84CC16',
]

const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return props.categories
  return props.categories.filter((category) =>
    [category.name, ...(category.aliases || [])].some((value) =>
      value.toLowerCase().includes(query),
    ),
  )
})

function openForm() {
  formOpen.value = true
  error.value = ''
  form.name = ''
  form.aliases = ''
  form.color = colors[Math.floor(Math.random() * colors.length)]
}

function closeForm() {
  formOpen.value = false
  error.value = ''
}

function submit() {
  const name = form.name.trim()
  if (!name) {
    error.value = 'Введите название категории'
    return
  }
  emit('create', {
    name,
    aliases: form.aliases
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
    color: form.color,
  })
  closeForm()
  search.value = ''
}

function startDrag(event, category) {
  const payload = {
    categoryId: category.id,
    fromLevelId: null,
    fromPosition: null,
  }
  event.dataTransfer.setData('application/x-shelf-category', JSON.stringify(payload))
  event.dataTransfer.setData('text/plain', category.name)
  event.dataTransfer.effectAllowed = 'move'
}

function removeCategory(category) {
  if (window.confirm(`Удалить категорию «${category.name}» из справочника?`)) {
    emit('delete', category.id)
  }
}
</script>

<template>
  <aside class="palette">
    <div class="panel-heading">
      <div>
        <p class="eyebrow">Справочник</p>
        <h2>Категории</h2>
      </div>
      <span class="counter">{{ placedCount }} из {{ totalCount }}</span>
    </div>

    <p class="panel-note">
      Перетащите блок на полку. Покупатель увидит категорию только в ответе агента.
    </p>

    <label class="search">
      <Search :size="16" />
      <input v-model="search" type="search" placeholder="Найти категорию" />
    </label>

    <div class="unplaced-label">
      <span>Не на полках</span>
      <span class="section-count">{{ filtered.length }}</span>
    </div>

    <div class="palette-list">
      <div
        v-for="category in filtered"
        :key="category.id"
        class="category-card"
        draggable="true"
        :style="{ '--cat-color': category.color }"
        @dragstart="startDrag($event, category)"
      >
        <GripVertical class="drag-grip" :size="14" aria-hidden="true" />
        <span class="color-bar"></span>
        <span class="category-name">{{ category.name }}</span>
        <button
          class="icon-button delete-category"
          type="button"
          title="Удалить категорию"
          @click.stop="removeCategory(category)"
        >
          <Trash2 :size="14" />
        </button>
      </div>

      <div v-if="!filtered.length && !categories.length" class="empty-palette">
        <Package :size="20" />
        <span>Все категории уже на полках</span>
        <small>Или добавьте новую категорию</small>
      </div>
      <div v-else-if="!filtered.length" class="empty-palette">
        <Search :size="20" />
        <span>Ничего не найдено</span>
        <small>Попробуйте другое название</small>
      </div>
    </div>

    <button v-if="!formOpen" class="add-category-button" type="button" @click="openForm">
      <Plus :size="14" />
      Новая категория
    </button>

    <form v-else class="category-form" @submit.prevent="submit">
      <div class="form-title">
        <strong>Новая категория</strong>
        <button class="icon-button" type="button" @click="closeForm">
          <X :size="14" />
        </button>
      </div>
      <label>
        Название
        <input v-model="form.name" autofocus placeholder="Например, Молоко" />
      </label>
      <label>
        Синонимы <span>через запятую</span>
        <input v-model="form.aliases" placeholder="молочка, молочные продукты" />
      </label>
      <div class="color-field">
        <span>Цвет</span>
        <div class="color-picker">
          <button
            v-for="color in colors"
            :key="color"
            type="button"
            class="color-swatch"
            :class="{ active: form.color === color }"
            :style="{ background: color }"
            :aria-label="`Выбрать цвет ${color}`"
            @click="form.color = color"
          ></button>
        </div>
      </div>
      <p v-if="error" class="form-error">{{ error }}</p>
      <button class="primary-button full" type="submit">Добавить категорию</button>
    </form>

    <div class="tip-card">
      <Info :size="14" />
      <p>Порядок блоков слева направо подсказывает агенту, где именно на полке стоит товар.</p>
    </div>
  </aside>
</template>

<style scoped>
.palette {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 20px 16px;
  border-right: 1px solid var(--line);
  background: var(--surface);
  overflow-y: auto;
}

.panel-heading {
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
  font-size: 20px;
  font-weight: 500;
  letter-spacing: 0;
}

.counter {
  padding-top: 2px;
  color: var(--muted);
  font-family: var(--mono);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.panel-note {
  margin: 10px 0 16px;
  color: var(--secondary);
  font-size: 12px;
  line-height: 1.5;
}

.search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  transition:
    border-color 160ms var(--ease),
    box-shadow 160ms var(--ease);
}

.search:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.search > svg {
  flex: 0 0 auto;
  color: var(--muted);
  stroke-width: 1.5;
}

.search input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: 12px;
}

.search input::placeholder {
  color: var(--muted);
}

.unplaced-label {
  display: flex;
  justify-content: space-between;
  margin: 20px 2px 6px;
  color: var(--secondary);
  font-size: 11px;
  font-weight: 500;
}

.section-count {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.palette-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-card {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  height: 38px;
  padding: 0 6px 0 4px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  cursor: grab;
  transition:
    background-color 160ms var(--ease),
    border-color 160ms var(--ease);
}

.category-card:hover {
  border-color: var(--line);
  background: var(--surface-raised);
}

.category-card:active {
  cursor: grabbing;
}

.drag-grip {
  flex: 0 0 auto;
  color: var(--line-strong);
  stroke-width: 1.5;
}

.color-bar {
  flex: 0 0 auto;
  width: 3px;
  height: 18px;
  border-radius: 2px;
  background: var(--cat-color);
}

.category-name {
  min-width: 0;
  overflow: hidden;
  color: var(--ink);
  font-size: 12px;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-category {
  width: 24px;
  height: 24px;
  margin-left: auto;
  color: var(--muted);
  opacity: 0;
}

.category-card:hover .delete-category,
.delete-category:focus-visible {
  opacity: 1;
}

.delete-category:hover {
  border-color: #e2cbc6;
  background: var(--danger-soft);
  color: var(--danger);
}

.empty-palette {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 24px 10px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius-control);
  color: var(--secondary);
  font-size: 12px;
  text-align: center;
}

.empty-palette > svg {
  margin-bottom: 4px;
  color: var(--muted);
  stroke-width: 1.5;
}

.empty-palette small {
  color: var(--muted);
  font-size: 11px;
}

.add-category-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  min-height: 36px;
  margin-top: 12px;
  padding: 7px 10px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--secondary);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  transition:
    background-color 160ms var(--ease),
    border-color 160ms var(--ease),
    color 160ms var(--ease);
}

.add-category-button:hover {
  border-color: var(--accent);
  background: var(--surface-raised);
  color: var(--ink);
}

.add-category-button svg {
  stroke-width: 1.5;
}

.category-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  background: var(--surface-raised);
}

.form-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--ink);
  font-size: 12px;
  font-weight: 500;
}

.category-form label,
.color-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--secondary);
  font-size: 11px;
  font-weight: 500;
}

.category-form label span {
  color: var(--muted);
  font-weight: 400;
}

.category-form input {
  width: 100%;
  height: 32px;
  padding: 0 9px;
  border: 1px solid var(--line);
  border-radius: 6px;
  outline: 0;
  background: #fff;
  color: var(--ink);
  font: inherit;
  font-size: 12px;
}

.category-form input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.color-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.color-swatch {
  width: 18px;
  height: 18px;
  padding: 0;
  border: 2px solid var(--surface-raised);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 0 0 1px var(--line);
}

.color-swatch.active {
  box-shadow: 0 0 0 2px var(--ink);
}

.form-error {
  margin: 0;
  color: var(--danger);
  font-size: 11px;
}

.tip-card {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding: 12px 0 0;
  border-top: 1px solid var(--line);
  color: var(--secondary);
  font-size: 11px;
  line-height: 1.5;
}

.tip-card > svg {
  flex: 0 0 auto;
  margin-top: 1px;
  color: var(--muted);
  stroke-width: 1.5;
}

.tip-card p {
  margin: 0;
}

@media (max-width: 1100px) {
  .palette {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .palette-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 2px 12px;
  }
}
</style>
