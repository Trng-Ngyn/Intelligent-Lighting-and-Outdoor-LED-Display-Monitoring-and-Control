export const districts = ["Hải Châu", "Sơn Trà", "Thanh Khê", "Ngũ Hành Sơn"] as const;
export type District = (typeof districts)[number];

export const districtData = {
  "Hải Châu": { lights: 4820, offline: 71, energy: 7120, baseline: 9800, screens: 24, screensOffline: 1 },
  "Sơn Trà": { lights: 3260, offline: 45, energy: 4604, baseline: 6500, screens: 22, screensOffline: 1 },
  "Thanh Khê": { lights: 2840, offline: 40, energy: 4140, baseline: 5800, screens: 20, screensOffline: 1 },
  "Ngũ Hành Sơn": { lights: 1720, offline: 26, energy: 2562, baseline: 3635, screens: 24, screensOffline: 1 },
};

export const cityData = { lights: 12640, offline: 182, energy: 18426, baseline: 25735, screens: 90, screensOffline: 4 };
export const demoDate = "2026-11-13";
export const clockTime = "21:42:08";

export const deviceTypes = { light: "Đèn đường", cabinet: "Tủ điều khiển", led: "Màn hình LED" } as const;
export type DeviceType = keyof typeof deviceTypes;
export type DeviceStatus = "Hoạt động" | "Cảnh báo" | "Mất kết nối" | "Ngoại tuyến";

export type Device = {
  id: string;
  type: DeviceType;
  area: District;
  status: DeviceStatus;
  address: string;
  coordinates: [number, number];
  schematic: [number, number];
  time: string;
  lights?: number;
};

export const devices: Device[] = [
  { id: "TĐK-HC-023", type: "cabinet", area: "Hải Châu", status: "Mất kết nối", address: "128 Bạch Đằng", coordinates: [16.0678, 108.2240], schematic: [46.5, 34.2], time: "21:38:12", lights: 48 },
  { id: "TĐK-ST-008", type: "cabinet", area: "Sơn Trà", status: "Cảnh báo", address: "145 Ngô Quyền", coordinates: [16.0712, 108.2401], schematic: [83.3, 17.3], time: "21:35:46", lights: 36 },
  { id: "TĐK-HC-041", type: "cabinet", area: "Hải Châu", status: "Cảnh báo", address: "77 Trần Phú", coordinates: [16.0734, 108.2230], schematic: [35.4, 45.5], time: "21:33:08", lights: 26 },
  { id: "TĐK-TK-012", type: "cabinet", area: "Thanh Khê", status: "Cảnh báo", address: "190 Điện Biên Phủ", coordinates: [16.0672, 108.1983], schematic: [16.4, 31.9], time: "21:31:20", lights: 32 },
  { id: "L-HC-01892", type: "light", area: "Hải Châu", status: "Ngoại tuyến", address: "54 Nguyễn Văn Linh", coordinates: [16.0597, 108.2167], schematic: [31.8, 59.4], time: "21:27:42" },
  { id: "TĐK-ST-016", type: "cabinet", area: "Sơn Trà", status: "Cảnh báo", address: "122 Võ Nguyên Giáp", coordinates: [16.0672, 108.2471], schematic: [90.4, 44.8], time: "21:22:15", lights: 40 },
  { id: "LED-HC-009", type: "led", area: "Hải Châu", status: "Ngoại tuyến", address: "36 Trần Phú", coordinates: [16.0759, 108.2238], schematic: [49.2, 22.4], time: "21:18:36" },
  { id: "LED-HC-001", type: "led", area: "Hải Châu", status: "Hoạt động", address: "Cầu Rồng", coordinates: [16.0610, 108.2266], schematic: [61.6, 49.2], time: "21:41:58" },
  { id: "L-ST-004", type: "light", area: "Sơn Trà", status: "Hoạt động", address: "42 Trần Hưng Đạo", coordinates: [16.066, 108.232], schematic: [75.6, 47.4], time: "21:41:55" },
  { id: "LED-NHS-014", type: "led", area: "Ngũ Hành Sơn", status: "Hoạt động", address: "209 Lê Văn Hiến", coordinates: [15.998, 108.260], schematic: [87.5, 73.7], time: "21:41:39" },
  { id: "L-TK-022", type: "light", area: "Thanh Khê", status: "Hoạt động", address: "32 Hà Huy Tập", coordinates: [16.0653, 108.1871], schematic: [18.7, 66.0], time: "21:41:53" },
];

export const deviceTone = { "Hoạt động": "green", "Cảnh báo": "amber", "Mất kết nối": "red", "Ngoại tuyến": "muted" } as const;

export const teams = ["Đội kỹ thuật Hải Châu", "Đội kỹ thuật Sơn Trà", "Đội kỹ thuật Thanh Khê", "Đội kỹ thuật Ngũ Hành Sơn"] as const;
export const teamLeads = ["Nguyễn Văn Hùng", "Trần Minh Tâm", "Lê Quốc Bảo", "Phạm Khánh Linh"];

type AlarmStatus = "Đã phân công" | "Đang xử lý" | "Chưa tiếp nhận" | "Đã tiếp nhận";
export type Severity = "Nghiêm trọng" | "Cảnh báo";
export type Alarm = { id: string; deviceId: string; short: string; title: string; severity: Severity; status: AlarmStatus; time: string; team?: string; jobId?: string; earlier?: boolean };

const featuredAlarms: Alarm[] = [
  { id: "ALM-20261113-024", deviceId: "TĐK-HC-023", short: "Mất kết nối tủ", title: "Mất kết nối tủ điều khiển", severity: "Nghiêm trọng", status: "Đã phân công", time: "21:38:12", team: teams[0], jobId: "WO-1042" },
  { id: "ALM-20261113-023", deviceId: "TĐK-ST-008", short: "Quá dòng L2", title: "Quá dòng nhánh L2", severity: "Nghiêm trọng", status: "Đang xử lý", time: "21:35:46", team: teams[1], jobId: "WO-1041" },
  { id: "ALM-20261113-022", deviceId: "TĐK-HC-041", short: "Rò điện nhánh L1", title: "Rò điện nhánh L1", severity: "Nghiêm trọng", status: "Đang xử lý", time: "21:33:08" },
  { id: "ALM-20261113-021", deviceId: "TĐK-TK-012", short: "Điện áp thấp", title: "Điện áp thấp (< 190V)", severity: "Cảnh báo", status: "Chưa tiếp nhận", time: "21:31:20", team: teams[2] },
  { id: "ALM-20261113-020", deviceId: "L-HC-01892", short: "Đèn không phản hồi", title: "Đèn không phản hồi", severity: "Cảnh báo", status: "Đang xử lý", time: "21:27:42", team: teams[0], jobId: "WO-1040" },
  { id: "ALM-20261113-019", deviceId: "TĐK-ST-016", short: "Nhiệt độ tủ cao", title: "Nhiệt độ tủ điều khiển cao", severity: "Cảnh báo", status: "Chưa tiếp nhận", time: "21:22:15", team: teams[1] },
  { id: "ALM-20261113-018", deviceId: "LED-HC-009", short: "LED ngoại tuyến", title: "Màn hình LED ngoại tuyến", severity: "Cảnh báo", status: "Đang xử lý", time: "21:18:36", team: teams[0], jobId: "WO-1039" },
];

const monitoringMessages = ["Mất gói dữ liệu", "Tín hiệu phản hồi chậm", "Cần kiểm tra nguồn", "Kết nối chập chờn"];

export const initialAlarms: Alarm[] = [
  ...featuredAlarms,
  ...Array.from({ length: 17 }, (_, index): Alarm => {
    const earlier = index > 12;
    const times = ["23:45:00", "23:15:00", "22:45:00", "22:15:00"];
    const time = earlier ? times[index - 13] : `${20 - Math.floor(index / 3)}:${[45, 30, 15][index % 3]}:00`;
    return {
      id: `ALM-${earlier ? "20261112" : "20261113"}-${String(17 - index).padStart(3, "0")}`,
      deviceId: devices[(index + 2) % devices.length].id,
      short: monitoringMessages[index % monitoringMessages.length],
      title: monitoringMessages[index % monitoringMessages.length],
      severity: "Cảnh báo",
      status: index < 3 ? "Đang xử lý" : "Chưa tiếp nhận",
      time,
      earlier,
    };
  }),
];

export const jobStatuses = ["Mới tạo", "Đang di chuyển", "Đang xử lý", "Chờ vật tư"] as const;
export type JobStatus = (typeof jobStatuses)[number];
export type Job = { id: string; title: string; deviceId: string; severity: Severity | "Định kỳ"; status: JobStatus; team: string; remaining: string; checklist?: boolean[] };

export const initialJobs: Job[] = [
  { id: "WO-1042", title: "Mất kết nối tủ", deviceId: "TĐK-HC-023", severity: "Nghiêm trọng", status: "Đang di chuyển", team: teams[0], remaining: "Còn 18 phút" },
  { id: "WO-1041", title: "Quá dòng nhánh L2", deviceId: "TĐK-ST-008", severity: "Nghiêm trọng", status: "Đang xử lý", team: teams[1], remaining: "Còn 26 phút" },
  { id: "WO-1040", title: "Đèn không phản hồi", deviceId: "L-HC-01892", severity: "Cảnh báo", status: "Chờ vật tư", team: teams[0], remaining: "Còn 1 giờ" },
  { id: "WO-1039", title: "Bảo trì màn hình LED", deviceId: "LED-HC-009", severity: "Định kỳ", status: "Mới tạo", team: teams[0], remaining: "Còn 2 giờ" },
  ...Array.from({ length: 14 }, (_, index): Job => ({
    id: `WO-${1038 - index}`,
    title: ["Kiểm tra nguồn cấp", "Kiểm tra tủ chiếu sáng", "Rà soát kết nối thiết bị", "Bảo dưỡng định kỳ"][index % 4],
    deviceId: devices[(index + 4) % devices.length].id,
    severity: index < 2 ? "Cảnh báo" : "Định kỳ",
    status: index < 5 ? "Mới tạo" : index < 11 ? "Đang xử lý" : "Chờ vật tư",
    team: teams[(index + 1) % teams.length],
    remaining: index === 0 ? "Còn 12 phút" : "Còn 3 giờ",
  })),
];

export function getDevice(id: string) {
  return devices.find((device) => device.id === id);
}

export function formatNumber(value: number, decimals = 0) {
  return value.toLocaleString("vi-VN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function normalizeSearch(value: string) {
  return value.toLowerCase().replace(/đ/g, "d").normalize("NFD").replace(/\p{Diacritic}/gu, "").trim();
}

export function matchesQuery(query: string, ...values: string[]) {
  const text = normalizeSearch(values.join(" "));
  return normalizeSearch(query).split(/\s+/).every((part) => text.includes(part));
}

export function downloadCsv(filename: string, rows: (string | number)[][]) {
  const encodeCell = (cell: string | number) => {
    let value = String(cell);
    if (typeof cell === "string" && /^[=+\-@\t\r]/.test(value)) value = `'${value}`;
    return `"${value.replace(/"/g, '""')}"`;
  };
  const csv = rows.map((row) => row.map(encodeCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8;" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
