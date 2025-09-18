# main.py
import asyncio
import csv
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

# ========= Конфигурация =========
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DEALS_CSV = DATA_DIR / "deals.csv"
CLIENTS_CSV = DATA_DIR / "clients.csv"
CLIENTS_MAX_BTNS = 20  # сколько имён показывать на клавиатуре выбора

# ========= Утилиты =========
def ensure_dirs_and_headers():
    """Создаёт папку data и CSV с заголовками, если их ещё нет."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not DEALS_CSV.exists():
        with DEALS_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "deal_id","opened_at","client_A","client_B",
                "rub_target","rate_A_rub_per_usd","fee_A_pct",
                "rate_B_rub_per_usd","fee_B_pct","payout_currency_B",
                "status","est_rev_usd","final_rev_usd","notes"
            ])

    if not CLIENTS_CSV.exists():
        with CLIENTS_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["client_name"])

def normalize_number(s: str) -> Decimal:
    """
    Принимаем ввод с запятой или точкой -> Decimal.
    """
    s = (s or "").strip().replace(" ", "").replace(",", ".")
    return Decimal(s)

def to_pct_decimal(s: str) -> Decimal:
    """
    '1.5' -> 0.015; '0,5' -> 0.005; '0.015' -> 0.015
    """
    v = normalize_number(s)
    return v / Decimal("100") if v > 1 else v

def gen_deal_id() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"D-{ts}"

def est_revenue_usd(R: Decimal, rA: Decimal, fA: Decimal, rB: Decimal, fB: Decimal) -> Decimal:
    """
    Предварительный доход без поставщиков (M = 1).
    """
    usd_in = (R / rA) * (Decimal("1") + fA)
    usd_out = (R / rB) * (Decimal("1") - fB)
    return usd_in - usd_out

def save_deal_row(row: dict):
    with DEALS_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            row["deal_id"], row["opened_at"], row["client_A"], row["client_B"],
            f'{row["rub_target"]}', f'{row["rate_A_rub_per_usd"]}', f'{row["fee_A_pct"]}',
            f'{row["rate_B_rub_per_usd"]}', f'{row["fee_B_pct"]}', row["payout_currency_B"],
            row["status"], f'{row["est_rev_usd"]}', "", row.get("notes","")
        ])

# ====== Справочник клиентов ======
def load_clients() -> List[str]:
    if not CLIENTS_CSV.exists():
        return []
    out = []
    with CLIENTS_CSV.op_
