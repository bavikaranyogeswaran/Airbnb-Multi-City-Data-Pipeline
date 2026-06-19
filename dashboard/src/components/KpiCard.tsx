interface Props {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}

export default function KpiCard({ label, value, sub, accent }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-1">
      <p className="text-xs font-medium text-brand-gray uppercase tracking-wide">{label}</p>
      <p
        className="text-2xl font-bold text-brand-dark leading-tight"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-brand-gray">{sub}</p>}
    </div>
  );
}
