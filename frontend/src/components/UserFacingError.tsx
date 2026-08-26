import { userFacingError } from "../utils/userFacingError";

export function UserFacingError({
  error,
  title,
  fallback,
  onRetry,
  retryLabel = "Try again",
  compact = false,
}: {
  error: unknown;
  title?: string;
  fallback?: string;
  onRetry?: () => void;
  retryLabel?: string;
  compact?: boolean;
}) {
  const message = userFacingError(error, fallback);

  return (
    <div className={`rounded-xl border border-red-500/25 bg-red-500/5 ${compact ? "p-4" : "p-6"}`}>
      {title && <p className="mb-1 text-sm font-medium text-red-200">{title}</p>}
      <p className="text-sm text-red-300/90">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg border border-red-400/30 px-3 py-1.5 text-sm text-red-200 transition hover:bg-red-500/10"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}
