<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { AlertCircle, Check, Image as ImageIcon, MapPin, RotateCcw } from '@lucide/vue'
import { api, mapUrl } from './api'
import CategoryPalette from './components/CategoryPalette.vue'
import MapPreviewModal from './components/MapPreviewModal.vue'
import ShelfInspector from './components/ShelfInspector.vue'
import StoreMap from './components/StoreMap.vue'

const shelfColors = ['#4F8EF7', '#0EA5E9', '#14B8A6', '#22C55E', '#F59E0B', '#F97316', '#EF4444', '#8B5CF6']

const loading = ref(true)
const fatalError = ref('')
const storeId = ref(null)
const layout = ref(null)
const selectedShelfId = ref(null)
const saveState = ref('saved')
const saveError = ref('')
const pendingSaves = ref(0)
const mapOpen = ref(false)
const mapVersion = ref(Date.now())
const toast = ref(null)
const resetting = ref(false)

let toastTimer = null
let lastRefresh = 0

const store = computed(() => layout.value?.store || null)
const shelves = computed(() => layout.value?.shelves || [])
const categories = computed(() => layout.value?.categories || [])
const unplacedCategories = computed(() =>
  categories.value.filter((category) => !category.shelf_level_id),
)
const selectedShelf = computed(
  () => shelves.value.find((shelf) => shelf.id === selectedShelfId.value) || null,
)
const stats = computed(() => layout.value?.stats || { shelves: 0, categories: 0, placed: 0 })
const imageUrl = computed(() =>
  storeId.value ? mapUrl(storeId.value, mapVersion.value) : '',
)
const saveLabel = computed(() => {
  if (saveState.value === 'saving') return 'Сохраняем…'
  if (saveState.value === 'error') return 'Ошибка сохранения'
  return 'Все изменения сохранены'
})

function showToast(message, type = 'success') {
  toast.value = { message, type }
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = null
  }, type === 'error' ? 5200 : 3300)
}

async function refreshLayout({ selectFirst = false } = {}) {
  if (!storeId.value) return
  const token = ++lastRefresh
  const data = await api.layout(storeId.value)
  if (token !== lastRefresh) return
  layout.value = data

  const currentStillExists = data.shelves.some(
    (shelf) => shelf.id === selectedShelfId.value,
  )
  if (!currentStillExists) {
    selectedShelfId.value =
      selectFirst && data.shelves.length ? data.shelves[0].id : null
  }
}

async function boot() {
  loading.value = true
  fatalError.value = ''
  try {
    const stores = await api.stores()
    let storeRecord = stores[0]
    if (!storeRecord) {
      storeRecord = await api.createStore({
        name: 'Мой магазин',
        address: '',
        map_width: 100,
        map_height: 64,
        entrance_x: 50,
        entrance_y: 60,
        entrance_label: 'Вход',
      })
    }
    storeId.value = storeRecord.id
    await refreshLayout({ selectFirst: true })
  } catch (error) {
    fatalError.value = error.message || 'Не удалось загрузить данные'
  } finally {
    loading.value = false
  }
}

async function save(task, { refresh = false, selectFirst = false, successMessage = '' } = {}) {
  pendingSaves.value += 1
  saveState.value = 'saving'
  saveError.value = ''
  try {
    const result = await task()
    if (refresh) {
      await refreshLayout({ selectFirst })
    }
    if (successMessage) showToast(successMessage)
    return result
  } catch (error) {
    saveState.value = 'error'
    saveError.value = error.message || 'Неизвестная ошибка'
    showToast(saveError.value, 'error')
    try {
      await refreshLayout({ selectFirst })
    } catch {
      // The toast already explains the failure.
    }
    return null
  } finally {
    pendingSaves.value = Math.max(0, pendingSaves.value - 1)
    if (pendingSaves.value === 0 && saveState.value !== 'error') {
      saveState.value = 'saved'
    }
  }
}

function selectShelf(id) {
  selectedShelfId.value = id
}

async function moveShelf({ shelfId: id, x, y }) {
  const shelf = shelves.value.find((item) => item.id === id)
  if (!shelf) return
  shelf.x = x
  shelf.y = y
  const result = await save(() => api.updateShelf(id, { x, y }))
  if (!result) await refreshLayout()
}

async function addShelf() {
  if (!store.value) return
  const dimensions = findFreeSpot()
  const payload = {
    name: `Стеллаж ${shelves.value.length + 1}`,
    location_hint: '',
    color: shelfColors[shelves.value.length % shelfColors.length],
    x: dimensions.x,
    y: dimensions.y,
    width: dimensions.width,
    height: dimensions.height,
    levels_count: 4,
  }
  const created = await save(() => api.createShelf(storeId.value, payload), {
    refresh: true,
    successMessage: 'Стеллаж добавлен',
  })
  if (created) {
    selectedShelfId.value = created.id
  }
}

function findFreeSpot() {
  const mapWidth = store.value?.map_width || 100
  const mapHeight = store.value?.map_height || 64
  const width = 22
  const height = 10
  const stepX = 26
  const stepY = 13

  const overlaps = (x, y) =>
    shelves.value.some(
      (shelf) =>
        x < shelf.x + shelf.width &&
        x + width > shelf.x &&
        y < shelf.y + shelf.height &&
        y + height > shelf.y,
    )

  for (let y = 8; y <= mapHeight - height - 2; y += stepY) {
    for (let x = 8; x <= mapWidth - width - 2; x += stepX) {
      if (!overlaps(x, y)) return { x, y, width, height }
    }
  }

  const x = Math.max(4, Math.round((mapWidth - width) / 2))
  const y = Math.max(4, Math.round((mapHeight - height) / 2))
  return { x, y, width, height }
}

async function deleteShelf() {
  if (!selectedShelf.value) return
  const id = selectedShelf.value.id
  const result = await save(() => api.deleteShelf(id), {
    refresh: true,
    selectFirst: true,
    successMessage: 'Стеллаж удалён',
  })
  if (result !== null) {
    selectedShelfId.value = shelves.value[0]?.id || null
  }
}

async function saveShelfField({ field, value }) {
  if (!selectedShelf.value) return
  const shelf = selectedShelf.value
  const previous = shelf[field]
  shelf[field] = value
  const result = await save(() => api.updateShelf(shelf.id, { [field]: value }))
  if (!result) {
    shelf[field] = previous
    await refreshLayout()
  }
}

async function setLevels(count) {
  if (!selectedShelf.value) return
  await save(() => api.updateShelf(selectedShelf.value.id, { levels_count: count }), {
    refresh: true,
  })
}

async function placeCategory({ categoryId, shelfLevelId, position }) {
  await save(() => api.placeCategory(categoryId, shelfLevelId, position), {
    refresh: true,
  })
}

async function unplaceCategory(categoryId) {
  await save(() => api.placeCategory(categoryId, null, null), {
    refresh: true,
  })
}

async function createCategory(payload) {
  await save(() => api.createCategory(storeId.value, payload), {
    refresh: true,
    successMessage: `Категория «${payload.name}» добавлена`,
  })
}

async function deleteCategory(categoryId) {
  const category = categories.value.find((item) => item.id === categoryId)
  await save(() => api.deleteCategory(categoryId), {
    refresh: true,
    successMessage: category ? `Категория «${category.name}» удалена` : 'Категория удалена',
  })
}

async function resetDemo() {
  if (!store.value) return
  const confirmed = window.confirm(
    'Сбросить схему к демо-данным? Все текущие стеллажи, полки и категории будут заменены демонстрационной схемой.',
  )
  if (!confirmed) return

  resetting.value = true
  const result = await save(() => api.resetDemo(storeId.value), {
    successMessage: 'Демо-схема восстановлена',
  })
  if (result) {
    layout.value = result
    selectedShelfId.value = result.shelves[0]?.id || null
    mapVersion.value = Date.now()
  }
  resetting.value = false
}

function openMap() {
  mapVersion.value = Date.now()
  mapOpen.value = true
}

function refreshMap() {
  mapVersion.value = Date.now()
  showToast('Схема обновлена')
}

function retry() {
  boot()
}

onMounted(boot)

onBeforeUnmount(() => {
  window.clearTimeout(toastTimer)
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 32 32">
            <rect x="2" y="2" width="28" height="28" rx="7" fill="currentColor" />
            <path d="M9 10.5h14M9 16h14M9 21.5h9" stroke="#fffefa" stroke-width="1.8" stroke-linecap="round" />
            <path d="M22 21.5v3" stroke="#fffefa" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </span>
        <div class="brand-copy">
          <span class="brand-name">полка</span>
          <span class="brand-tagline">схема зала и AI-навигация</span>
        </div>
      </div>

      <div v-if="store" class="store-context">
        <MapPin :size="16" />
        <div class="store-copy">
          <strong>{{ store.name }}</strong>
          <span>{{ store.address || 'Схема торгового зала' }}</span>
        </div>
      </div>

      <div class="top-actions">
        <div class="save-status" :class="saveState" :title="saveError || saveLabel">
          <span class="status-dot"></span>
          <span>{{ saveLabel }}</span>
        </div>
        <button
          class="reset-button"
          type="button"
          :disabled="!store || resetting"
          title="Сбросить схему к демо-данным"
          @click="resetDemo"
        >
          <RotateCcw :size="14" />
          <span class="reset-label">Сбросить демо</span>
        </button>
        <button class="secondary-button map-button" type="button" :disabled="!store" @click="openMap">
          <ImageIcon :size="16" />
          Схема для покупателя
        </button>
      </div>
    </header>

    <main v-if="layout" class="workspace">
      <CategoryPalette
        :categories="unplacedCategories"
        :placed-count="stats.placed"
        :total-count="stats.categories"
        @create="createCategory"
        @delete="deleteCategory"
      />

      <StoreMap
        :store="store"
        :shelves="shelves"
        :selected-id="selectedShelfId"
        @select="selectShelf"
        @move="moveShelf"
        @add="addShelf"
      />

      <ShelfInspector
        :shelf="selectedShelf"
        @save-field="saveShelfField"
        @set-levels="setLevels"
        @place="placeCategory"
        @unplace="unplaceCategory"
        @delete-shelf="deleteShelf"
      />
    </main>

    <div v-else-if="loading" class="center-state">
      <div class="loader"></div>
      <strong>Собираем схему магазина</strong>
      <span>Загружаем стеллажи и категории</span>
    </div>

    <div v-else class="center-state error-state">
      <AlertCircle class="error-mark" :size="28" />
      <strong>Не удалось открыть конструктор</strong>
      <span>{{ fatalError }}</span>
      <button class="primary-button" type="button" @click="retry">Попробовать снова</button>
    </div>

    <MapPreviewModal
      :open="mapOpen"
      :store-name="store?.name || ''"
      :image-url="imageUrl"
      @close="mapOpen = false"
      @refresh="refreshMap"
    />

    <Transition name="toast">
      <div v-if="toast" class="toast" :class="toast.type">
        <AlertCircle v-if="toast.type === 'error'" :size="16" />
        <Check v-else :size="16" />
        <span>{{ toast.message }}</span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 640px;
  overflow: hidden;
  background: var(--paper);
}

.topbar {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 24px;
  min-height: 64px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}

.brand {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  width: 30px;
  height: 30px;
  color: var(--accent);
}

.brand-mark svg {
  display: block;
  width: 100%;
  height: 100%;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1;
}

.brand-name {
  color: var(--ink);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0;
}

.brand-tagline {
  color: var(--muted);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0.01em;
}

.store-context {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding-left: 20px;
  border-left: 1px solid var(--line);
  color: var(--muted);
}

.store-context > svg {
  flex: 0 0 auto;
  stroke-width: 1.5;
}

.store-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.store-copy strong {
  max-width: 260px;
  overflow: hidden;
  color: var(--ink);
  font-size: 12px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.store-copy span {
  overflow: hidden;
  color: var(--muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-left: auto;
}

.save-status {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--secondary);
  font-size: 11px;
  font-weight: 400;
  white-space: nowrap;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
}

.save-status.saving .status-dot {
  background: #b7791f;
  animation: blink 1.1s steps(2, end) infinite;
}

.save-status.error {
  color: var(--danger);
}

.save-status.error .status-dot {
  background: var(--danger);
}

@keyframes blink {
  50% {
    opacity: 0.35;
  }
}

.map-button {
  min-height: 36px;
}

.reset-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  font-weight: 400;
  white-space: nowrap;
  transition:
    background-color 160ms var(--ease),
    color 160ms var(--ease);
}

.reset-button svg {
  stroke-width: 1.5;
}

.reset-button:hover:not(:disabled) {
  background: var(--danger-soft);
  color: var(--danger);
}

.reset-button:disabled {
  opacity: 0.45;
  cursor: default;
}

.workspace {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(224px, 248px) minmax(0, 1fr) minmax(352px, 392px);
  min-height: 0;
}

.center-state {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 40px;
  color: var(--secondary);
  text-align: center;
}

.center-state strong {
  margin-top: 8px;
  color: var(--ink);
  font-size: 18px;
  font-weight: 500;
  letter-spacing: 0;
}

.center-state span {
  max-width: 360px;
  font-size: 12px;
  line-height: 1.5;
}

.loader {
  width: 24px;
  height: 24px;
  border: 2px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-mark {
  width: 36px;
  height: 36px;
  padding: 7px;
  border-radius: 50%;
  background: var(--danger-soft);
  color: var(--danger);
  stroke-width: 1.5;
}

.error-state .primary-button {
  margin-top: 12px;
}

.toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 80;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: min(420px, calc(100vw - 48px));
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  box-shadow: 0 8px 24px rgb(30 36 30 / 10%);
  color: var(--ink);
  font-size: 12px;
  font-weight: 400;
}

.toast > svg {
  flex: 0 0 auto;
  margin-top: 1px;
  color: var(--accent);
  stroke-width: 1.75;
}

.toast.error {
  border-color: #e2cbc6;
  background: #fffaf8;
}

.toast.error > svg {
  color: var(--danger);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 160ms var(--ease),
    transform 160ms var(--ease);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (max-width: 1280px) {
  .store-copy strong {
    max-width: 170px;
  }

  .save-status span:last-child {
    display: none;
  }
}

@media (max-width: 1100px) {
  .app-shell {
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }

  .topbar {
    flex-wrap: wrap;
    gap: 12px;
    padding: 12px 18px;
  }

  .store-context {
    order: 3;
    width: 100%;
    padding-top: 10px;
    padding-left: 0;
    border-top: 1px solid var(--line);
    border-left: 0;
  }

  .top-actions {
    margin-left: auto;
  }

  .workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .topbar {
    min-height: auto;
  }

  .brand-tagline,
  .save-status,
  .store-copy span,
  .reset-label {
    display: none;
  }

  .brand-name {
    font-size: 17px;
  }

  .map-button {
    min-height: 34px;
    padding: 7px 11px;
    font-size: 11px;
  }

  .toast {
    right: 16px;
    bottom: 16px;
  }
}
</style>
