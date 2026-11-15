/* Line icons on a 16 grid: the same drawings as look.py had and CodePage's builder has. */
const P = {
  plus: <path d="M8 3.2v9.6M3.2 8h9.6" />,
  folder: <path d="M1.8 4.4c0-.6.4-1 1-1h3.1l1.5 1.5h5.8c.6 0 1 .4 1 1v6.2c0 .6-.4 1-1 1H2.8c-.6 0-1-.4-1-1Z" />,
  save: <><path d="M2.6 3.6c0-.6.4-1 1-1h7l2.8 2.8v7c0 .6-.4 1-1 1H3.6c-.6 0-1-.4-1-1Z" /><path d="M5.2 2.7v2.8h4.6V2.7" /><path d="M5 13.3V9.6h6v3.7" /></>,
  spark: <path d="M8 1.8 9.4 6.6 14.2 8 9.4 9.4 8 14.2 6.6 9.4 1.8 8 6.6 6.6Z" />,
  play: <path d="M5 3.4v9.2L12.6 8Z" />,
  stop: <rect x="4" y="4" width="8" height="8" rx="1.4" />,
  export: <><path d="M8 10V2.6" /><path d="M5.2 5.3 8 2.5l2.8 2.8" /><path d="M2.6 9.6v2.8c0 .6.4 1 1 1h8.8c.6 0 1-.4 1-1V9.6" /></>,
  open: <><path d="M9.4 2.6h4v4M13.2 2.8 7.6 8.4" /><path d="M12 9.4v3c0 .6-.4 1-1 1H3.6c-.6 0-1-.4-1-1V5c0-.6.4-1 1-1h3" /></>,
  file: <><path d="M3.6 1.6h5.8l3 3v9.8H3.6Z" /><path d="M9.4 1.6v3h3" /></>,
  image: <><rect x="2" y="2.6" width="12" height="10.8" rx="1.4" /><circle cx="5.8" cy="6.2" r="1.1" /><path d="m2.4 12 3.6-3.3 2.4 2.1 2-1.7 3.2 2.8" /></>,
  chev: <path d="m4.6 6.2 3.4 3.4 3.4-3.4" />,
  chevRight: <path d="m6.2 4.6 3.4 3.4-3.4 3.4" />,
  chevLeft: <path d="M9.8 4.6 6.4 8l3.4 3.4" />,
  check: <path d="m3.6 8.3 2.8 2.8 6-6.3" />,
  close: <path d="m4.2 4.2 7.6 7.6M11.8 4.2l-7.6 7.6" />,
  search: <><circle cx="7" cy="7" r="4.4" /><path d="m10.3 10.3 3.3 3.3" /></>,
  refresh: <><path d="M13 4.6V2.4M13 4.6h-2.2" /><path d="M12.8 4.4A5.4 5.4 0 1 0 13.4 9" /></>,
  list: <><path d="M5.6 4h7.8M5.6 8h7.8M5.6 12h7.8" /><circle cx="2.8" cy="4" r=".6" /><circle cx="2.8" cy="8" r=".6" /><circle cx="2.8" cy="12" r=".6" /></>,
  wave: <path d="M1.8 8h1.4M4.6 5v6M7.4 2.8v10.4M10.2 5.6v4.8M13 7v2" />,
  music: <><path d="M6 12.2V3.4l7-1.4v8.6" /><circle cx="4.4" cy="12.2" r="1.7" /><circle cx="11.4" cy="10.6" r="1.7" /></>,
  game: <><rect x="1.8" y="4.6" width="12.4" height="7.4" rx="3.6" /><path d="M5 7.4v2M4 8.4h2" /><circle cx="10.6" cy="7.8" r=".6" /><circle cx="11.8" cy="9.2" r=".6" /></>,
  slides: <><rect x="1.8" y="2.6" width="12.4" height="8.6" rx="1.2" /><path d="M8 11.2v2.4M5.6 13.6h4.8M4.6 8.4l2.2-2.2 1.6 1.4 2.6-2.6" /></>,
  chart: <><path d="M2.4 13.6h11.2" /><rect x="3.4" y="8" width="2.2" height="4.4" rx=".5" /><rect x="6.9" y="4.6" width="2.2" height="7.8" rx=".5" /><rect x="10.4" y="6.6" width="2.2" height="5.8" rx=".5" /></>,
  cube: <><path d="m8 1.8 5.4 3.1v6.2L8 14.2l-5.4-3.1V4.9Z" /><path d="m2.6 4.9 5.4 3.1 5.4-3.1M8 8v6.2" /></>,
  flask: <><path d="M6 1.8h4M6.6 1.8v4.4L2.8 12.4c-.4.7.1 1.6.9 1.6h8.6c.8 0 1.3-.9.9-1.6L9.4 6.2V1.8" /><path d="M4.4 10h7.2" /></>,
  film: <><rect x="2" y="2.6" width="12" height="10.8" rx="1.4" /><path d="M4.8 2.6v10.8M11.2 2.6v10.8M2 5.4h2.8M2 8h2.8M2 10.6h2.8M11.2 5.4H14M11.2 8H14M11.2 10.6H14" /></>,
  tools: <path d="M9.6 2.4a3 3 0 0 0-3.4 4L2.4 10.2a1.3 1.3 0 0 0 1.8 1.8L8 8.2a3 3 0 0 0 4-3.4l-1.8 1.8-1.7-.4-.4-1.7Z" />,
  page: <><rect x="2.2" y="2.2" width="11.6" height="11.6" rx="1.4" /><path d="M2.2 6h11.6M6.4 6v7.8" /></>,
  cut: <><circle cx="4.4" cy="11.6" r="2" /><circle cx="11.6" cy="11.6" r="2" /><path d="M5.7 10 11.8 2.4M10.3 10 4.2 2.4" /></>,
  dot: <circle cx="8" cy="8" r="2.4" />,
  more: <><circle cx="3.6" cy="8" r=".9" /><circle cx="8" cy="8" r=".9" /><circle cx="12.4" cy="8" r=".9" /></>,
  code: <><path d="m5.4 4.6-3.4 3.4 3.4 3.4" /><path d="m10.6 4.6 3.4 3.4-3.4 3.4" /><path d="m9 2.8-2 10.4" /></>,
  clock: <><circle cx="8" cy="8" r="5.8" /><path d="M8 4.8V8l2.2 1.4" /></>,
  mic: <><rect x="5.8" y="1.8" width="4.4" height="7.6" rx="2.2" /><path d="M3.6 7.6a4.4 4.4 0 0 0 8.8 0M8 12v2.2" /></>,
  warn: <path d="M8 2.8 14 13H2zM8 6.6v3M8 11.4v.1" />,
  info: <path d="M8 2.4a5.6 5.6 0 1 0 0 11.2A5.6 5.6 0 0 0 8 2.4ZM8 7.4v3.6M8 5.2v.1" />,
  trash: <><path d="M3 4.4h10M6.4 4.4V3c0-.4.3-.6.6-.6h2c.3 0 .6.2.6.6v1.4" /><path d="m4.2 4.4.6 8.6c0 .4.4.7.8.7h4.8c.4 0 .8-.3.8-.7l.6-8.6" /></>,
  copy: <><path d="M5.4 5.4h8v8h-8z" /><path d="M10.6 3.3a.8.8 0 0 0-.8-.7H3.4a.8.8 0 0 0-.8.8v6.4c0 .4.3.8.7.8" /></>,
  undo: <><path d="M4.6 6.4h5.6a3 3 0 0 1 0 6H7" /><path d="M6.6 4.2 4.4 6.4l2.2 2.2" /></>,
  redo: <><path d="M11.4 6.4H5.8a3 3 0 0 0 0 6H9" /><path d="m9.4 4.2 2.2 2.2-2.2 2.2" /></>,
  sun: <><circle cx="8" cy="8" r="2.8" /><path d="M8 1.8v1.4M8 12.8v1.4M1.8 8h1.4M12.8 8h1.4M3.6 3.6l1 1M11.4 11.4l1 1M3.6 12.4l1-1M11.4 4.6l1-1" /></>,
  moon: <path d="M13 9.6A5.4 5.4 0 0 1 6.4 3a5.4 5.4 0 1 0 6.6 6.6Z" />,
  plug: <><path d="M6 2v3M10 2v3M4.4 5h7.2v2.4a3.6 3.6 0 0 1-7.2 0Z" /><path d="M8 11v3" /></>,
  layers: <><path d="m8 2.4 6 3.2-6 3.2-6-3.2Z" /><path d="m2 8.4 6 3.2 6-3.2" /></>,
  scissors: <><circle cx="4.4" cy="11.6" r="2" /><circle cx="11.6" cy="11.6" r="2" /><path d="M5.7 10 11.8 2.4M10.3 10 4.2 2.4" /></>,
  eye: <><path d="M1.6 8s2.4-4.4 6.4-4.4S14.4 8 14.4 8 12 12.4 8 12.4 1.6 8 1.6 8Z" /><circle cx="8" cy="8" r="1.8" /></>,
  grid: <><rect x="2.4" y="2.4" width="4.6" height="4.6" rx="1" /><rect x="9" y="2.4" width="4.6" height="4.6" rx="1" /><rect x="2.4" y="9" width="4.6" height="4.6" rx="1" /><rect x="9" y="9" width="4.6" height="4.6" rx="1" /></>,
  volume: <><path d="M2.6 6.2h2.2L8 3.6v8.8L4.8 9.8H2.6Z" /><path d="M10.4 6a2.8 2.8 0 0 1 0 4M12 4.4a5 5 0 0 1 0 7.2" /></>,
  pause: <path d="M5.4 3.6v8.8M10.6 3.6v8.8" />,
};
const FILLED = new Set(['play', 'dot']);

export function Icon({ name, size = 16, stroke = 1.4, className = '' }) {
  const filled = FILLED.has(name);
  return (
    <svg className={`ic ${className}`} width={size} height={size} viewBox="0 0 16 16" aria-hidden="true"
      fill={filled ? 'currentColor' : 'none'} stroke={filled ? 'none' : 'currentColor'} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round">
      {P[name] || P.dot}
    </svg>
  );
}

export const hasIcon = (name) => name in P;
