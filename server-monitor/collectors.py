"""Text formatters for metrics snapshots."""

from __future__ import annotations

from metrics import MetricsSnapshot, build_snapshot


def _fmt_mb(mb: float) -> str:
    return f"{mb:.0f} MB"


def _pct(used: float, total: float) -> int:
    if total <= 0:
        return 0
    return round(used * 100 / total)


def format_server(s: MetricsSnapshot) -> str:
    lines = [
        "🖥 <b>Сервер</b>",
        f"CPU: {s.cpu_count} ядер · load {s.load_1:.2f} {s.load_5:.2f} {s.load_15:.2f}",
        f"RAM: {_fmt_mb(s.mem_used_mb)} / {_fmt_mb(s.mem_total_mb)} ({_pct(s.mem_used_mb, s.mem_total_mb)}%)",
        f"Swap: {_fmt_mb(s.swap_used_mb)} / {_fmt_mb(s.swap_total_mb)}",
        f"Диск /: {s.disk_used_gb:.1f} / {s.disk_total_gb:.1f} GB ({s.disk_percent:.0f}%)",
    ]
    if s.uptime:
        lines.append(f"Uptime: {s.uptime}")
    return "\n".join(lines)


def format_docker(s: MetricsSnapshot) -> str:
    if not s.docker:
        return "🐳 <b>Docker</b>\nнет данных"
    lines = ["🐳 <b>Docker</b>"]
    for c in s.docker:
        lines.append(
            f"• <code>{c.short_name}</code>: CPU {c.cpu_percent:.1f}%, "
            f"RAM {_fmt_mb(c.mem_used_mb)} ({c.mem_percent:.0f}%)"
        )
    return "\n".join(lines)


def format_transcriber(s: MetricsSnapshot) -> str:
    lines = ["🎙 <b>LetsTranscriber</b>"]
    if s.transcriber_ok:
        model = "загружена" if s.transcriber_model_loaded else "не в памяти"
        lines.append(f"API: ok · модель {model}")
        lines.append(f"Очередь: {s.transcriber_queue} · preset: {s.transcriber_preset}")
    else:
        lines.append("API: недоступен")
    for c in s.docker:
        if c.name.startswith("letstranscriber-"):
            lines.append(
                f"• <code>{c.short_name}</code>: CPU {c.cpu_percent:.1f}%, RAM {_fmt_mb(c.mem_used_mb)}"
            )
    return "\n".join(lines)


def format_cpv(s: MetricsSnapshot) -> str:
    lines = ["📋 <b>CPV Bot</b>"]
    for svc in s.systemd:
        lines.append(
            f"• <code>{svc.unit}</code>: {svc.state}, "
            f"RAM {_fmt_mb(svc.mem_mb)}, CPU {svc.cpu_seconds:.1f}s"
        )
    if not s.systemd:
        lines.append("сервисы не найдены")
    return "\n".join(lines)


def format_vpn(s: MetricsSnapshot) -> str:
    if s.vpn_rx_mb == 0 and s.vpn_tx_mb == 0 and s.vpn_peers == 0:
        return "🔒 <b>VPN</b>\nинтерфейс не найден или нет данных"
    return (
        f"🔒 <b>VPN</b>\n"
        f"Трафик: ↓ {_fmt_mb(s.vpn_rx_mb)} · ↑ {_fmt_mb(s.vpn_tx_mb)}\n"
        f"Пиров: {s.vpn_peers}"
    )


def format_snapshot(s: MetricsSnapshot) -> str:
    return "\n\n".join(
        [
            format_server(s),
            format_transcriber(s),
            format_docker(s),
            format_cpv(s),
            format_vpn(s),
        ]
    )


def format_all(
    transcriber_api: str = "http://127.0.0.1:8000",
    systemd_units: list[str] | None = None,
    vpn_iface: str = "awg0",
) -> str:
    return format_snapshot(build_snapshot(transcriber_api, systemd_units, vpn_iface))


# Backward-compatible aliases for single-section commands
def collect_server() -> str:
    return format_server(build_snapshot())


def collect_docker() -> str:
    return format_docker(build_snapshot())


def collect_transcriber(api_url: str = "http://127.0.0.1:8000") -> str:
    return format_transcriber(build_snapshot(api_url))


def collect_cpv(units: list[str]) -> str:
    return format_cpv(build_snapshot(systemd_units=units))


def collect_vpn(iface: str = "awg0") -> str:
    return format_vpn(build_snapshot(vpn_iface=iface))


def collect_all(transcriber_api: str) -> str:
    return format_all(transcriber_api)
