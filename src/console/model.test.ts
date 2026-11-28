import { describe, expect, it } from 'vitest';
import { position, totalPower, withGaps, commandLabel } from './model';
import type { Asset } from './api';
const asset = (props: Partial<Asset>): Asset => ({ status: 'online', power_w: null, ...props } as Asset);
describe('live console data rules', () => {
  it('keeps missing coordinates out of the map instead of inventing a position', () => {
    expect(position(asset({ latitude: null, longitude: 108 }))).toBeNull();
    expect(position(asset({ latitude: 0, longitude: 0 }))).toEqual([0, 0]);
    expect(position(asset({ latitude: 91, longitude: 100 }))).toBeNull();
  });
  it('does not count stale power as current or show no data as zero', () => {
    expect(totalPower([asset({ status: 'offline', power_w: 100 })])).toBeNull();
    expect(totalPower([asset({ power_w: 80 }), asset({ status: 'offline', power_w: 100 })])).toBe(80);
  });
  it('breaks chart lines across missing samples and preserves actual zero', () => {
    const points = [{ time: '2026-11-27T00:00:00Z', value: 0 }, { time: '2026-11-27T00:20:00Z', value: 10 }];
    expect(withGaps(points, 300000).map(p => p.value)).toEqual([0, null, 10]);
  });
  it('does not label MQTT acceptance as physical verification', () => {
    expect(commandLabel.sent).toBe('Đã gửi MQTT');
    expect(commandLabel.executed).toContain('chờ telemetry');
    expect(commandLabel.verified).toContain('Telemetry');
  });
});
