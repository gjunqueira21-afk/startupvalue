import Link from "next/link";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link className="brand" href="/" aria-label="QuantoVale — início">
      <svg aria-hidden="true" className="brand-mark" viewBox="0 0 32 32">
        <path d="M4 24.2 10.4 16l5.1 4.8L23 8l5 4.3" />
        <path d="M4 28h24" />
      </svg>
      <span>QUANTO{compact ? "" : "VALE"}</span>
    </Link>
  );
}
