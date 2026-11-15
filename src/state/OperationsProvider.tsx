import { useState } from "react";
import type { ReactNode } from "react";
import { initialAlarms, initialJobs } from "../data/operations";
import { OperationsContext } from "./operationsContext";
import type { Broadcast } from "./operationsContext";

export default function OperationsProvider({ children }: { children: ReactNode }) {
  const [alarms, setAlarms] = useState(initialAlarms);
  const [jobs, setJobs] = useState(initialJobs);
  const [brightness, setBrightness] = useState<Record<string, number>>({});
  const [broadcast, setBroadcast] = useState<Broadcast | null>(null);

  return (
    <OperationsContext.Provider value={{ alarms, setAlarms, jobs, setJobs, brightness, setBrightness, broadcast, setBroadcast }}>
      {children}
    </OperationsContext.Provider>
  );
}
