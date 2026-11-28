import { lazy, Suspense, useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorText, login, logout, onExpired, type Asset, type Command, type History } from './api';
const AssetMap = lazy(() => import('./AssetMap'));
const Chart = lazy(() => import('./Chart'));
import { commandLabel, position, statusLabel, totalPower } from './model';
const fmt = (time: string | null) => time ? new Date(time).toLocaleString('vi-VN') : 'Chưa có';
const number = (n: number | null, digits = 1) => n == null ? '—' : n.toLocaleString('vi-VN', { maximumFractionDigits: digits });

function Login({ done }: { done: (roles: string[]) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const mutation = useMutation({ mutationFn: () => login(username, password), onSuccess: user => { setPassword(''); done(user.roles); } });
  function submit(event: FormEvent) { event.preventDefault(); mutation.mutate(); }
  return <main className="login"><form onSubmit={submit}>
    <span className="brand">PCCOM <b>OPERATIONS</b></span><h1>Đăng nhập Staging</h1>
    <p>Điều hành chiếu sáng & màn hình LED ngoài trời</p>
    <label>Tài khoản<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label>
    <label>Mật khẩu<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
    {mutation.isError && <p role="alert" className="error">{errorText(mutation.error)}</p>}
    <button disabled={mutation.isPending}>{mutation.isPending ? 'Đang xác thực…' : 'Đăng nhập'}</button>
    <small>Sử dụng tài khoản do Tech Lead cấp. Phiên đăng nhập chỉ được giữ trong bộ nhớ của trang.</small>
  </form></main>;
}


function Dashboard({ roles, leave }: { roles: string[]; leave: () => void }) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState('');
  const [group, setGroup] = useState('all');
  const [mode, setMode] = useState<'device' | 'group'>('device');
  const [brightness, setBrightness] = useState(50);
  const [hours, setHours] = useState(24);
  const [batch, setBatch] = useState('');
  const editable = roles.includes('ADMIN') || roles.includes('OPERATOR');
  const query = useQuery({
    queryKey: ['assets'], queryFn: async () => (await api.get<{ assets: Asset[]; server_time: string }>('/console/assets')).data,
    refetchInterval: 3000,
  });
  const assets = query.data?.assets || [];
  const groups = [...new Map(assets.map(a => [a.group_id, a.group_name || 'Chưa phân nhóm'])).entries()];
  const visible = assets.filter(a => group === 'all' || a.group_id === group);
  const asset = assets.find(a => a.asset_id === selected);
  useEffect(() => { if (!selected && assets.length) setSelected(assets[0].asset_id); }, [assets, selected]);
  const history = useQuery({
    queryKey: ['history', selected, hours], enabled: !!selected,
    queryFn: async () => (await api.get<History>('/console/assets/' + selected + '/history', { params: { hours } })).data,
    refetchInterval: 15000,
  });
  const commands = useQuery({
    queryKey: ['commands', batch], enabled: !!batch,
    queryFn: async () => (await api.get<{ commands: Command[] }>('/console/commands/' + batch)).data.commands,
    refetchInterval: q => q.state.data?.every(c => ['verified', 'rejected', 'expired', 'failed'].includes(c.state)) ? false : 1500,
  });
  const targets = mode === 'group' ? visible.filter(a => a.kind === 'lighting') : asset?.kind === 'lighting' ? [asset] : [];
  const dimming = useMutation({
    mutationFn: async () => (await api.post('/console/dimming', { asset_ids: targets.map(a => a.asset_id), brightness },
      { headers: { 'Idempotency-Key': crypto.randomUUID() } })).data,
    onSuccess: data => { setBatch(data.batch_id); cache.invalidateQueries({ queryKey: ['assets'] }); },
  });
  async function signout() { await logout().catch(() => {}); cache.clear(); leave(); }
  const power = totalPower(assets);
  return <div className="shell">
    <header><div className="brand">PCCOM <b>OPERATIONS</b></div><div className="header-right">
      <span className={'connection ' + (query.isError ? 'bad' : query.data ? 'good' : '')}>
        {query.isError ? 'Gián đoạn API' : query.data ? 'API đã kết nối' : 'Đang kết nối'}
      </span><button className="secondary" onClick={signout}>Đăng xuất</button>
    </div></header>
    <main>
      <div className="page-title"><div><span className="eyebrow">WEB OPERATIONS CONSOLE</span><h1>Điều hành hệ thống</h1>
        <p>Vị trí, trạng thái và năng lượng từ TimescaleDB qua Backend API.</p></div>
        <div className="sync">Cập nhật gần nhất<br /><strong>{query.dataUpdatedAt ? fmt(new Date(query.dataUpdatedAt).toISOString()) : 'Đang chờ…'}</strong></div>
      </div>
      {query.isError && <div role="alert" className="banner error">{errorText(query.error)} Dữ liệu đang hiển thị có thể đã cũ.
        <button onClick={() => query.refetch()}>Thử lại</button></div>}
      {assets.some(a => a.is_demo) && <div className="banner">Có thiết bị đánh dấu DEMO. Kết quả của thiết bị này dùng kiểm thử phần mềm, không phải bằng chứng phần cứng.</div>}
      <div className="stats">
        <div><span>Thiết bị đăng ký</span><strong>{query.data ? assets.length : '—'}</strong></div>
        <div><span>Đang online</span><strong className="green">{query.data ? assets.filter(a => a.status === 'online').length : '—'}</strong></div>
        <div><span>Cần kiểm tra</span><strong>{query.data ? assets.filter(a => a.status !== 'online').length : '—'}</strong></div>
        <div><span>Tổng công suất có báo cáo</span><strong>{number(power)} <small>W</small></strong></div>
      </div>
      <div className="workspace">
        <section className="panel map-panel"><div className="section-title"><h2>Bản đồ GIS</h2>
          <select aria-label="Lọc nhóm" value={group} onChange={e => setGroup(e.target.value)}>
            <option value="all">Tất cả nhóm</option>{groups.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select></div>
          <div className="legend"><span className="online">● Online</span><span className="error-status">● Có lỗi</span><span>● Mất kết nối</span></div>
          {query.isPending ? <div className="empty">Đang tải thiết bị…</div> : <Suspense fallback={<div className="empty">Đang tải bản đồ…</div>}><AssetMap assets={visible} select={setSelected} /></Suspense>}
          <div className="table-wrap"><table><thead><tr><th>Thiết bị</th><th>Trạng thái</th><th>Độ sáng báo về</th><th>Công suất</th></tr></thead>
            <tbody>{visible.map(a => <tr key={a.asset_id} className={selected === a.asset_id ? 'selected' : ''}>
              <td><button className="link" onClick={() => setSelected(a.asset_id)}>{a.asset_code}</button>
                {a.is_demo && <small className="tag">DEMO</small>}{!position(a) && <small> · Chưa có tọa độ</small>}</td>
              <td><span className={'status ' + a.status}>{statusLabel[a.status]}</span></td>
              <td>{number(a.reported_brightness, 0)}{a.reported_brightness != null && '%'}</td><td>{number(a.power_w)} W</td>
            </tr>)}</tbody></table>{!visible.length && !query.isPending && <p className="empty">Chưa có thiết bị trong nhóm hoặc phạm vi tài khoản.</p>}</div>
        </section>
        <aside className="panel control"><span className="eyebrow">ĐIỀU KHIỂN DIMMING</span><h2>{asset?.asset_code || 'Chọn thiết bị'}</h2>
          <p>Độ sáng thiết bị báo về</p><div className="reported">{number(asset?.reported_brightness ?? null, 0)}<small>%</small></div>
          <p className="muted">Telemetry: {fmt(asset?.source_time || null)}<br />Đồng hồ: {asset?.clock_quality || 'Chưa có dữ liệu'}</p>
          <label>Phạm vi gửi lệnh<select value={mode} onChange={e => setMode(e.target.value as 'device' | 'group')}>
            <option value="device">Cột đèn đang chọn</option><option value="group">Các cột đèn trong nhóm đang lọc</option></select></label>
          <label htmlFor="dimming">Độ sáng yêu cầu <strong>{brightness}%</strong></label>
          <input id="dimming" type="range" min="0" max="100" value={brightness} onChange={e => setBrightness(Number(e.target.value))} disabled={!editable} />
          <div className="range-label"><span>0%</span><span>100%</span></div>
          <p>Gửi tới {targets.length} cột đèn. Độ sáng báo về chỉ thay đổi khi có telemetry mới.</p>
          <button className="full" disabled={!editable || !targets.length || dimming.isPending || query.isError} onClick={() => dimming.mutate()}>
            {dimming.isPending ? 'Đang gửi yêu cầu…' : 'Gửi lệnh dimming'}</button>
          {!editable && <p className="muted">Tài khoản này chỉ có quyền xem.</p>}
          {dimming.isError && <p role="alert" className="error">{errorText(dimming.error)}</p>}
          {commands.isError && <p role="alert" className="error">{errorText(commands.error)}</p>}
          {commands.data && <div className="command-log" aria-live="polite"><h3>Theo dõi lệnh</h3>
            {commands.data.map(c => <p key={c.command_id}><strong>{assets.find(a => a.asset_id === c.asset_id)?.asset_code}</strong>
              <br />{commandLabel[c.state] || c.state}{c.is_demo && ' · DEMO'}
              {c.reason && <small>{c.reason}</small>}</p>)}
            <small>Telemetry xác nhận nghĩa là thiết bị báo đúng giá trị yêu cầu. Đo đạc điện/quang học tại hiện trường vẫn cần cho nghiệm thu phần cứng.</small>
          </div>}
        </aside>
      </div>
      <div className="section-title history-title"><h2>Phụ tải & điện năng · {asset?.asset_code || 'Chưa chọn thiết bị'}</h2>
        <select aria-label="Khoảng thời gian" value={hours} onChange={e => setHours(Number(e.target.value))}>
          <option value={6}>6 giờ</option><option value={24}>24 giờ</option><option value={168}>7 ngày</option></select></div>
      {history.isError && <p role="alert" className="error">{errorText(history.error)}</p>}
      {history.isPending && selected && <p>Đang tải lịch sử…</p>}
      <div className="charts"><Suspense fallback={<p>Đang tải biểu đồ…</p>}><Chart title="Công suất trung bình 5 phút" unit="W" points={history.data?.power || []} interval={300000} />
        <Chart title="Điện năng theo giờ" unit="kWh" points={history.data?.energy || []} interval={3600000} /></Suspense></div>
      <p className="muted">Điện năng lấy từ Continuous Aggregates, cập nhật theo lịch 15 phút cho giờ đã đóng. Khoảng thiếu dữ liệu được để trống.</p>
      <footer>PCCOM · Staging Operations · Dữ liệu API thực tế · {roles.join(', ')}</footer>
    </main>
  </div>;
}
export default function Console() {
  const [roles, setRoles] = useState<string[] | null>(null);
  const cache = useQueryClient();
  useEffect(() => { onExpired(() => { cache.clear(); setRoles(null); }); }, [cache]);
  return roles ? <Dashboard roles={roles} leave={() => setRoles(null)} /> : <Login done={setRoles} />;
}
