"use client";

type Props = {
  value: string;
  onChange: (value: string) => void;
};

export function LiveSearch({ value, onChange }: Props) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
        Search
      </span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Channel or topic — e.g. C5N, Ibai, Lofi"
        autoComplete="off"
        spellCheck={false}
        className="h-9 w-full max-w-xl border border-border bg-surface px-3 text-sm text-fg outline-none transition-colors duration-200 placeholder:text-muted/60 hover:border-accent/50 focus:border-accent"
      />
    </label>
  );
}
