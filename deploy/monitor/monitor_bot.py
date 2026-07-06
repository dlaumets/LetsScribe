#!/usr/bin/env python3
"""Telegram bot for on-demand server monitoring."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from collectors import (
    collect_all,
    collect_cpv,
    collect_docker,
    collect_server,
    collect_transcriber,
    collect_vpn,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

router = Router()

TRANSCRIBER_API = os.getenv("MONITOR_TRANSCRIBER_API", "http://127.0.0.1:8000")
CPV_UNITS = [
    unit.strip()
    for unit in os.getenv("MONITOR_CPV_UNITS", "cpv-bot.service,cpv-api.service").split(",")
    if unit.strip()
]
VPN_IFACE = os.getenv("MONITOR_VPN_IFACE", "awg0")


def allowed_ids() -> set[int]:
    raw = os.getenv("MONITOR_ALLOWED_IDS", "")
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


def is_allowed(message: Message) -> bool:
    ids = allowed_ids()
    if not ids:
        return True
    return bool(message.from_user and message.from_user.id in ids)


async def deny_or(message: Message) -> bool:
    if is_allowed(message):
        return True
    await message.answer("Нет доступа. Отправь /whoami и добавь свой ID в MONITOR_ALLOWED_IDS.")
    return False


@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    if not await deny_or(message):
        return
    await message.answer(
        "<b>Мониторинг сервера</b>\n\n"
        "/status — всё сразу\n"
        "/server — CPU, RAM, диск\n"
        "/transcriber — LetsTranscriber\n"
        "/docker — все контейнеры\n"
        "/cpv — cpv_bot сервисы\n"
        "/vpn — VPN (awg0)\n"
        "/whoami — твой Telegram ID",
        parse_mode="HTML",
    )


@router.message(Command("whoami"))
async def cmd_whoami(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    await message.answer(f"Твой Telegram ID: <code>{uid}</code>", parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not await deny_or(message):
        return
    text = collect_all(TRANSCRIBER_API)
    if len(text) <= 4000:
        await message.answer(text, parse_mode="HTML")
        return
    for chunk in _split_message(text, 4000):
        await message.answer(chunk, parse_mode="HTML")


def _split_message(text: str, limit: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        piece = block if not current else f"{current}\n\n{block}"
        if len(piece) > limit and current:
            parts.append(current)
            current = block
        else:
            current = piece
    if current:
        parts.append(current)
    return parts


@router.message(Command("server"))
async def cmd_server(message: Message) -> None:
    if not await deny_or(message):
        return
    await message.answer(collect_server(), parse_mode="HTML")


@router.message(Command("transcriber"))
async def cmd_transcriber(message: Message) -> None:
    if not await deny_or(message):
        return
    await message.answer(collect_transcriber(TRANSCRIBER_API), parse_mode="HTML")


@router.message(Command("docker"))
async def cmd_docker(message: Message) -> None:
    if not await deny_or(message):
        return
    await message.answer(collect_docker(), parse_mode="HTML")


@router.message(Command("cpv"))
async def cmd_cpv(message: Message) -> None:
    if not await deny_or(message):
        return
    await message.answer(collect_cpv(CPV_UNITS), parse_mode="HTML")


@router.message(Command("vpn"))
async def cmd_vpn(message: Message) -> None:
    if not await deny_or(message):
        return
    await message.answer(collect_vpn(VPN_IFACE), parse_mode="HTML")


async def main() -> None:
    token = os.getenv("MONITOR_BOT_TOKEN")
    if not token:
        raise SystemExit("MONITOR_BOT_TOKEN is required")

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Monitor bot starting (allowed_ids=%s)", allowed_ids() or "any")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
