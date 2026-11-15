import { useState } from "react";
import type { CSSProperties } from "react";
import PageTitle from "../assets/components/PageTitle";
import StatCard from "../assets/components/StatCard";
import { cityData, demoDate, districtData, districts, downloadCsv, formatNumber } from "../data/operations";

const baselineWeights = [875, 900, 930, 920, 875, 778, 593, 530, 479, 455, 493, 578, 850, 1020, 1110, 1062, 1010, 989, 1035, 1000, 900, 754, 633, 531];
const actualWeights = [625, 645, 670, 660, 625, 554, 421, 377, 342, 326, 351, 413, 607, 732, 794, 757, 724, 706, 743, 716, 642, 534, 446, 378];
const dates = [{ id: demoDate, label: "13/11/2026", factor: 1 }, { id: "2026-11-12", label: "12/11/2026", factor: 1.045 }, { id: "2026-11-11", label: "11/11/2026", factor: 0.974 }];

function hourlySeries(weights: number[], total: number) {
  const sum = weights.reduce((acc, value) => acc + value, 0);
  let cumulative = 0;
  let allocated = 0;
  return weights.map((weight) => {
    cumulative += weight;
    const next = Math.round(cumulative * total / sum);
    const hour = next - allocated;
    allocated = next;
    return hour;
  });
}

export default function Energy() {
  const [date, setDate] = useState(dates[0].id);
  const selected = dates.find((entry) => entry.id === date) ?? dates[0];
  const districtsForDay = districts.map((district) => {
    const metric = districtData[district];
    const energy = Math.round(metric.energy * selected.factor);
    const savings = 100 * (1 - energy / metric.baseline);
    return { district, lights: metric.lights, energy, baseline: metric.baseline, savings };
  });
  const energy = districtsForDay.reduce((sum, row) => sum + row.energy, 0);
  const savings = cityData.baseline - energy;
  const rate = 100 * savings / cityData.baseline;
  const actualSeries = hourlySeries(actualWeights, energy);
  const baselineSeries = hourlySeries(baselineWeights, cityData.baseline);
  const chartMaximum = 1600;
  const hourLabel = (hour: number) => `${String(hour).padStart(2, "0")}:00`;

  function exportReport() {
    downloadCsv(`PCCOM_Nang_luong_${date}.csv`, [
      ["Ngày", "Khu vực", "Số đèn", "Điện năng (kWh)", "Đường cơ sở (kWh)", "Tiết kiệm (%)"],
      ...districtsForDay.map((row) => [selected.label, row.district, row.lights, row.energy, row.baseline, Number(row.savings.toFixed(1))]),
      [],
      ["Giờ", "Thực tế (kWh)", "Đường cơ sở (kWh)"],
      ...actualSeries.map((value, index) => [hourLabel(index), value, baselineSeries[index]]),
    ]);
  }

  return (
    <>
      <PageTitle title="Giám sát năng lượng">
        <select className="btn select-button" aria-label="Ngày báo cáo" value={date} onChange={(event) => setDate(event.target.value)}>{dates.map((day) => <option value={day.id} key={day.id}>{day.label}</option>)}</select>
        <button className="btn" onClick={exportReport}>Xuất báo cáo</button>
      </PageTitle>
      <section className="stats-grid" aria-label="Chỉ số năng lượng">
        <StatCard title={date === demoDate ? "Điện năng hôm nay" : "Điện năng trong ngày"} value={`${formatNumber(energy)} kWh`} description={`↓ ${formatNumber(rate, 1)}% so với đường cơ sở`} />
        <StatCard title={date === demoDate ? "Tiết kiệm hôm nay" : "Tiết kiệm trong ngày"} value={`${formatNumber(savings)} kWh`} description={`Đường cơ sở: ${formatNumber(cityData.baseline)} kWh`} />
        <StatCard title="Chi phí ước tính" value={`${formatNumber(energy * 0.002, 2)} triệu ₫`} description="Đơn giá mẫu: 2.000 ₫/kWh" />
        <StatCard title="CO₂ tránh phát thải" value={`${formatNumber(savings * 0.000659, 2)} tấn`} description="Hệ số mẫu: 0,659 kg/kWh" />
      </section>
      <div className="energy-grid">
        <section className="panel energy-chart">
          <div className="panel-heading"><h2>Điện năng theo giờ</h2><div className="energy-legend"><span className="text-blue"><i className="status-dot" /> Thực tế (kWh)</span><span className="muted"><i className="status-dot" /> Đường cơ sở</span></div></div>
          <figure className="hourly-chart" aria-label="Biểu đồ điện năng thực tế so với đường cơ sở trong 24 giờ">
            <figcaption className="muted">kWh</figcaption>
            <div className="hourly-plot">
              <div className="grid-ticks" aria-hidden="true">{[1600, 1200, 800, 400, 0].map((tick) => <div key={tick}><span>{tick}</span><i /></div>)}</div>
              <div className="bar-pairs">
                {actualSeries.map((value, index) => <div key={index} className="bar-pair" tabIndex={0} title={`${hourLabel(index)} · Thực tế ${formatNumber(value)} kWh · Cơ sở ${formatNumber(baselineSeries[index])} kWh`} aria-label={`${hourLabel(index)}, thực tế ${value} kWh, cơ sở ${baselineSeries[index]} kWh`}>
                  <i style={{ "--bar-height": `${baselineSeries[index] / chartMaximum * 100}%` } as CSSProperties} />
                  <i style={{ "--bar-height": `${value / chartMaximum * 100}%` } as CSSProperties} />
                </div>)}
              </div>
            </div>
            <div className="hour-ticks" aria-hidden="true">{[0, 4, 8, 12, 16, 20, 23].map((hour) => <span key={hour} style={{ left: `${(hour + 0.5) / 24 * 100}%` }}>{hourLabel(hour)}</span>)}</div>
          </figure>
        </section>
        <section className="panel energy-saving">
          <h2>Hiệu quả tiết kiệm</h2>
          <strong className="saving-value text-green">{formatNumber(rate, 1)}%</strong>
          <p className="muted">Mục tiêu tháng: 25% · {rate >= 25 ? "Vượt" : "Còn thiếu"} {formatNumber(Math.abs(rate - 25), 1)} điểm %</p>
          <progress className="saving-progress" max="35" value={rate} aria-label="Tỷ lệ tiết kiệm điện năng" />
          <div className="energy-month">
            <p className="eyebrow">THÁNG 11 / 2026</p>
            <div><strong>486.200 kWh</strong><strong className="text-green">↓ 26,8%</strong></div>
            <p className="muted">Điện năng lũy kế</p>
          </div>
        </section>
      </div>
      <section className="panel energy-distribution">
        <h2>Phân bổ theo khu vực</h2>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Khu vực</th><th>Số đèn</th><th>Điện năng {date === demoDate ? "hôm nay" : "trong ngày"}</th><th>Đường cơ sở</th><th>Tiết kiệm</th><th>Xu hướng</th></tr></thead>
            <tbody>{districtsForDay.map((row) => <tr key={row.district}><td>{row.district}</td><td>{formatNumber(row.lights)}</td><td>{formatNumber(row.energy)} kWh</td><td>{formatNumber(row.baseline)} kWh</td><td className="text-green">{formatNumber(row.savings, 1)}%</td><td className="text-green">↓ Ổn định</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </>
  );
}
