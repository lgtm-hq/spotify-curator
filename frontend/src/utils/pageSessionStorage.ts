const ADVISOR_SESSION_KEY = "spotify-curator-advisor-session";
const CURATE_SESSION_KEY = "spotify-curator-curate-session";

export function loadJsonSession<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function saveJsonSession(key: string, value: unknown): void {
  sessionStorage.setItem(key, JSON.stringify(value));
}

export function clearJsonSession(key: string): void {
  sessionStorage.removeItem(key);
}

export function loadAdvisorSession<T>(): T | null {
  return loadJsonSession<T>(ADVISOR_SESSION_KEY);
}

export function saveAdvisorSession(value: unknown): void {
  saveJsonSession(ADVISOR_SESSION_KEY, value);
}

export function clearAdvisorSession(): void {
  clearJsonSession(ADVISOR_SESSION_KEY);
}

export function loadCurateSession<T>(): T | null {
  return loadJsonSession<T>(CURATE_SESSION_KEY);
}

export function saveCurateSession(value: unknown): void {
  saveJsonSession(CURATE_SESSION_KEY, value);
}

export function clearCurateSession(): void {
  clearJsonSession(CURATE_SESSION_KEY);
}

const DISCOVER_SESSION_KEY = "spotify-curator-discover-session";

export function loadDiscoverSession<T>(): T | null {
  return loadJsonSession<T>(DISCOVER_SESSION_KEY);
}

export function saveDiscoverSession(value: unknown): void {
  saveJsonSession(DISCOVER_SESSION_KEY, value);
}

export function clearDiscoverSession(): void {
  clearJsonSession(DISCOVER_SESSION_KEY);
}
