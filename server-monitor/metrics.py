"""Structured metrics snapshot for text reports and charts."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DockerContainer:
    name: str
    short_name: str
    cpu_percent: float
    mem_used_mb: float
    mem_limit_mb: float | None
    mem_percent: float


@dataclass
class SystemdService:
    unit: str
    state: str
    mem_mb: float
    cpu_seconds: float


@dataclass
class MetricsSnapshot:
    cpu_count: int
    load_1: float
    load_5: float
    load_15: float
    mem_total_mb: float
    mem_used_mb: float
    mem_available_mb: float
    swap_total_mb: float
    swap_used_mb: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    uptime: str
    docker: list[DockerContainer] = field(default_factory=list)
    systemd: list[SystemdService] = field(default_factory=list)
    transcriber_ok: bool = False
    transcriber_model_loaded: bool = False
    transcriber_queue: int = 0
    transcriber_preset: str = "—"
    vpn_rx_mb: float = 0.0
    vpn_tx_mb: float = 0.0
    vpn_peers: int = 0


def _run(cmd: list[str], timeout: int = 5) -> str:
    if not shutil.which(cmd[0]):
        return ""
    wrapped = cmd
    if shutil.which("timeout") and timeout > 0:
        wrapped = ["timeout", str(timeout), *cmd]
    try:
        result = subprocess.run(
            wrapped,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            check=False,
        )
        return (result.stdout or result.stderr or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _parse_size_to_mb(value: str) -> float:
    value = value.strip().upper()
    match = re.match(r"([\d.]+)\s*(B|KIB|MIB|GIB|TIB|KB|MB|GB|TB)?", value)
    if not match:
        return 0.0
    amount = float(match.group(1))
    unit = (match.group(2) or "B").replace("IB", "B")
    factors = {"B": 1 / 1024 / 1024, "KB": 1 / 1024, "MB": 1.0, "GB": 1024.0, "TB": 1024 * 1024}
    return amount * factors.get(unit, 1 / 1024 / 1024)


def _parse_cpu_percent(value: str) -> float:
    return float(value.strip().rstrip("%") or 0)


def _read_meminfo() -> dict[str, int]:
    data: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        data[key.strip()] = int(value.strip().split()[0])
    return data


def _docker_rows() -> list[str]:
    out = _run(
        [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
        ],
        timeout=6,
    )
    return [line for line in out.splitlines() if line.strip()]


def _parse_docker_row(row: str) -> DockerContainer | None:
    parts = row.split("\t")
    if len(parts) < 4:
        return None
    name, cpu, mem_usage, mem_pct = parts[0], parts[1], parts[2], parts[3]
    used_raw, _, limit_raw = mem_usage.partition("/")
    limit_mb = _parse_size_to_mb(limit_raw) if limit_raw else None
    short = name.replace("letstranscriber-", "").removesuffix("-1")
    return DockerContainer(
        name=name,
        short_name=short,
        cpu_percent=_parse_cpu_percent(cpu),
        mem_used_mb=_parse_size_to_mb(used_raw),
        mem_limit_mb=limit_mb,
        mem_percent=_parse_cpu_percent(mem_pct),
    )


def build_snapshot(
    transcriber_api: str = "http://127.0.0.1:8000",
    systemd_units: list[str] | None = None,
    vpn_iface: str = "awg0",
) -> MetricsSnapshot:
    units = systemd_units or ["cpv-bot.service", "cpv-api.service"]
    meminfo = _read_meminfo()
    total_kb = meminfo.get("MemTotal", 0)
    avail_kb = meminfo.get("MemAvailable", 0)
    swap_total_kb = meminfo.get("SwapTotal", 0)
    swap_free_kb = meminfo.get("SwapFree", 0)
    used_kb = total_kb - avail_kb
    swap_used_kb = swap_total_kb - swap_free_kb

    load_parts = Path("/proc/loadavg").read_text().split()
    load = [float(x) for x in load_parts[:3]] + [0.0, 0.0, 0.0]

    disk_line = _run(["df", "-B1", "/", "--output=size,used,pcent", "-x", "tmpfs"], timeout=4)
    disk_total_gb = disk_used_gb = 0.0
    disk_percent = 0.0
    if disk_line:
        parts = disk_line.splitlines()[-1].split()
        if len(parts) >= 3:
            disk_total_gb = int(parts[0]) / 1024 ** 3
            disk_used_gb = int(parts[1]) / 1024 ** 3
            disk_percent = float(parts[2].rstrip("%"))

    uptime = (_run(["uptime", "-p"], timeout=3) or _run(["uptime"], timeout=3)).replace("up ", "")

    docker = [c for row in _docker_rows() if (c := _parse_docker_row(row))]

    systemd: list[SystemdService] = []
    for unit in units:
        props = _run(
            ["systemctl", "show", unit, "--property=ActiveState,MemoryCurrent,CPUUsageNSec", "--no-pager"],
            timeout=4,
        )
        if not props:
            continue
        data = dict(line.split("=", 1) for line in props.splitlines() if "=" in line)
        raw_mem = data.get("MemoryCurrent", "0") or "0"
        mem = 0 if raw_mem.startswith("[") else int(raw_mem)
        raw_cpu = data.get("CPUUsageNSec", "0") or "0"
        cpu_ns = 0 if raw_cpu.startswith("[") else int(raw_cpu)
        systemd.append(
            SystemdService(
                unit=unit.replace(".service", ""),
                state=data.get("ActiveState", "?"),
                mem_mb=mem / 1024 / 1024,
                cpu_seconds=cpu_ns / 1e9,
            )
        )

    cpu_count = max(1, Path("/proc/cpuinfo").read_text().count("processor\t:"))
    snap = MetricsSnapshot(
        cpu_count=cpu_count,
        load_1=load[0],
        load_5=load[1],
        load_15=load[2],
        mem_total_mb=total_kb / 1024,
        mem_used_mb=used_kb / 1024,
        mem_available_mb=avail_kb / 1024,
        swap_total_mb=swap_total_kb / 1024,
        swap_used_mb=swap_used_kb / 1024,
        disk_total_gb=disk_total_gb,
        disk_used_gb=disk_used_gb,
        disk_percent=disk_percent,
        uptime=uptime,
        docker=docker,
        systemd=systemd,
    )

    health = _run(["curl", "-sf", "--max-time", "3", f"{transcriber_api}/v1/health"], timeout=4)
    if health:
        try:
            data = json.loads(health)
            snap.transcriber_ok = True
            snap.transcriber_model_loaded = bool(data.get("model_loaded"))
            snap.transcriber_queue = int(data.get("queue_size", 0))
            snap.transcriber_preset = str(data.get("current_preset") or "—")
        except json.JSONDecodeError:
            pass

    iface = Path(f"/sys/class/net/{vpn_iface}")
    if iface.exists():
        snap.vpn_rx_mb = int((iface / "statistics/rx_bytes").read_text()) / 1024 / 1024
        snap.vpn_tx_mb = int((iface / "statistics/tx_bytes").read_text()) / 1024 / 1024
        wg = _run(["wg", "show", vpn_iface], timeout=3)
        snap.vpn_peers = sum(1 for line in wg.splitlines() if line.strip().startswith("peer:"))

    return snap
