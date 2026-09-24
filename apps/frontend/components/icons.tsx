type IconProps = { className?: string };

export function ArrowUpRight({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><path d="M5 15 15 5m-8 0h8v8" /></svg>;
}

export function ArrowRight({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><path d="M3 10h14m-5-5 5 5-5 5" /></svg>;
}

export function Check({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><path d="m4 10 4 4 8-9" /></svg>;
}

export function GridIcon({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><rect x="3" y="3" width="5" height="5" rx="1"/><rect x="12" y="3" width="5" height="5" rx="1"/><rect x="3" y="12" width="5" height="5" rx="1"/><rect x="12" y="12" width="5" height="5" rx="1"/></svg>;
}

export function BuildingIcon({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><path d="M4 17V3h9v14M2 17h16M7 6h3M7 9h3M7 12h3m6 5V8h-4" /></svg>;
}

export function ChartIcon({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><path d="M3 3v14h14M6 13l3-4 3 2 4-6" /></svg>;
}

export function FileIcon({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><path d="M5 2h7l4 4v12H5zM12 2v5h4M8 11h5M8 14h5" /></svg>;
}

export function ShieldIcon({ className }: IconProps) {
  return <svg aria-hidden="true" className={className} viewBox="0 0 20 20"><path d="M10 2 17 5v5c0 4-2.8 6.8-7 8-4.2-1.2-7-4-7-8V5zM7 10l2 2 4-5" /></svg>;
}
