import { useSyncExternalStore } from "react";

const state = {
  booted: false,
  appConfig: null,
  sidebar: [],
  launcher: [],
  buttons: [],
  permissions: {},
  liveData: null,
  reports: [],
  apiStatus: null,
  pinned: JSON.parse(localStorage.getItem("erp:pinned") || "[]"),
  tabs: [
    { id: "dashboard", title: "Dashboard", type: "dashboard" },
  ],
  activeTab: "dashboard",
  notifications: [],
  activity: null,
  realtimeStatus: "offline",
  commandOpen: false,
  splitView: false,
  brand: { name: "Billentra", accent: "#2563eb" },
};

const listeners = new Set();

function emit() {
  listeners.forEach((listener) => listener());
}

export function setErpState(patch) {
  const nextPatch = typeof patch === "function" ? patch(state) : patch;
  Object.assign(state, nextPatch);
  if (nextPatch.pinned) {
    localStorage.setItem("erp:pinned", JSON.stringify(nextPatch.pinned));
  }
  emit();
}

export function useErpStore(selector = (value) => value) {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => selector(state),
    () => selector(state),
  );
}

export function openWorkspaceTab(tab) {
  const exists = state.tabs.some((item) => item.id === tab.id);
  setErpState({
    tabs: exists ? state.tabs : [...state.tabs, tab],
    activeTab: tab.id,
  });
}

export function closeWorkspaceTab(id) {
  const tabs = state.tabs.filter((tab) => tab.id !== id);
  setErpState({
    tabs: tabs.length ? tabs : [{ id: "dashboard", title: "Dashboard", type: "dashboard" }],
    activeTab: state.activeTab === id ? (tabs[0]?.id || "dashboard") : state.activeTab,
  });
}

export function togglePinned(moduleKey) {
  const pinned = state.pinned.includes(moduleKey)
    ? state.pinned.filter((key) => key !== moduleKey)
    : [...state.pinned, moduleKey];
  setErpState({ pinned });
}
