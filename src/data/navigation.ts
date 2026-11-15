import { LayoutGrid, Map, Lightbulb, Zap, TriangleAlert, MonitorPlay, CalendarDays, Server, UsersRound, Settings, ShieldAlert, PanelsTopLeft } from "lucide-react";

export const mainNavigation = [
  { label: "Overview Dashboard", title: "Tổng quan vận hành", path: "/", icon: LayoutGrid },
  { label: "GIS Map View", title: "Bản đồ hạ tầng đô thị", path: "/gis", icon: Map },
  { label: "Lighting Control", title: "Điều khiển chiếu sáng", path: "/dimming", icon: Lightbulb },
  { label: "Energy Monitoring", title: "Giám sát năng lượng", path: "/energy", icon: Zap },
  { label: "Alarm Management", title: "Quản lý cảnh báo", path: "/alarms", icon: TriangleAlert },
  { label: "LED Content Management", title: "Quản lý nội dung LED", path: "/led", icon: MonitorPlay },
  { label: "Schedule Management", title: "Lịch chiếu sáng", path: "/dimming#schedule", icon: CalendarDays },
  { label: "Device Management", title: "Danh sách thiết bị", path: "/gis?panel=devices", icon: Server },
  { label: "User Management", title: "Quản lý người dùng", path: "", icon: UsersRound },
  { label: "System Settings", title: "Cài đặt hệ thống", path: "", icon: Settings },
] as const;

export const shortcuts = [
  { label: "Cảnh báo khẩn cấp", title: "Phát cảnh báo khẩn cấp", path: "/emergency", icon: ShieldAlert },
  { label: "Công việc hiện trường", title: "Điều phối hiện trường", path: "/field-operations", icon: PanelsTopLeft },
] as const;
