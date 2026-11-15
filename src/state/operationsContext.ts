import { createContext, useContext } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { Alarm, District, Job } from "../data/operations";

export type Broadcast = { title: string; body: string; area: District; expires: string };

export type OperationsState = {
  alarms: Alarm[];
  setAlarms: Dispatch<SetStateAction<Alarm[]>>;
  jobs: Job[];
  setJobs: Dispatch<SetStateAction<Job[]>>;
  brightness: Record<string, number>;
  setBrightness: Dispatch<SetStateAction<Record<string, number>>>;
  broadcast: Broadcast | null;
  setBroadcast: Dispatch<SetStateAction<Broadcast | null>>;
};

export const OperationsContext = createContext<OperationsState | null>(null);

export function useOperations() {
  const state = useContext(OperationsContext);
  if (!state) throw new Error("OperationsProvider is required.");
  return state;
}
