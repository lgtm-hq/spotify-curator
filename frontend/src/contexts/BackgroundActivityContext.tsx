import { type ReactNode, useCallback, useMemo, useState } from "react";
import {
  type AdvisorActivity,
  BackgroundActivityContext,
  type CurateActivity,
  type DashboardActivity,
  type DiscoverActivity,
} from "./backgroundActivity";

export function BackgroundActivityProvider({ children }: { children: ReactNode }) {
  const [dashboard, setDashboard] = useState<DashboardActivity>({
    scanning: false,
    hasResults: false,
  });
  const [advisor, setAdvisor] = useState<AdvisorActivity>({
    scanning: false,
    hasResults: false,
  });
  const [curate, setCurate] = useState<CurateActivity>({
    busy: false,
    hasResults: false,
  });
  const [discover, setDiscover] = useState<DiscoverActivity>({
    busy: false,
    hasResults: false,
  });

  const setDashboardActivity = useCallback((update: Partial<DashboardActivity>) => {
    setDashboard((current) => ({ ...current, ...update }));
  }, []);

  const setAdvisorActivity = useCallback((update: Partial<AdvisorActivity>) => {
    setAdvisor((current) => ({ ...current, ...update }));
  }, []);

  const setCurateActivity = useCallback((update: Partial<CurateActivity>) => {
    setCurate((current) => ({ ...current, ...update }));
  }, []);

  const setDiscoverActivity = useCallback((update: Partial<DiscoverActivity>) => {
    setDiscover((current) => ({ ...current, ...update }));
  }, []);

  const value = useMemo(
    () => ({
      dashboard,
      advisor,
      curate,
      discover,
      setDashboardActivity,
      setAdvisorActivity,
      setCurateActivity,
      setDiscoverActivity,
    }),
    [
      dashboard,
      advisor,
      curate,
      discover,
      setDashboardActivity,
      setAdvisorActivity,
      setCurateActivity,
      setDiscoverActivity,
    ],
  );

  return (
    <BackgroundActivityContext.Provider value={value}>
      {children}
    </BackgroundActivityContext.Provider>
  );
}
