import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Point } from './api';
import { withGaps } from './model';
const fmt = (time: string) => new Date(time).toLocaleString('vi-VN');
const number = (n: number | null, digits = 1) => n == null ? '—' : n.toLocaleString('vi-VN', { maximumFractionDigits: digits });

export default function Chart({ title, unit, points, interval }: { title: string; unit: string; points: Point[]; interval: number }) {
  const chart = withGaps(points, interval).map(p => ({ ...p, timestamp: Date.parse(p.time) }));
  return <section className="panel"><div className="section-title"><h3>{title}</h3><span>{unit}</span></div>
    {!points.length ? <div className="empty">Chưa có dữ liệu hợp lệ trong khoảng thời gian này.</div> :
      <div className="chart"><ResponsiveContainer width="100%" height="100%">
        <LineChart data={chart} margin={{ top: 12, right: 20, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="timestamp" type="number" domain={['dataMin', 'dataMax']}
            tickFormatter={t => new Date(t).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })} />
          <YAxis width={62} tickFormatter={v => Math.abs(Number(v)) > 0 && Math.abs(Number(v)) < .001
            ? Number(v).toExponential(1) : number(Number(v), 3)} /><Tooltip labelFormatter={t => fmt(new Date(Number(t)).toISOString())}
            formatter={v => [number(typeof v === 'number' ? v : null, unit === 'kWh' ? 6 : 2) + ' ' + unit, title]} />
          <Line type="linear" dataKey="value" stroke="#2563eb" strokeWidth={2} dot={points.length === 1} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer></div>}
  </section>;
}
