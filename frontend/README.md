# RentA-Fleet PRO — Frontend

Vue 3 (`<script setup>`) + Pinia single-page app. See the
[repo root README](../README.md) for the full project overview and backend
setup.

## Project setup

```sh
npm install
```

### Dev server (proxies `/api` to `http://127.0.0.1:8000`)

```sh
npm run dev
```

### Production build

```sh
npm run build
```

### Tests (Vitest)

```sh
npm run test        # single run
npm run test:watch  # watch mode
```

### Lint / format

```sh
npm run lint    # eslint
npm run format  # prettier --write src
```

## Structure

```
src/stores/       Pinia stores — one per domain concern (vehicle, vehicleMarket,
                   vehicleLiveTracking, vehicleMaintenance, rental, driver, ...)
src/components/   Reusable UI + feature components
src/views/        Top-level screens switched by stores/uiStore.js's hash router
src/composables/  Shared reactive logic (useModalLifecycle, useClickOutside, ...)
src/utils/        Pure helpers (formatting, icon paths, storage keys, ...)
```

Non-landing views/modals are lazy-loaded via `defineAsyncComponent` in
`views/Workspace.vue` and `App.vue` to keep the initial bundle small — see
that file before adding a new top-level view.

## Recommended IDE setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar).
