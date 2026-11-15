import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import Badge from "../assets/components/Badge";
import MapBackdrop from "../assets/components/MapBackdrop";
import { MapLegend } from "../assets/components/OperationsMap";
import PageTitle from "../assets/components/PageTitle";
import PowerChart from "../assets/components/PowerChart";
import StatCard from "../assets/components/StatCard";
import { cityData, districtData, districts, downloadCsv, formatNumber, getDevice } from "../data/operations";
import type { District } from "../data/operations";
import { useOperations } from "../state/operationsContext";

export default function Dashboard() {
  const { alarms, broadcast } = useOperations();
  const [district, setDistrict] = useState<District | "">("");
  const totals = district ? districtData[district] : cityData;
  const localAlarms = district ? alarms.filter((item) => getDevice(item.deviceId)?.area === district) : alarms;
  const urgent = localAlarms.filter((item) => item.severity === "Nghiêm trọng").length;
  const flagged = [alarms[0], alarms[1], alarms[3]].filter((item) => localAlarms.includes(item));
  const priority = (flagged.length ? flagged : localAlarms).slice(0, 3);
  const actualLights = totals.lights - totals.offline;
  const actualScreens = totals.screens - totals.screensOffline;
  const savings = 100 * (1 - totals.energy / totals.baseline);

  function exportReport() {
    downloadCsv("PCCOM_Tong_quan.csv", [
      ["Khu vực", "Đèn đang hoạt động", "Tổng số đèn", "Điện năng (kWh)", "Cảnh báo đang mở", "LED trực tuyến"],
      [district || "Toàn thành phố", actualLights, totals.lights, totals.energy, localAlarms.length, actualScreens],
    ]);
  }

  return (
    <>
      <PageTitle title="Tổng quan vận hành">
        <select aria-label="Phạm vi tổng quan" className="btn select-button" value={district} onChange={(event) => setDistrict(event.target.value as District | "")}>
          <option value="">Toàn thành phố</option>
          {districts.map((area) => <option key={area}>{area}</option>)}
        </select>
        <button className="btn" onClick={exportReport}>Xuất báo cáo</button>
      </PageTitle>
      <section className="stats-grid" aria-label="Chỉ số vận hành">
        <StatCard title="Đèn đang hoạt động" value={`${formatNumber(actualLights)} / ${formatNumber(totals.lights)}`} description={<><i className="status-dot" /> {formatNumber(actualLights / totals.lights * 100, 1)}% online · {totals.offline} mất kết nối</>} />
        <StatCard title="Điện năng hôm nay" value={`${formatNumber(totals.energy)} kWh`} description={`↓ ${formatNumber(savings, 1)}% so với đường cơ sở`} />
        <StatCard title="Cảnh báo đang mở" value={String(localAlarms.length)} description={`${urgent} nghiêm trọng · ${localAlarms.length - urgent} cần theo dõi`} />
        <StatCard title="Màn hình LED trực tuyến" value={`${actualScreens} / ${totals.screens}`} description={<><i className="status-dot" /> {formatNumber(actualScreens / totals.screens * 100, 1)}% online · {totals.screensOffline} ngoại tuyến</>} />
      </section>
      <div className="dashboard-grid">
        <section className="panel dashboard-map">
          <div className="panel-heading"><h2>Bản đồ vận hành</h2><Badge tone="green">Trực tuyến</Badge></div>
          <Link className="dashboard-map-view" to={district ? `/gis?area=${encodeURIComponent(district)}` : "/gis"} aria-label="Mở bản đồ vận hành">
            <MapBackdrop />
            <span className="map-note">{district ? `BẢN ĐỒ SƠ ĐỒ · ${district.toLocaleUpperCase("vi")}` : "BẢN ĐỒ SƠ ĐỒ · ĐÀ NẴNG"}</span>
            <span className="map-cluster cluster-left">128</span>
            <span className="map-cluster cluster-right">86</span>
            <MapLegend />
          </Link>
        </section>
        <section className="panel dashboard-power">
          <div className="panel-heading"><h2>Công suất tiêu thụ</h2><span className="chart-legend muted"><i className="status-dot" /> Thực tế (xanh dương) / Cơ sở (xanh lá)</span></div>
          <PowerChart factor={district ? totals.energy / cityData.energy : 1} />
        </section>
        <section className="panel dashboard-health">
          <h2>Sức khỏe hạ tầng</h2>
          <dl>
            <div><dt>MQTT gateway</dt><dd className="text-green">99,9%</dd></div>
            <div><dt>Tủ điều khiển</dt><dd className="text-green">248 / 250</dd></div>
            <div><dt>Độ trễ trung bình</dt><dd className="text-blue">42 ms</dd></div>
          </dl>
        </section>
        <section className="panel dashboard-alerts">
          <div className="panel-heading"><h2>Cảnh báo ưu tiên</h2><Link className="text-link" to={district ? `/alarms?area=${encodeURIComponent(district)}` : "/alarms"}>Xem tất cả <ArrowRight /></Link></div>
          <div className="table-scroll">
            <table className="priority-table" aria-label="Cảnh báo ưu tiên">
              <tbody>
                {priority.map((alarm) => (
                  <tr key={alarm.id}>
                    <td><Badge tone={alarm.severity === "Nghiêm trọng" ? "red" : "amber"}>{alarm.severity}</Badge></td>
                    <td><Link to={`/alarms?alarm=${alarm.id}`}>{alarm.title}</Link></td>
                    <td className="muted">{alarm.deviceId}</td>
                    <td className="muted">{alarm.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="panel dashboard-log">
          <h2>Nhật ký vận hành</h2>
          <ol className="timeline">
            {broadcast && <li><time>21:42</time><span>Cảnh báo khẩn cấp đã phát mô phỏng<small>{broadcast.area} · {broadcast.title}</small></span></li>}
            <li><time>21:40</time><span>Lịch tiết giảm 70% đã áp dụng<small>128 đèn · Tuyến Trần Hưng Đạo</small></span></li>
            <li><time>21:36</time><span>Đội kỹ thuật tiếp nhận WO-1042<small>Nguyễn Văn Hùng · Hải Châu</small></span></li>
            {!broadcast && <li><time>21:30</time><span>Playlist “Đà Nẵng về đêm” đang phát<small>24 màn hình · Nhóm trung tâm</small></span></li>}
          </ol>
        </section>
      </div>
    </>
  );
}
