import { type ReactNode, useEffect, useState } from "react";

/** Keeps page content mounted after first visit so state and effects survive navigation. */
export function PersistentPage({
  active,
  pageKey,
  children,
}: {
  active: boolean;
  pageKey: string;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(active);

  useEffect(() => {
    if (active) {
      setMounted(true);
    }
  }, [active]);

  if (!mounted) {
    return null;
  }

  return (
    <div data-page={pageKey} hidden={!active} className={active ? undefined : "hidden"}>
      {children}
    </div>
  );
}
