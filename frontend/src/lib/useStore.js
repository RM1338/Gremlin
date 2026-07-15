import { useSyncExternalStore } from "react";
import { subscribe, getSnapshot } from "./store.js";

export function useStore() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
