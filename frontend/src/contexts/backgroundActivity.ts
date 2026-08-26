import { createContext, useContext } from "react";

export interface DashboardActivity {
  scanning: boolean;
  hasResults: boolean;
}

export interface AdvisorActivity {
  scanning: boolean;
  hasResults: boolean;
}

export interface CurateActivity {
  busy: boolean;
  hasResults: boolean;
}

export interface DiscoverActivity {
  busy: boolean;
  hasResults: boolean;
}

export interface BackgroundActivityContextValue {
  dashboard: DashboardActivity;
  advisor: AdvisorActivity;
  curate: CurateActivity;
  discover: DiscoverActivity;
  setDashboardActivity: (update: Partial<DashboardActivity>) => void;
  setAdvisorActivity: (update: Partial<AdvisorActivity>) => void;
  setCurateActivity: (update: Partial<CurateActivity>) => void;
  setDiscoverActivity: (update: Partial<DiscoverActivity>) => void;
}

export const BackgroundActivityContext = createContext<BackgroundActivityContextValue | null>(null);

export function useBackgroundActivity() {
  const context = useContext(BackgroundActivityContext);
  if (!context) {
    throw new Error("useBackgroundActivity must be used within BackgroundActivityProvider");
  }
  return context;
}
