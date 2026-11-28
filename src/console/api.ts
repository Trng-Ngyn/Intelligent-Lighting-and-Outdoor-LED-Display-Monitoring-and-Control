import axios from 'axios';
export type Asset = {
  tenant_id: string; site_id: string; asset_id: string; asset_code: string;
  kind: 'lighting' | 'led'; location_id: string | null; group_id: string; group_name: string | null;
  latitude: number | null; longitude: number | null; is_demo: boolean;
  status: 'online' | 'offline' | 'error'; reported_brightness: number | null;
  power_w: number | null; clock_quality: string | null;
  source_time: string | null; received_time: string | null;
};
export type Point = { time: string; value: number | null };
export type History = { power: Point[]; energy: Point[]; aggregation: string };
export type Command = { command_id: string; asset_id: string; brightness: number;
  state: string; reason: string | null; is_demo: boolean; verified_at: string | null };
export const api = axios.create({ baseURL: '/api/v1', timeout: 15000 });
let access = '';
let refresh = '';
let refreshing: Promise<void> | null = null;
let expiredHandler = () => {};
export function onExpired(callback: () => void) { expiredHandler = callback; }
api.interceptors.request.use(config => {
  if (access) config.headers.Authorization = 'Bearer ' + access;
  return config;
});
api.interceptors.response.use(response => response, async error => {
  const request = error.config;
  if (error.response?.status === 401 && refresh && !request._retried && !request.url?.startsWith('/auth/')) {
    request._retried = true;
    try {
      refreshing ||= axios.post('/api/v1/auth/refresh', { refresh_token: refresh }, { timeout: 15000 })
        .then(({ data }) => { access = data.access_token; refresh = data.refresh_token; })
        .finally(() => { refreshing = null; });
      await refreshing;
      return api(request);
    } catch {
      access = ''; refresh = ''; expiredHandler();
    }
  }
  return Promise.reject(error);
});
export async function login(username: string, password: string) {
  const { data } = await api.post('/auth/login', { username, password });
  access = data.access_token; refresh = data.refresh_token;
  return (await api.get('/auth/me')).data as { user_id: string; roles: string[] };
}
export async function logout() {
  try { if (refresh) await api.post('/auth/logout', { refresh_token: refresh }); }
  finally { access = ''; refresh = ''; }
}
export function errorText(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (error.response?.status === 422) return 'Thông số gửi đi chưa hợp lệ.';
    if (!error.response) return 'Không kết nối được Backend. Kiểm tra mạng hoặc máy chủ Staging.';
    return 'API trả lỗi ' + error.response.status + '.';
  }
  return 'Không hoàn tất được thao tác.';
}
