import { deviceTone } from "../../data/operations";
import type { Device } from "../../data/operations";
import Badge from "./Badge";
import Dialog from "./Dialog";

export default function DeviceHistory({ device, onClose }: { device: Device; onClose: () => void }) {
  return (
    <Dialog title={`Lịch sử thiết bị ${device.id}`} onClose={onClose}>
      <p className="muted">{device.address} · {device.area}</p>
      <ol className="timeline">
        <li><time>{device.time}</time><span>Trạng thái gần nhất <Badge tone={deviceTone[device.status]}>{device.status}</Badge></span></li>
        <li><time>21:00:00</time><span>Đồng bộ cấu hình vận hành.</span></li>
        <li><time>18:00:00</time><span>Bắt đầu ca trực tối.</span></li>
      </ol>
    </Dialog>
  );
}
