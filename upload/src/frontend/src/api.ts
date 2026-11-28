import axios from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'

/* ------------------------------------------------------------------ types */
export type Asset = {
  tenant_id: string; site_id: string; asset_id: string; asset_code: string; device_id: string
  kind: string; circuit_id: string | null; circuit_code: string | null; location_name: string | null
  latitude: number | null; longitude: number | null
  status: 'online' | 'fault' | 'offline'
  brightness: number | null; fault_code: string | null
  last_seen: string | null; source_time: string | null; power_w: number | null; heartbeat_s: number
}
export type Sample = { bucket: string; power_kw: number | null; energy_kwh: number | null; power_assets: number; energy_assets: number }
export type User = { user_id: string; roles: string[] }
export type Scope = { tenant_id: string; site_id: string }
/** Payload command.result.v1: observed_value là object {kind, value}, không phải số. */
export type ObservedValue = { kind: string; value: unknown }
export type CommandState = {
  command_id: string; status: string
  result?: { observed_value?: ObservedValue | null; reason?: string | null } | null
  error?: string | null; updated_at?: string
}

/* ---------------------------------------------------------------- session */
// Token chỉ giữ trong bộ nhớ (không localStorage) để giảm rủi ro XSS.
let accessToken = ''
let refreshToken = ''
let onUnauthorized: (() => void) | null = null
let refreshing: Promise<void> | null = null

export function clearSession() { accessToken = ''; refreshToken = '' }
/** App đăng ký callback để quay về màn hình đăng nhập khi phiên hết hạn hẳn. */
export function setUnauthorizedHandler(fn: (() => void) | null) { onUnauthorized = fn }

const baseURL = import.meta.env.VITE_API_BASE_URL || ''
export const api = axios.create({ baseURL, timeout: 15000 })

api.interceptors.request.use(c => {
  if (accessToken) c.headers.Authorization = `Bearer ${accessToken}`
  if (import.meta.env.VITE_TENANT_ID && !c.headers.has('X-Tenant-Id')) c.headers.set('X-Tenant-Id', import.meta.env.VITE_TENANT_ID)
  if (import.meta.env.VITE_SITE_ID && !c.headers.has('X-Site-Id')) c.headers.set('X-Site-Id', import.meta.env.VITE_SITE_ID)
  return c
})

async function refreshAccessToken() {
  // Dùng axios trần để không đi qua interceptor (tránh vòng lặp 401).
  const { data } = await axios.post(`${baseURL}/api/v1/auth/refresh`, { refresh_token: refreshToken }, { timeout: 15000 })
  accessToken = data.access_token
}

// Access token backend chỉ sống 30 phút. Khi gặp 401: refresh một lần rồi gửi lại.
// An toàn cho POST dim: 401 bị từ chối ở bước xác thực, trước khi command được tạo;
// request gửi lại vẫn mang nguyên Idempotency-Key.
api.interceptors.response.use(r => r, async error => {
  const cfg = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
  const url = cfg?.url ?? ''
  const isAuthCall = url.includes('/auth/login') || url.includes('/auth/refresh')
  if (!axios.isAxiosError(error) || error.response?.status !== 401 || !cfg || isAuthCall) return Promise.reject(error)
  if (!cfg._retried && refreshToken) {
    cfg._retried = true
    try {
      refreshing ??= refreshAccessToken().finally(() => { refreshing = null })
      await refreshing
      return api(cfg)
    } catch { /* refresh thất bại → đăng xuất bên dưới */ }
  }
  clearSession()
  onUnauthorized?.()
  return Promise.reject(error)
})

/* ---------------------------------------------------------------- helpers */
export const filters = { tenant_id: import.meta.env.VITE_TENANT_ID || undefined, site_id: import.meta.env.VITE_SITE_ID || undefined }
export const assetKey = (a: Asset) => `${a.tenant_id}/${a.site_id}/${a.asset_id}`
export const groupKey = (a: Asset) => `${a.tenant_id}/${a.site_id}/${a.circuit_id || 'none'}`
export const groupLabel = (a: Asset) => `${a.circuit_code || 'Chưa gán mạch'} · Site ${a.site_id.slice(0, 8)}`
const scope = (a: Scope) => ({ 'X-Tenant-Id': a.tenant_id, 'X-Site-Id': a.site_id })

/** Idempotency-Key. crypto.randomUUID chỉ có ở secure context (HTTPS/localhost);
 *  staging chạy http://<ip> sẽ không có, nên cần fallback getRandomValues. */
export function newId(): string {
  const c = globalThis.crypto
  if (typeof c?.randomUUID === 'function') return c.randomUUID()
  const b = c.getRandomValues(new Uint8Array(16))
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const h = Array.from(b, x => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}

export function errorText(e: unknown) {
  if (axios.isAxiosError(e)) {
    const detail = e.response?.data?.detail
    return `${e.response?.status ? `HTTP ${e.response.status} · ` : ''}${typeof detail === 'string' ? detail : e.message}`
  }
  return e instanceof Error ? e.message : String(e)
}

/** Danh sách (tenant, site) duy nhất của các đèn — operations-series bắt buộc có cả hai. */
export function scopesOf(assets: Asset[]): Scope[] {
  return [...new Map(assets.map(a => [`${a.tenant_id}/${a.site_id}`, { tenant_id: a.tenant_id, site_id: a.site_id }])).values()]
}

/* -------------------------------------------------------------------- API */
export async function login(username: string, password: string) {
  const { data } = await api.post('/api/v1/auth/login', new URLSearchParams({ username, password }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  accessToken = data.access_token
  refreshToken = data.refresh_token || ''
  try { return (await api.get<User>('/api/v1/auth/me')).data } catch (e) { clearSession(); throw e }
}

const num = (v: unknown): number | null => (v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v))

export async function listAssets(signal?: AbortSignal) {
  const { data } = await api.get<{ items: Asset[] }>('/api/v1/assets', { params: filters, signal })
  // Ép kiểu số phòng khi backend trả numeric/Decimal dạng chuỗi.
  return data.items.filter(a => a.kind === 'lighting').map(a => ({
    ...a, latitude: num(a.latitude), longitude: num(a.longitude), brightness: num(a.brightness), power_w: num(a.power_w),
  }))
}

async function seriesForScope(s: Scope, hours: number, assetId: string | undefined, signal?: AbortSignal) {
  const end = new Date()
  const start = new Date(end.getTime() - hours * 3600000)
  const { data } = await api.get<{ items: Sample[] }>('/api/v1/analytics/telemetry/operations-series', {
    params: { ...s, ...(assetId ? { asset_id: assetId } : {}), start_time: start.toISOString(), end_time: end.toISOString(), bucket_s: hours <= 1 ? 60 : 300 },
    signal,
  })
  return data.items.map(i => ({ ...i, power_kw: num(i.power_kw), energy_kwh: num(i.energy_kwh) }))
}

/** Gọi từng site song song rồi cộng theo bucket (các site không chung thiết bị nên cộng là hợp lệ). */
export async function series(hours: number, scopes: Scope[], assetId: string | undefined, signal?: AbortSignal): Promise<Sample[]> {
  const parts = await Promise.all(scopes.map(s => seriesForScope(s, hours, assetId, signal)))
  const merged = new Map<number, Sample>()
  const add = (a: number | null, b: number | null) => (a == null ? b : b == null ? a : a + b)
  for (const item of parts.flat()) {
    const t = Date.parse(item.bucket)
    const cur = merged.get(t)
    merged.set(t, cur ? {
      bucket: cur.bucket, power_kw: add(cur.power_kw, item.power_kw), energy_kwh: add(cur.energy_kwh, item.energy_kwh),
      power_assets: cur.power_assets + item.power_assets, energy_assets: cur.energy_assets + item.energy_assets,
    } : item)
  }
  return [...merged.entries()].sort((x, y) => x[0] - y[0]).map(([, v]) => v)
}

export async function sendDim(a: Asset, brightness: number) {
  const body = import.meta.env.VITE_DIM_FIELD === 'brightness_pct'
    ? { asset_id: a.asset_id, brightness_pct: brightness, priority: 'operator', expires_in_seconds: 60 }
    : { asset_id: a.asset_id, brightness, policy_version: 'v1.0' }
  const res = await api.post('/api/v1/controls/lighting/dim', body, { headers: { ...scope(a), 'Idempotency-Key': newId() } })
  if (res.status !== 202) throw new Error(`Phản hồi không đúng hợp đồng: HTTP ${res.status}`)
  return res.data as { command_id?: string; status?: string; duplicate?: boolean }
}

export async function commandState(a: Asset, id: string, signal?: AbortSignal) {
  const { data } = await api.get<CommandState>(`/api/v1/controls/lighting/commands/${encodeURIComponent(id)}`, { headers: scope(a), signal })
  if (data.command_id !== id) throw new Error('Command ID trả về không khớp')
  return data
}
