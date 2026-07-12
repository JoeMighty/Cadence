export default function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-foreground-secondary">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-accent" />
      {label}
    </div>
  );
}
