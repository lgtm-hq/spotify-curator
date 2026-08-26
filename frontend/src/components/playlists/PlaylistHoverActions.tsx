import type { ReactNode } from "react";

function IconButton({
  label,
  tone,
  disabled,
  onClick,
  children,
}: {
  label: string;
  tone: "neutral" | "danger";
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const toneClass =
    tone === "danger"
      ? "border-red-500/30 text-red-200 hover:bg-red-500/15"
      : "border-white/15 text-zinc-200 hover:bg-white/10";

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      className={`rounded-lg border bg-black/70 p-1.5 backdrop-blur transition disabled:opacity-50 ${toneClass}`}
    >
      {children}
    </button>
  );
}

export function EditPlaylistIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor" aria-hidden>
      <path d="M13.586 3.586a2 2 0 0 1 2.828 2.828l-8.25 8.25a1 1 0 0 1-.464.263l-3.5 1a1 1 0 0 1-1.213-1.213l1-3.5a1 1 0 0 1 .263-.464l8.25-8.25Z" />
      <path d="M11.379 5.793 14.207 8.62l1.414-1.414-2.828-2.828-1.414 1.414Z" />
    </svg>
  );
}

export function DeletePlaylistIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M8.75 2A1.75 1.75 0 0 0 7 3.75v.25H4.25a.75.75 0 0 0 0 1.5h11.5a.75.75 0 0 0 0-1.5H13v-.25A1.75 1.75 0 0 0 11.25 2h-2.5ZM5.5 7.5v7.75A2.25 2.25 0 0 0 7.75 17.5h4.5A2.25 2.25 0 0 0 14.5 15.25V7.5h-9Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function PlaylistHoverActions({
  disabled,
  onEdit,
  onDelete,
  compact = false,
}: {
  disabled?: boolean;
  onEdit: () => void;
  onDelete: () => void;
  compact?: boolean;
}) {
  return (
    <div
      className={`flex gap-1 ${compact ? "" : "shadow-lg"}`}
      onClick={(event) => event.stopPropagation()}
    >
      <IconButton label="Edit playlist" tone="neutral" disabled={disabled} onClick={onEdit}>
        <EditPlaylistIcon />
      </IconButton>
      <IconButton label="Remove playlist" tone="danger" disabled={disabled} onClick={onDelete}>
        <DeletePlaylistIcon />
      </IconButton>
    </div>
  );
}
