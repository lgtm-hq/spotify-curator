/** Shared selectable card with violet check badge — used for quick start & focus picks. */

export function SelectionCard({
  selected,
  disabled,
  onClick,
  title,
  description,
  role = "button",
  ariaChecked,
  ariaPressed,
  className = "",
}: {
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
  title: string;
  description: string;
  role?: "radio" | "button";
  ariaChecked?: boolean;
  ariaPressed?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role={role}
      aria-checked={ariaChecked}
      aria-pressed={ariaPressed}
      disabled={disabled}
      onClick={onClick}
      className={`relative rounded-xl border px-4 py-3 text-left transition disabled:opacity-50 ${
        selected
          ? "border-violet-400/70 bg-violet-500/15 ring-1 ring-violet-400/40"
          : "border-white/10 bg-white/[0.03] hover:border-violet-400/40 hover:bg-violet-500/5"
      } ${className}`}
    >
      {selected && (
        <span className="absolute top-3 right-3 flex h-5 w-5 items-center justify-center rounded-full bg-violet-500 text-xs text-black">
          ✓
        </span>
      )}
      <span
        className={`block pr-6 text-sm font-medium ${
          selected ? "text-violet-100" : "text-zinc-200"
        }`}
      >
        {title}
      </span>
      <span className="mt-1 block text-xs leading-relaxed text-zinc-500">{description}</span>
    </button>
  );
}
