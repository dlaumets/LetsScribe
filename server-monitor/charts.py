"""PNG chart generation for Telegram reports."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from metrics import MetricsSnapshot

# Non-interactive backend for headless server
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BG = "#090a0e"
PANEL = "#181b24"
TEXT = "#f0ebe3"
MUTED = "#8c8799"
COLORS = ["#e8a838", "#5cce8f", "#6ea8fe", "#f07070", "#c48820", "#8c8799"]


def _style_ax(ax) -> None:
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.title.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_color("#2a2f3d")


def render_charts(snapshot: "MetricsSnapshot") -> list[tuple[str, bytes]]:
    charts: list[tuple[str, bytes]] = []
    charts.append(("Память", _memory_chart(snapshot)))
    if snapshot.docker:
        charts.append(("Docker RAM", _docker_chart(snapshot)))
    if snapshot.systemd:
        charts.append(("Сервисы", _systemd_chart(snapshot)))
    charts.append(("Диск", _disk_chart(snapshot)))
    return charts


def _save_fig(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, facecolor=BG, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _memory_chart(s: "MetricsSnapshot") -> bytes:
    fig, ax = plt.subplots(figsize=(6, 3.2), facecolor=BG)
    _style_ax(ax)

    avail = max(0.0, s.mem_available_mb)
    used = max(0.0, s.mem_total_mb - avail)
    labels = ["Занято", "Свободно", "Swap"]
    values = [used, s.mem_available_mb, s.swap_used_mb]
    colors = [COLORS[3], COLORS[1], COLORS[0]]

    bars = ax.barh(labels, values, color=colors, height=0.55)
    ax.set_xlabel("MB", color=MUTED)
    ax.set_title(f"RAM {s.mem_used_mb:.0f}/{s.mem_total_mb:.0f} MB · load {s.load_1:.2f}", fontsize=11)
    for bar, val in zip(bars, values):
        if val > 0:
            ax.text(bar.get_width() + 8, bar.get_y() + bar.get_height() / 2, f"{val:.0f}", va="center", color=TEXT, fontsize=9)
    fig.tight_layout()
    return _save_fig(fig)


def _docker_chart(s: "MetricsSnapshot") -> bytes:
    fig, ax = plt.subplots(figsize=(6, max(2.5, len(s.docker) * 0.55 + 1)), facecolor=BG)
    _style_ax(ax)
    names = [c.short_name for c in s.docker]
    mems = [c.mem_used_mb for c in s.docker]
    cpus = [c.cpu_percent for c in s.docker]
    y = range(len(names))
    bars = ax.barh(list(y), mems, color=COLORS[2], height=0.6, label="RAM MB")
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, color=TEXT)
    ax.set_xlabel("RAM (MB)", color=MUTED)
    ax.set_title("Docker · RAM и CPU%", fontsize=11)
    for i, (mem, cpu) in enumerate(zip(mems, cpus)):
        ax.text(mem + 5, i, f"{mem:.0f} MB · {cpu:.1f}%", va="center", color=TEXT, fontsize=8)
    fig.tight_layout()
    return _save_fig(fig)


def _systemd_chart(s: "MetricsSnapshot") -> bytes:
    fig, ax = plt.subplots(figsize=(6, max(2.2, len(s.systemd) * 0.5 + 1)), facecolor=BG)
    _style_ax(ax)
    names = [svc.unit for svc in s.systemd]
    mems = [svc.mem_mb for svc in s.systemd]
    y = range(len(names))
    ax.barh(list(y), mems, color=COLORS[4], height=0.55)
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, color=TEXT)
    ax.set_xlabel("RAM (MB)", color=MUTED)
    ax.set_title("CPV / systemd", fontsize=11)
    for i, mem in enumerate(mems):
        ax.text(mem + 2, i, f"{mem:.0f} MB", va="center", color=TEXT, fontsize=8)
    fig.tight_layout()
    return _save_fig(fig)


def _disk_chart(s: "MetricsSnapshot") -> bytes:
    fig, ax = plt.subplots(figsize=(5, 2.8), facecolor=BG)
    _style_ax(ax)
    free = max(0.0, s.disk_total_gb - s.disk_used_gb)
    ax.bar(
        ["Занято", "Свободно"],
        [s.disk_used_gb, free],
        color=[COLORS[3], COLORS[1]],
        width=0.5,
    )
    ax.set_ylabel("GB", color=MUTED)
    ax.set_title(f"Диск / · {s.disk_percent:.0f}% занято", fontsize=11)
    for i, val in enumerate([s.disk_used_gb, free]):
        ax.text(i, val + 0.1, f"{val:.1f}", ha="center", color=TEXT, fontsize=9)
    fig.tight_layout()
    return _save_fig(fig)
