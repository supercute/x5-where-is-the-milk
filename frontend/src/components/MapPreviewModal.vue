<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { Download, RefreshCw, X } from '@lucide/vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  storeName: { type: String, default: '' },
  imageUrl: { type: String, default: '' },
})

const emit = defineEmits(['close', 'refresh'])

function onKeydown(event) {
  if (event.key === 'Escape' && props.open) emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
        <div class="map-modal" role="dialog" aria-modal="true" aria-label="Схема магазина">
          <div class="modal-head">
            <div>
              <p class="eyebrow">Схема для покупателя</p>
              <h2>Схема магазина</h2>
              <p>
                Такую картинку Telegram-бот отправит по команде <b>/map</b>.
                {{ storeName ? `Магазин «${storeName}».` : '' }}
              </p>
            </div>
            <button class="icon-button close" type="button" @click="emit('close')">
              <X :size="16" />
            </button>
          </div>

          <div class="image-frame">
            <img :src="imageUrl" alt="Схема магазина со стеллажами и категориями товаров" />
          </div>

          <div class="modal-actions">
            <p>
              Схема собирается из текущего расположения стеллажей, полок и категорий.
              Перетаскивание блоков сразу отражается на картинке.
            </p>
            <div class="buttons">
              <button class="secondary-button" type="button" @click="emit('refresh')">
                <RefreshCw :size="14" />
                Обновить
              </button>
              <a class="primary-button" :href="imageUrl" download="store-map.png">
                <Download :size="14" />
                Скачать PNG
              </a>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  padding: 28px;
  place-items: center;
  background: rgb(20 24 20 / 56%);
}

.map-modal {
  display: flex;
  flex-direction: column;
  width: min(1120px, 100%);
  max-height: calc(100vh - 56px);
  padding: 20px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-panel);
  background: var(--surface);
  box-shadow: 0 24px 64px rgb(20 24 20 / 20%);
  overflow: hidden;
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
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

.modal-head p:last-child {
  margin: 5px 0 0;
  color: var(--secondary);
  font-size: 12px;
  line-height: 1.5;
}

.modal-head b {
  color: var(--ink);
  font-weight: 500;
}

.close {
  flex: 0 0 auto;
  border-color: var(--line);
  background: var(--surface-raised);
}

.image-frame {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-card);
  background: var(--surface-sunken);
  overflow: auto;
}

.image-frame img {
  display: block;
  width: 100%;
  height: auto;
}

.modal-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 16px;
}

.modal-actions p {
  max-width: 620px;
  margin: 0;
  color: var(--secondary);
  font-size: 11px;
  line-height: 1.5;
}

.buttons {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

.buttons svg {
  stroke-width: 1.5;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 180ms var(--ease);
}

.modal-enter-active .map-modal,
.modal-leave-active .map-modal {
  transition:
    transform 180ms var(--ease),
    opacity 180ms var(--ease);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .map-modal,
.modal-leave-to .map-modal {
  opacity: 0;
  transform: translateY(6px);
}

@media (max-width: 700px) {
  .modal-backdrop {
    padding: 12px;
  }

  .map-modal {
    max-height: calc(100vh - 24px);
    padding: 16px;
    border-radius: var(--radius-card);
  }

  .modal-actions {
    align-items: stretch;
    flex-direction: column;
    gap: 12px;
  }

  .buttons {
    justify-content: flex-end;
  }
}
</style>
