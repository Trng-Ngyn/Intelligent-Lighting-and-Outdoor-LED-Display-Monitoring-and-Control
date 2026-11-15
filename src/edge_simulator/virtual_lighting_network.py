"""Entrypoint của Virtual Edge Simulator (MQTT 5).

Vị trí trong luồng: Simulator -> Broker -> Cloud. File này chỉ làm nhiệm vụ
điều phối: đọc cấu hình, tạo nhiều SimulatorDevice, chạy vòng phát telemetry
và xử lý dừng/chế độ crash để kiểm thử LWT.

Cách chạy:
    python src/edge_simulator/virtual_lighting_network.py --config config.json

Xem src/edge_simulator/README.md và
docs/specifications/MQTT5_COMMUNICATION_PROTOCOL.md.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional, Sequence

# Cho phép chạy trực tiếp file này (sys.path[0] là src/edge_simulator) mà vẫn
# import được package iot_protocol/edge_simulator ở thư mục src.
SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from edge_simulator.config import ConfigError, SimulatorConfig, load_config
from edge_simulator.mqtt_client import MqttConnectionError
from edge_simulator.simulator_device import SimulatorDevice

LOGGER_NAME = "edge_simulator"


def _configure_utf8_streams() -> None:
    """Buộc stdout/stderr dùng UTF-8 để log tiếng Việt không bị escape."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def configure_logging(level: str) -> None:
    """Cấu hình logging một lần cho toàn bộ tiến trình.

    Format có mili-giây để đo chính xác thời điểm online/offline khi kiểm thử
    LWT. Mỗi dòng log nghiệp vụ đều kèm topic và correlation_id ở nơi phát.
    """
    _configure_utf8_streams()
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=(
            "%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Đọc tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="Virtual Edge Simulator MQTT 5 cho đèn/LED PCCOM",
    )
    parser.add_argument(
        "--config",
        help="Đường dẫn config JSON (mặc định: SIM_CONFIG hoặc config.json)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Ghi đè log level trong config",
    )
    parser.add_argument(
        "--max-devices",
        type=int,
        help="Giới hạn số thiết bị sau khi mở rộng cấu hình (dùng khi test)",
    )
    parser.add_argument(
        "--crash-after",
        type=float,
        metavar="SECONDS",
        help="Tự thoát không gửi DISCONNECT sau N giây để kiểm thử LWT",
    )
    parser.add_argument(
        "--run-seconds",
        type=float,
        help="Tự dừng gracefully sau N giây (dùng cho kiểm thử tự động)",
    )
    return parser.parse_args(argv)


def apply_cli_overrides(
    config: SimulatorConfig,
    args: argparse.Namespace,
) -> SimulatorConfig:
    """Ghi đè cấu hình bằng tham số dòng lệnh nếu có."""
    settings = config.settings
    if args.log_level:
        settings = replace(settings, log_level=args.log_level.upper())
    if args.max_devices is not None:
        if args.max_devices < 1:
            raise ConfigError("--max-devices phải >= 1")
        settings = replace(settings, max_devices=args.max_devices)
    if args.crash_after is not None:
        if args.crash_after <= 0:
            raise ConfigError("--crash-after phải > 0")
        settings = replace(settings, crash_after_sec=args.crash_after)

    devices = config.devices
    if settings.max_devices is not None:
        devices = devices[: settings.max_devices]

    return replace(config, settings=settings, devices=devices)


def telemetry_loop(
    devices: Sequence[SimulatorDevice],
    interval_sec: float,
    stop_event: threading.Event,
    logger: logging.Logger,
) -> None:
    """Phát telemetry cho mọi thiết bị theo chu kỳ cố định.

    Dùng monotonic để tránh trôi thời gian khi mỗi vòng publish mất vài trăm
    mili-giây. Bản tin đầu tiên được phát ngay sau khi kết nối thành công.
    """
    next_run = time.monotonic()
    while not stop_event.is_set():
        started = time.monotonic()
        for device in devices:
            try:
                device.publish_telemetry()
            except Exception:  # pragma: no cover - một thiết bị lỗi không dừng cả mạng
                logger.exception(
                    "Lỗi phát telemetry device=%s",
                    device.spec.device_id,
                )
        logger.info(
            "Đã phát telemetry cho %s thiết bị trong %.1f ms",
            len(devices),
            (time.monotonic() - started) * 1000.0,
        )

        next_run += interval_sec
        sleep_for = max(0.0, next_run - time.monotonic())
        stop_event.wait(sleep_for)


def crash_after_delay(
    devices: Sequence[SimulatorDevice],
    delay_sec: float,
) -> None:
    """Chờ rồi gọi os._exit() để broker phải dùng LWT.

    Không gọi stop(), không gửi DISCONNECT, không publish offline: đây là
    kịch bản mô phỏng mất điện/mất mạng đột ngột.
    """
    time.sleep(delay_sec)
    if devices:
        devices[0].crash_process()
    else:  # pragma: no cover - không xảy ra vì config luôn có thiết bị
        import os

        os._exit(1)


def run(
    config: SimulatorConfig,
    logger: logging.Logger,
    run_seconds: Optional[float] = None,
) -> int:
    """Khởi động toàn bộ simulator và chờ đến khi dừng.

    Tham số:
        run_seconds: Nếu có, tự dừng gracefully sau N giây (dùng cho test).

    Trả về:
        Mã thoát 0 nếu dừng chủ động, 1 nếu không thiết bị nào kết nối được.
    """
    logger.info(
        "Nạp cấu hình từ %s: broker=%s:%s devices=%s keep_alive=%ss "
        "telemetry_interval=%ss replay_window=%sms",
        config.source_path,
        config.broker.host,
        config.broker.port,
        len(config.devices),
        config.settings.keep_alive_sec,
        config.settings.telemetry_interval_sec,
        config.settings.replay_window_ms,
    )

    devices = [
        SimulatorDevice(spec, config, logger.getChild(spec.device_id))
        for spec in config.devices
    ]

    started: list[SimulatorDevice] = []
    for device in devices:
        try:
            device.start()
            started.append(device)
        except (MqttConnectionError, OSError) as exc:
            logger.error(
                "Không kết nối được device=%s/%s/%s: %s",
                device.spec.site_id,
                device.spec.device_type,
                device.spec.device_id,
                exc,
            )

    if not started:
        logger.error("Không có thiết bị nào kết nối được broker")
        return 1

    logger.info("Đã kết nối %s/%s thiết bị", len(started), len(devices))

    stop_event = threading.Event()
    telemetry_thread = threading.Thread(
        target=telemetry_loop,
        args=(
            started,
            config.settings.telemetry_interval_sec,
            stop_event,
            logger,
        ),
        name="telemetry-loop",
        daemon=True,
    )
    telemetry_thread.start()

    crash_delay = config.settings.crash_after_sec
    if crash_delay is not None:
        logger.warning(
            "CRASH MODE bật: sẽ thoát không DISCONNECT sau %.1fs",
            crash_delay,
        )
        threading.Thread(
            target=crash_after_delay,
            args=(started, crash_delay),
            name="crash-timer",
            daemon=True,
        ).start()

    try:
        # run_seconds chỉ dùng cho test tự động; chạy thật sẽ chờ Ctrl+C.
        if run_seconds is None:
            while True:
                time.sleep(1.0)
        else:
            time.sleep(float(run_seconds))
    except KeyboardInterrupt:
        logger.info("Nhận Ctrl+C, dừng simulator...")
    finally:
        stop_event.set()
        telemetry_thread.join(timeout=5.0)
        for device in started:
            try:
                device.stop(graceful=True)
            except Exception:  # pragma: no cover
                logger.exception(
                    "Lỗi khi dừng device=%s",
                    device.spec.device_id,
                )
        logger.info("Simulator đã dừng")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Hàm main: đọc args, cấu hình logging, nạp config và chạy."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        config = apply_cli_overrides(config, args)
    except ConfigError as exc:
        # Chưa cấu hình logging nên in trực tiếp ra stderr.
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2

    configure_logging(config.settings.log_level)
    logger = logging.getLogger(LOGGER_NAME)
    if args.run_seconds is not None and args.run_seconds <= 0:
        logger.error("--run-seconds phải > 0")
        return 2

    return run(config, logger, run_seconds=args.run_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
