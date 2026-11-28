import type { Asset, Point } from './api';
export const statusLabel = { online: 'Online', error: 'Có lỗi', offline: 'Mất kết nối' };
export const statusColor = { online: '#10b981', error: '#ef4444', offline: '#64748b' };
export const commandLabel: Record<string, string> = {
  queued: 'Đã xếp hàng', sent: 'Đã gửi MQTT', acknowledged: 'Thiết bị đã nhận',
  executed: 'Thiết bị báo thực thi · chờ telemetry', verified: 'Telemetry đã xác nhận',
  expired: 'Hết hạn · chưa xác nhận', rejected: 'Thiết bị từ chối', failed: 'Thực thi thất bại',
};
export function position(asset: Asset): [number, number] | null {
  return asset.latitude != null && asset.longitude != null &&
    Number.isFinite(asset.latitude) && Number.isFinite(asset.longitude) &&
    Math.abs(asset.latitude) <= 90 && Math.abs(asset.longitude) <= 180
    ? [asset.latitude, asset.longitude] : null;
}
export function withGaps(points: Point[], intervalMs: number): Point[] {
  return points.flatMap((point, index) => {
    const previous = points[index - 1];
    return previous && Date.parse(point.time) - Date.parse(previous.time) > intervalMs * 1.5
      ? [{ time: new Date(Date.parse(previous.time) + intervalMs).toISOString(), value: null }, point]
      : [point];
  });
}
export function totalPower(assets: Asset[]) {
  const fresh = assets.filter(a => a.status !== 'offline' && a.power_w != null);
  return fresh.length ? fresh.reduce((sum, a) => sum + a.power_w!, 0) : null;
}
