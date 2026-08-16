#!/usr/bin/env python3
"""
🤖 TELEGRAM БОТ ДЛЯ МАССОВЫХ РАССЫЛОК 🤖
@avtorasslkabot - ВСЕ КНОПКИ РАБОТАЮТ
Версия: 3.0.3
"""

import asyncio
import sqlite3
import os
import sys
import json
import re
import time
import random
import string
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import contextmanager
from functools import wraps
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum

# ============================================================================
# УДАЛЕНИЕ СТАРЫХ ФАЙЛОВ СЕССИЙ
# ============================================================================
session_files = ['bot_session.session', 'bot_session.session.lock']
for file in session_files:
    if os.path.exists(file):
        try:
            os.remove(file)
            print(f"🗑️ Удален старый файл сессии: {file}")
        except Exception as e:
            print(f"⚠️ Не удалось удалить {file}: {e}")

# ============================================================================
# АВТОМАТИЧЕСКАЯ УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================================
def auto_install():
    packages = ['telethon', 'apscheduler', 'loguru', 'pillow', 'cryptg']
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"📦 Установка {package}...")
            os.system(f"{sys.executable} -m pip install {package} --quiet")

auto_install()

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from telethon import TelegramClient, Button, events
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberFloodError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError,
    RPCError,
    UserAlreadyParticipantError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    ChatWriteForbiddenError,
    SlowModeWaitError,
    MessageTooLongError,
    MediaInvalidError,
    UserNotParticipantError,
    UserBannedInChannelError,
    PeerIdInvalidError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
    InviteHashInvalidError,
    InviteHashExpiredError,
    UserPrivacyRestrictedError,
    ChatSendInlineForbiddenError,
    ChatSendMediaForbiddenError,
    MessageDeleteForbiddenError,
    ChannelInvalidError
)
from telethon.tl.types import (
    Channel,
    Chat,
    InputPeerChat,
    InputPeerChannel,
    MessageMediaPhoto,
    MessageMediaDocument,
    User,
    ChatForbidden,
    ChannelForbidden,
    Message,
    PeerUser,
    PeerChat,
    PeerChannel
)
from telethon.tl.functions.messages import SendMessageRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from loguru import logger
from PIL import Image
import io

# ============================================================================
# КОНФИГУРАЦИЯ (НОВЫЙ БОТ)
# ============================================================================
API_ID = 28121815
API_HASH = "05ad718bad150a8e636724e9fed59503"
BOT_TOKEN = "8982691390:AAFlUfA0rL-iXfnV2-jqfYQz0CaY6eEsPK8"
ADMIN_IDS = [8365786708, 6668784806]
CARD_NUMBER = "2202 2081 8598 3716"
CARD_HOLDER = "AVTOR BOT"
BANK_NAME = "СБЕРБАНК"
PRICE_PER_DAY = 15
FREE_TRIAL_DAYS = 3
BOT_USERNAME = "avtorasslkabot"
VERSION = "3.0.3"

DB_PATH = "bot_database.db"
SPONSORS_FILE = "sponsors.json"
REQUIRED_CHANNELS_FILE = "required_channels.json"
SETTINGS_FILE = "settings.json"
LOG_FILE = "bot.log"

MAX_GROUPS_PER_USER = 1000
MAX_MESSAGE_LENGTH = 4096
MAX_RETRY_ATTEMPTS = 5
RATE_LIMIT_DELAY = 2
FLOOD_WAIT_BUFFER = 15
MAX_SEND_GROUPS = 200

# ============================================================================
# ПОДПИСЬ
# ============================================================================
SIGNATURE = f"""

📢 Бесплатная рассылка 3 дня - @{BOT_USERNAME}
🤖 Версия {VERSION}"""

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ
# ============================================================================
bot = TelegramClient("bot_session", API_ID, API_HASH, connection_retries=10)
scheduler = AsyncIOScheduler()

# ============================================================================
# ГЛОБАЛЬНЫЕ ХРАНИЛИЩА СОСТОЯНИЙ
# ============================================================================
user_states: Dict[int, Dict] = {}
phone_waiting: Dict[int, bool] = {}
code_waiting: Dict[int, str] = {}
password_waiting: Dict[int, Dict] = {}
user_clients: Dict[int, TelegramClient] = {}
user_phones: Dict[int, str] = {}
user_temp_codes: Dict[int, str] = {}
scheduled_jobs: Dict[str, Dict] = {}

# ============================================================================
# УТИЛИТЫ
# ============================================================================
def format_number(num: int) -> str:
    if num is None:
        return "0"
    return f"{num:,}".replace(",", " ")

def generate_id(length: int = 16) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_timestamp() -> str:
    return datetime.now().isoformat()

def truncate_text(text: str, max_length: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def safe_json_load(file_path: str, default: Any = None) -> Any:
    if default is None:
        default = []
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default
    except Exception as e:
        logger.error(f"Ошибка загрузки {file_path}: {e}")
        return default

def safe_json_save(file_path: str, data: Any) -> bool:
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения {file_path}: {e}")
        return False

def add_signature(text: str) -> str:
    if not text:
        return SIGNATURE.strip()
    if len(text) + len(SIGNATURE) > MAX_MESSAGE_LENGTH:
        return text[:MAX_MESSAGE_LENGTH - len(SIGNATURE) - 15] + SIGNATURE
    return f"{text}{SIGNATURE}"

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================================================
def init_database():
    with get_db_connection() as conn:
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TEXT,
            subscription_end TEXT,
            subscription_type TEXT DEFAULT 'Нет',
            has_subscription INTEGER DEFAULT 0,
            total_paid INTEGER DEFAULT 0,
            trial_used INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            checked_channels INTEGER DEFAULT 0,
            referral_code TEXT,
            referred_by INTEGER,
            referral_count INTEGER DEFAULT 0,
            last_activity TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            session_string TEXT,
            created_at TEXT,
            last_used TEXT,
            is_active INTEGER DEFAULT 1
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id INTEGER,
            group_username TEXT,
            group_title TEXT,
            group_type TEXT DEFAULT 'group',
            added_at TEXT,
            is_active INTEGER DEFAULT 1,
            UNIQUE(user_id, group_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS send_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_name TEXT,
            group_id INTEGER,
            sent_at TEXT,
            message_text TEXT,
            message_type TEXT DEFAULT 'text',
            status TEXT DEFAULT 'sent',
            error_message TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            days INTEGER,
            status TEXT DEFAULT 'pending',
            transaction_id TEXT,
            created_at TEXT,
            confirmed_at TEXT,
            confirmed_by INTEGER
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scheduled_sends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            groups TEXT,
            message TEXT,
            image_data BLOB,
            scheduled_at TEXT,
            interval_hours INTEGER DEFAULT 0,
            next_run TEXT,
            active INTEGER DEFAULT 1,
            last_run TEXT,
            total_runs INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            created_at TEXT,
            reward_given INTEGER DEFAULT 0
        )''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(has_subscription, subscription_end)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_groups_user ON groups(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_history_user ON send_history(user_id, sent_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)')
        
        conn.commit()
        logger.info("✅ База данных инициализирована")

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ ФАЙЛОВ
# ============================================================================
def init_sponsors():
    if not os.path.exists(SPONSORS_FILE):
        safe_json_save(SPONSORS_FILE, [])

def init_required_channels():
    if not os.path.exists(REQUIRED_CHANNELS_FILE):
        safe_json_save(REQUIRED_CHANNELS_FILE, [])

def init_settings():
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "maintenance_mode": False,
            "registration_enabled": True,
            "broadcast_enabled": True,
            "min_delay_between_sends": 2,
            "max_groups_per_send": 200,
            "flood_protection_enabled": True,
            "max_messages_per_minute": 30
        }
        safe_json_save(SETTINGS_FILE, default_settings)

# ============================================================================
# РАБОТА С БД - ОСНОВНЫЕ ФУНКЦИИ
# ============================================================================
def register_user(user_id: int, username: str, first_name: str, last_name: str = "") -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            return False
        
        referral_code = generate_id(8)
        c.execute("""INSERT INTO users 
                    (user_id, username, first_name, last_name, registered_at, has_subscription, checked_channels, referral_code) 
                    VALUES (?, ?, ?, ?, ?, 0, 0, ?)""",
                  (user_id, username or "", first_name or "", last_name or "", get_timestamp(), referral_code))
        conn.commit()
        logger.info(f"✅ Новый пользователь: {user_id}")
        return True

def get_user(user_id: int) -> Optional[Dict]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""SELECT user_id, username, first_name, last_name, registered_at, 
                            subscription_end, subscription_type, has_subscription, total_paid, 
                            trial_used, is_banned, checked_channels, referral_code, referred_by, referral_count
                     FROM users WHERE user_id = ?""", (user_id,))
        row = c.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "username": row[1] or "",
            "first_name": row[2] or "",
            "last_name": row[3] or "",
            "registered_at": row[4],
            "subscription_end": row[5],
            "subscription_type": row[6] or "Нет",
            "has_subscription": bool(row[7]),
            "total_paid": row[8] or 0,
            "trial_used": bool(row[9]),
            "is_banned": bool(row[10]),
            "checked_channels": bool(row[11]),
            "referral_code": row[12] or "",
            "referred_by": row[13] or 0,
            "referral_count": row[14] or 0
        }

def get_all_users() -> List[Dict]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name, has_subscription, total_paid, is_banned, subscription_type, checked_channels FROM users ORDER BY user_id")
        rows = c.fetchall()
        return [{
            "user_id": r[0],
            "username": r[1] or "нет",
            "first_name": r[2] or "нет",
            "active": bool(r[3]),
            "total_paid": r[4] or 0,
            "is_banned": bool(r[5]),
            "subscription_type": r[6] or "Нет",
            "checked_channels": bool(r[7])
        } for r in rows]

def check_subscription(user_id: int) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT subscription_end, has_subscription, is_banned FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return False
        if row[2]:
            return False
        if row[1] and row[0]:
            try:
                end = datetime.fromisoformat(row[0])
                if datetime.now() < end:
                    return True
            except:
                pass
        return False

def get_subscription_type(user_id: int) -> str:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT subscription_type FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row[0] if row and row[0] else "Нет"

def get_remaining_days(user_id: int) -> int:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row and row[0]:
            try:
                end = datetime.fromisoformat(row[0])
                return max(0, (end - datetime.now()).days)
            except:
                pass
        return 0

def activate_beta_subscription(user_id: int) -> bool:
    if get_remaining_days(user_id) > 0:
        return False
    with get_db_connection() as conn:
        c = conn.cursor()
        end = datetime.now() + timedelta(days=FREE_TRIAL_DAYS)
        c.execute("""UPDATE users 
                     SET subscription_end = ?, 
                         has_subscription = 1, 
                         subscription_type = 'BETA',
                         trial_used = 1 
                     WHERE user_id = ?""",
                  (end.isoformat(), user_id))
        conn.commit()
        logger.info(f"🎁 Активирована BETA подписка для {user_id}")
        return True

def extend_subscription(user_id: int, days: int, amount: int) -> datetime:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        
        if row and row[0]:
            try:
                current = datetime.fromisoformat(row[0])
                if datetime.now() < current:
                    new_end = current + timedelta(days=days)
                else:
                    new_end = datetime.now() + timedelta(days=days)
            except:
                new_end = datetime.now() + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        
        if days >= 9999:
            sub_type = "НАВСЕГДА"
        elif days >= 365:
            sub_type = "VIP"
        elif days >= 90:
            sub_type = "PREMIUM"
        else:
            sub_type = "PREMIUM"
        
        c.execute("""UPDATE users 
                     SET subscription_end = ?, 
                         has_subscription = 1, 
                         subscription_type = ?,
                         total_paid = total_paid + ? 
                     WHERE user_id = ?""",
                  (new_end.isoformat(), sub_type, amount, user_id))
        conn.commit()
        logger.info(f"💳 Продлена подписка для {user_id} на {days} дней")
        return new_end

def ban_user(user_id: int) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True

def unban_user(user_id: int) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True

# ============================================================================
# РАБОТА С СЕССИЯМИ
# ============================================================================
def save_session(user_id: int, session_string: str) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO sessions 
                     (user_id, session_string, created_at, last_used, is_active) 
                     VALUES (?, ?, ?, ?, 1)""",
                  (user_id, session_string, get_timestamp(), get_timestamp()))
        conn.commit()
        return True

def get_session(user_id: int) -> Optional[str]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT session_string FROM sessions WHERE user_id = ? AND is_active = 1", (user_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE sessions SET last_used = ? WHERE user_id = ?", (get_timestamp(), user_id))
            conn.commit()
            return row[0]
        return None

def delete_session(user_id: int) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        return True

# ============================================================================
# РАБОТА С ГРУППАМИ
# ============================================================================
def add_group(user_id: int, group_id: int, group_username: str = "", group_title: str = "", group_type: str = "group") -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM groups WHERE user_id = ? AND is_active = 1", (user_id,))
        count = c.fetchone()[0]
        if count >= MAX_GROUPS_PER_USER:
            return False
        try:
            c.execute("""INSERT OR IGNORE INTO groups 
                         (user_id, group_id, group_username, group_title, group_type, added_at) 
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (user_id, group_id, group_username or "", group_title or group_username or str(group_id), group_type, get_timestamp()))
            conn.commit()
            return c.rowcount > 0
        except sqlite3.IntegrityError:
            return False

def get_user_groups(user_id: int) -> List[Dict]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""SELECT group_id, group_username, group_title, group_type, added_at 
                     FROM groups 
                     WHERE user_id = ? AND is_active = 1 AND group_type = 'group'
                     ORDER BY group_title""", (user_id,))
        rows = c.fetchall()
        return [{
            "id": r[0],
            "username": r[1] or "",
            "title": r[2] or f"Группа {r[0]}",
            "type": r[3] or "group",
            "added_at": r[4]
        } for r in rows]

def clear_user_groups(user_id: int) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM groups WHERE user_id = ?", (user_id,))
        conn.commit()
        return True

# ============================================================================
# РАБОТА С ИСТОРИЕЙ
# ============================================================================
def add_to_history(user_id: int, group_name: str, group_id: int, message: str, status: str = "sent", error: str = "") -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""INSERT INTO send_history 
                     (user_id, group_name, group_id, sent_at, message_text, status, error_message) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (user_id, group_name, group_id, get_timestamp(), truncate_text(message, 500), status, error[:500]))
        conn.commit()
        return True

def get_history(user_id: int, limit: int = 20) -> List[Tuple]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""SELECT group_name, sent_at, message_text, status, error_message
                     FROM send_history 
                     WHERE user_id = ? 
                     ORDER BY sent_at DESC 
                     LIMIT ?""", (user_id, limit))
        return c.fetchall()

# ============================================================================
# РАБОТА С ПЛАТЕЖАМИ
# ============================================================================
def save_payment(user_id: int, days: int, amount: int) -> int:
    with get_db_connection() as conn:
        c = conn.cursor()
        transaction_id = generate_id()
        c.execute("""INSERT INTO payments 
                     (user_id, amount, days, status, transaction_id, created_at) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (user_id, amount, days, "pending", transaction_id, get_timestamp()))
        conn.commit()
        return c.lastrowid

def get_pending_payments() -> List[Dict]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""SELECT id, user_id, amount, days, transaction_id, created_at 
                     FROM payments WHERE status = 'pending' ORDER BY created_at ASC""")
        rows = c.fetchall()
        return [{
            "id": r[0],
            "user_id": r[1],
            "amount": r[2],
            "days": r[3],
            "transaction_id": r[4],
            "created_at": r[5]
        } for r in rows]

def get_payment(payment_id: int) -> Optional[Dict]:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, user_id, amount, days, status FROM payments WHERE id = ?", (payment_id,))
        row = c.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "amount": row[2],
            "days": row[3],
            "status": row[4]
        }

def confirm_payment(payment_id: int, admin_id: int) -> bool:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, days, amount FROM payments WHERE id = ? AND status = 'pending'", (payment_id,))
        row = c.fetchone()
        if not row:
            return False
        user_id, days, amount = row
        c.execute("""UPDATE payments SET status = 'confirmed', confirmed_at = ?, confirmed_by = ? WHERE id = ?""",
                  (get_timestamp(), admin_id, payment_id))
        conn.commit()
        extend_subscription(user_id, days, amount)
        return True

# ============================================================================
# РАБОТА С ОБЯЗАТЕЛЬНЫМИ КАНАЛАМИ
# ============================================================================
def get_required_channels() -> List[str]:
    return safe_json_load(REQUIRED_CHANNELS_FILE, [])

def add_required_channel(channel: str) -> bool:
    channels = get_required_channels()
    if channel not in channels:
        channels.append(channel)
        return safe_json_save(REQUIRED_CHANNELS_FILE, channels)
    return False

def remove_required_channel(channel: str) -> bool:
    channels = get_required_channels()
    if channel in channels:
        channels.remove(channel)
        return safe_json_save(REQUIRED_CHANNELS_FILE, channels)
    return False

# ============================================================================
# РАБОТА СО СПОНСОРАМИ
# ============================================================================
def get_sponsors() -> List[str]:
    return safe_json_load(SPONSORS_FILE, [])

def add_sponsor(link: str) -> bool:
    sponsors = get_sponsors()
    if link not in sponsors:
        sponsors.append(link)
        return safe_json_save(SPONSORS_FILE, sponsors)
    return False

def remove_sponsor(link: str) -> bool:
    sponsors = get_sponsors()
    if link in sponsors:
        sponsors.remove(link)
        return safe_json_save(SPONSORS_FILE, sponsors)
    return False

# ============================================================================
# СТАТИСТИКА
# ============================================================================
def get_stats() -> Dict:
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE has_subscription = 1 AND is_banned = 0")
        active_users = c.fetchone()[0]
        c.execute("SELECT SUM(total_paid) FROM users")
        revenue = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM sessions WHERE is_active = 1")
        accounts = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM groups WHERE is_active = 1")
        groups = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        banned = c.fetchone()[0]
        return {
            "total_users": total_users,
            "active_users": active_users,
            "revenue": revenue,
            "accounts": accounts,
            "groups": groups,
            "pending": pending,
            "banned": banned
        }

# ============================================================================
# ОТПРАВКА СООБЩЕНИЙ
# ============================================================================
async def check_user_channels(user_id: int) -> Tuple[bool, List[str]]:
    required_channels = get_required_channels()
    if not required_channels:
        return True, []
    
    session = get_session(user_id)
    if not session:
        return False, ["Нет аккаунта для проверки подписки"]
    
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH)
        await client.connect()
        me = await client.get_me()
        not_subscribed = []
        
        for channel_username in required_channels:
            try:
                clean_username = channel_username.replace('@', '')
                entity = await client.get_entity(clean_username)
                try:
                    await client.get_participant(entity, me.id)
                except (UserNotParticipantError, UserBannedInChannelError):
                    not_subscribed.append(channel_username)
            except Exception:
                not_subscribed.append(channel_username)
        
        await client.disconnect()
        return len(not_subscribed) == 0, not_subscribed
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подписки: {e}")
        return False, ["Ошибка проверки подписки"]

async def send_message_to_groups(user_id: int, groups: List[Dict], text: str, image_data: Optional[bytes] = None, is_scheduled: bool = False) -> Dict:
    if not check_subscription(user_id):
        return {"success": 0, "fails": 0, "failed_groups": ["Подписка истекла"]}
    
    channels_ok, not_subscribed = await check_user_channels(user_id)
    if not channels_ok:
        return {"success": 0, "fails": 0, "failed_groups": [f"Подпишитесь на каналы: {', '.join(not_subscribed)}"]}
    
    session = get_session(user_id)
    if not session:
        return {"success": 0, "fails": 0, "failed_groups": ["Нет аккаунта"]}
    
    final_text = add_signature(text)
    success = 0
    fails = 0
    failed_groups = []
    
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH, connection_retries=3)
        await client.connect()
        
        for group in groups[:MAX_SEND_GROUPS]:
            try:
                group_id = int(group['id'])
                group_title = group.get('title') or group.get('username') or str(group_id)
                
                try:
                    entity = await client.get_entity(group_id)
                except:
                    dialogs = await client.get_dialogs()
                    entity = None
                    for dialog in dialogs:
                        if dialog.entity.id == group_id:
                            entity = dialog.entity
                            break
                
                if not entity:
                    raise Exception("Entity не найдено")
                
                if image_data:
                    await client.send_file(entity, image_data, caption=final_text)
                else:
                    await client.send_message(entity, final_text)
                
                success += 1
                if not is_scheduled:
                    add_to_history(user_id, group_title, group_id, text, "sent")
                logger.info(f"✅ Отправлено в {group_title}")
                await asyncio.sleep(RATE_LIMIT_DELAY)
                
            except FloodWaitError as e:
                wait_time = e.seconds + FLOOD_WAIT_BUFFER
                logger.warning(f"⏳ Flood wait {wait_time} сек для {group_title}")
                await asyncio.sleep(wait_time)
                fails += 1
                failed_groups.append(group_title)
                add_to_history(user_id, group_title, group_id, text, "error", f"FloodWait: {e.seconds} сек")
                
            except Exception as e:
                fails += 1
                failed_groups.append(group_title)
                error_msg = str(e)[:200]
                logger.error(f"❌ Ошибка в {group_title}: {error_msg}")
                add_to_history(user_id, group_title, group_id, text, "error", error_msg)
                await asyncio.sleep(0.5)
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return {"success": 0, "fails": 1, "failed_groups": [str(e)[:100]]}
    
    return {"success": success, "fails": fails, "failed_groups": failed_groups}

# ============================================================================
# МЕНЮ
# ============================================================================
def get_main_menu(user_id: int) -> List[List]:
    is_admin = user_id in ADMIN_IDS
    buttons = [
        [Button.inline("➕ Добавить аккаунт", b"add_account"), Button.inline("👤 Мои аккаунты", b"my_accounts")],
        [Button.inline("📋 Добавить все группы", b"add_all_groups"), Button.inline("👥 Мои группы", b"my_groups")],
        [Button.inline("📨 Рассылка", b"send_message"), Button.inline("📊 История", b"show_history")],
        [Button.inline("🛍️ Купить подписку", b"buy_subscription"), Button.inline("ℹ️ Инфо", b"info")]
    ]
    if is_admin:
        buttons.append([Button.inline("👑 Админ панель", b"admin_panel")])
    return buttons

def get_admin_menu() -> List[List]:
    return [
        [Button.inline("📊 Статистика", b"admin_stats"), Button.inline("👥 Пользователи", b"admin_users")],
        [Button.inline("💳 Платежи", b"admin_payments"), Button.inline("📢 Объявления", b"admin_broadcast")],
        [Button.inline("📋 Каналы", b"admin_channels"), Button.inline("🎯 Спонсоры", b"admin_sponsors")],
        [Button.inline("⚙️ Настройки", b"admin_settings"), Button.inline("📜 Логи", b"admin_logs")],
        [Button.inline("◀️ Назад", b"back_to_main")]
    ]

# ============================================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================================
@bot.on(events.NewMessage(pattern="/start"))
async def start_cmd(event):
    uid = event.sender_id
    user = await event.get_sender()
    
    is_new = register_user(uid, user.username, user.first_name, user.last_name or "")
    days = get_remaining_days(uid)
    sub_type = get_subscription_type(uid)
    required_channels = get_required_channels()
    
    if is_new:
        await event.respond(
            f"👋 Добро пожаловать!\n\n"
            f"🔧 Для начала работы добавьте аккаунт и группы!\n"
            f"📦 Подписка: {sub_type}\n"
            f"📅 Осталось: {days} дн.\n"
            f"📢 Обязательные каналы: {len(required_channels)}",
            buttons=get_main_menu(uid)
        )
    else:
        if check_subscription(uid):
            await event.respond(
                f"👋 Главное меню\n"
                f"📦 Подписка: {sub_type}\n"
                f"📅 Осталось: {days} дн.\n"
                f"📢 Обязательные каналы: {len(required_channels)}",
                buttons=get_main_menu(uid)
            )
        else:
            await event.respond(
                f"👋 Главное меню\n"
                f"📦 Подписка: {sub_type}\n"
                f"📅 Осталось: {days} дн.\n\n"
                f"💡 Для работы добавьте аккаунт и купите подписку!\n"
                f"📢 Обязательные каналы: {len(required_channels)}",
                buttons=get_main_menu(uid)
            )

@bot.on(events.NewMessage(pattern="/panel"))
async def panel_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ Доступ запрещен")
        return
    
    stats = get_stats()
    required_channels = get_required_channels()
    
    text = f"""👑 АДМИН ПАНЕЛЬ @{BOT_USERNAME}

📊 СТАТИСТИКА:
├ 👥 Всего: {format_number(stats['total_users'])}
├ 🟢 Активных: {format_number(stats['active_users'])}
├ ⛔ Заблокировано: {format_number(stats['banned'])}
├ 💰 Выручка: {format_number(stats['revenue'])} руб
├ 📱 Аккаунтов: {format_number(stats['accounts'])}
├ 👥 Групп: {format_number(stats['groups'])}
└ 💳 Ожидают: {format_number(stats['pending'])}

📢 Обязательные каналы ({len(required_channels)}):
{chr(10).join(required_channels) if required_channels else 'Не заданы'}

📋 Команды:
├ /users - список пользователей
├ /podpis ID дни - выдать подписку
├ /check ID - проверить пользователя
├ /ban ID - заблокировать
├ /unban ID - разблокировать
├ /sponsor @username - добавить спонсора
├ /removesponsor @username - удалить спонсора
├ /sponsors - список спонсоров
├ /broadcast_all текст - рассылка
├ /pending - платежи
├ /confirm ID - подтвердить
├ /addchannel @channel - добавить обязательный канал
├ /removechannel @channel - удалить обязательный канал
└ /channels - список обязательных каналов"""
    
    await event.respond(text, buttons=get_admin_menu())

# ============================================================================
# КОМАНДЫ АДМИНА
# ============================================================================
@bot.on(events.NewMessage(pattern="/addchannel @(\\w+)"))
async def add_channel_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ Доступ запрещен")
        return
    m = re.match(r"/addchannel (@\w+)", event.text)
    if m:
        channel = m.group(1)
        if add_required_channel(channel):
            await event.respond(f"✅ Канал {channel} добавлен в обязательные")
        else:
            await event.respond(f"⚠️ Канал {channel} уже есть в списке")

@bot.on(events.NewMessage(pattern="/removechannel @(\\w+)"))
async def remove_channel_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ Доступ запрещен")
        return
    m = re.match(r"/removechannel (@\w+)", event.text)
    if m:
        channel = m.group(1)
        if remove_required_channel(channel):
            await event.respond(f"✅ Канал {channel} удален из обязательных")
        else:
            await event.respond(f"⚠️ Канал {channel} не найден в списке")

@bot.on(events.NewMessage(pattern="/channels"))
async def list_channels_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ Доступ запрещен")
        return
    channels = get_required_channels()
    if not channels:
        await event.respond("📢 Обязательные каналы не заданы")
    else:
        await event.respond(f"📢 Обязательные каналы:\n" + "\n".join(channels))

@bot.on(events.NewMessage(pattern="/users"))
async def users_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    users = get_all_users()
    if not users:
        await event.respond("Нет пользователей")
        return
    text = "👥 ПОЛЬЗОВАТЕЛИ\n\n"
    for u in users[:20]:
        status = "🟢" if u["active"] else "🔴"
        if u["is_banned"]:
            status = "⛔"
        channels_checked = "✅" if u["checked_channels"] else "❌"
        text += f"{status} `{u['user_id']}` | @{u['username']} | {u['subscription_type']} | {channels_checked} | 💰{u['total_paid']} руб\n"
    await event.respond(text)

@bot.on(events.NewMessage(pattern="/podpis (\\d+) (\\d+)"))
async def give_sub_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/podpis (\d+) (\d+)", event.text)
    if m:
        uid = int(m.group(1))
        days = int(m.group(2))
        amount = days * PRICE_PER_DAY
        extend_subscription(uid, days, amount)
        await event.respond(f"✅ Подписка выдана!\n👤 {uid}\n📅 {days} дн.\n💳 {amount} руб")
        try:
            await bot.send_message(uid, f"✅ Вам выдана подписка на {days} дней!")
        except:
            pass

@bot.on(events.NewMessage(pattern="/check (\\d+)"))
async def check_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/check (\d+)", event.text)
    if m:
        uid = int(m.group(1))
        info = get_user(uid)
        if info:
            days = get_remaining_days(uid)
            status = "🟢 Активна" if check_subscription(uid) else "🔴 Неактивна"
            channels_checked = "✅" if info["checked_channels"] else "❌"
            await event.respond(f"📊 Пользователь {uid}\n👤 {info['first_name']}\n📦 {info['subscription_type']}\n📅 {status}\n💰 {info['total_paid']} руб\n📆 Осталось: {days} дн.\n📢 Каналы проверены: {channels_checked}")
        else:
            await event.respond(f"❌ Пользователь {uid} не найден")

@bot.on(events.NewMessage(pattern="/ban (\\d+)"))
async def ban_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/ban (\d+)", event.text)
    if m:
        ban_user(int(m.group(1)))
        await event.respond(f"✅ Пользователь заблокирован")

@bot.on(events.NewMessage(pattern="/unban (\\d+)"))
async def unban_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/unban (\d+)", event.text)
    if m:
        unban_user(int(m.group(1)))
        await event.respond(f"✅ Пользователь разблокирован")

@bot.on(events.NewMessage(pattern="/sponsor @(\\w+)"))
async def add_sponsor_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/sponsor (@\w+)", event.text)
    if m:
        link = m.group(1)
        if add_sponsor(link):
            await event.respond(f"✅ Спонсор {link} добавлен")
        else:
            await event.respond(f"⚠️ Уже есть")

@bot.on(events.NewMessage(pattern="/removesponsor @(\\w+)"))
async def remove_sponsor_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/removesponsor (@\w+)", event.text)
    if m:
        link = m.group(1)
        if remove_sponsor(link):
            await event.respond(f"✅ Спонсор {link} удален")
        else:
            await event.respond(f"⚠️ Не найден")

@bot.on(events.NewMessage(pattern="/sponsors"))
async def list_sponsors_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    s = get_sponsors()
    if not s:
        await event.respond("Нет спонсоров")
    else:
        await event.respond("📢 Спонсоры:\n" + "\n".join(s))

@bot.on(events.NewMessage(pattern="/pending"))
async def pending_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    payments = get_pending_payments()
    if not payments:
        await event.respond("Нет платежей")
        return
    text = "💳 Ожидают оплаты:\n\n"
    for p in payments:
        text += f"🆔 {p['user_id']} | 💰 {p['amount']} руб | 📅 {p['days']} дн.\n✅ /confirm {p['id']}\n\n"
    await event.respond(text)

@bot.on(events.NewMessage(pattern="/confirm (\\d+)"))
async def confirm_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/confirm (\d+)", event.text)
    if m:
        pid = int(m.group(1))
        payment = get_payment(pid)
        if payment and payment['status'] == 'pending':
            if confirm_payment(pid, event.sender_id):
                await event.respond(f"✅ Платеж подтвержден!\n👤 {payment['user_id']}\n📅 {payment['days']} дн.")
                try:
                    await bot.send_message(payment['user_id'], f"✅ Подписка активирована на {payment['days']} дней!")
                except:
                    pass
            else:
                await event.respond(f"❌ Ошибка подтверждения")
        else:
            await event.respond(f"❌ Платеж не найден")

@bot.on(events.NewMessage(pattern="/broadcast_all"))
async def broadcast_all_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    msg = event.text.replace("/broadcast_all", "").strip()
    if not msg:
        await event.respond("❌ Укажите текст: /broadcast_all текст")
        return
    users = get_all_users()
    sent = 0
    await event.respond(f"📢 Рассылка {len(users)} пользователям...")
    for u in users:
        if u.get("is_banned"):
            continue
        try:
            await bot.send_message(u['user_id'], f"📢 ОБЪЯВЛЕНИЕ\n\n{msg}\n\n🤖 @{BOT_USERNAME}")
            sent += 1
            await asyncio.sleep(0.3)
        except:
            pass
    await event.respond(f"✅ Отправлено: {sent} из {len(users)}")

# ============================================================================
# ОБРАБОТЧИКИ КНОПОК
# ============================================================================
@bot.on(events.CallbackQuery(data=b"admin_panel"))
async def admin_panel_cb(event):
    await panel_cmd(event)

@bot.on(events.CallbackQuery(data=b"admin_stats"))
async def admin_stats_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    stats = get_stats()
    text = f"""📊 СТАТИСТИКА

👥 Всего: {format_number(stats['total_users'])}
🟢 Активных: {format_number(stats['active_users'])}
⛔ Заблокировано: {format_number(stats['banned'])}
💰 Выручка: {format_number(stats['revenue'])} руб
📱 Аккаунтов: {format_number(stats['accounts'])}
👥 Групп: {format_number(stats['groups'])}
💳 Ожидают: {format_number(stats['pending'])}"""
    await event.respond(text, buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"admin_users"))
async def admin_users_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    users = get_all_users()
    if not users:
        await event.respond("Нет пользователей", buttons=get_admin_menu())
        return
    text = "👥 ПОЛЬЗОВАТЕЛИ\n\n"
    for u in users[:15]:
        status = "🟢" if u["active"] else "🔴"
        if u["is_banned"]:
            status = "⛔"
        text += f"{status} {u['user_id']} | @{u['username']} | {u['subscription_type']}\n"
    text += f"\n📊 Всего: {len(users)} пользователей"
    await event.respond(text, buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"admin_payments"))
async def admin_payments_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    payments = get_pending_payments()
    if not payments:
        await event.respond("💳 Нет ожидающих платежей", buttons=get_admin_menu())
        return
    text = "💳 ОЖИДАЮТ ОПЛАТЫ:\n\n"
    for p in payments[:10]:
        text += f"🆔 {p['user_id']} | 💰 {p['amount']} руб | 📅 {p['days']} дн.\n✅ /confirm {p['id']}\n\n"
    text += f"\n📊 Всего: {len(payments)} платежей"
    await event.respond(text, buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"admin_broadcast"))
async def admin_broadcast_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    await event.respond(
        "📢 РАССЫЛКА АДМИНА\n\n"
        "Отправьте сообщение для рассылки всем пользователям.",
        buttons=[[Button.inline("❌ Отмена", b"cancel_broadcast")]]
    )
    user_states[event.sender_id] = {"action": "admin_broadcast"}

@bot.on(events.CallbackQuery(data=b"cancel_broadcast"))
async def cancel_broadcast_cb(event):
    if event.sender_id in user_states:
        del user_states[event.sender_id]
    await event.respond("❌ Рассылка отменена", buttons=get_admin_menu())

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states.get(e.sender_id, {}).get("action") == "admin_broadcast"))
async def process_admin_broadcast(event):
    uid = event.sender_id
    if event.text:
        msg = event.text.strip()
        users = get_all_users()
        sent = 0
        await event.respond(f"📢 Рассылка {len(users)} пользователям...")
        for u in users:
            if u.get("is_banned"):
                continue
            try:
                await bot.send_message(u['user_id'], f"📢 ОБЪЯВЛЕНИЕ\n\n{msg}\n\n🤖 @{BOT_USERNAME}")
                sent += 1
                await asyncio.sleep(0.3)
            except:
                pass
        await event.respond(f"✅ Отправлено: {sent} из {len(users)}", buttons=get_admin_menu())
        if uid in user_states:
            del user_states[uid]

@bot.on(events.CallbackQuery(data=b"admin_channels"))
async def admin_channels_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    channels = get_required_channels()
    text = "📢 ОБЯЗАТЕЛЬНЫЕ КАНАЛЫ\n\n"
    if channels:
        text += "\n".join(channels)
        text += f"\n\n📊 Всего: {len(channels)} каналов"
    else:
        text += "Не заданы"
    await event.respond(text, buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"admin_sponsors"))
async def admin_sponsors_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    sponsors = get_sponsors()
    text = "🎯 СПОНСОРЫ\n\n"
    if sponsors:
        text += "\n".join(sponsors)
        text += f"\n\n📊 Всего: {len(sponsors)} спонсоров"
    else:
        text += "Нет спонсоров"
    await event.respond(text, buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"admin_settings"))
async def admin_settings_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    settings = safe_json_load(SETTINGS_FILE, {})
    text = f"""⚙️ НАСТРОЙКИ @{BOT_USERNAME}

Режим обслуживания: {'🟢 Вкл' if settings.get('maintenance_mode', False) else '🔴 Выкл'}
Рассылки: {'🟢 Вкл' if settings.get('broadcast_enabled', True) else '🔴 Выкл'}
Задержка: {settings.get('min_delay_between_sends', 2)} сек
Макс. групп: {settings.get('max_groups_per_send', 200)}
Защита от флуда: {'🟢 Вкл' if settings.get('flood_protection_enabled', True) else '🔴 Выкл'}"""
    await event.respond(text, buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"admin_logs"))
async def admin_logs_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_lines = lines[-20:] if len(lines) > 20 else lines
                text = "📜 ПОСЛЕДНИЕ ЛОГИ\n\n" + "".join(last_lines[-20:])
                if len(text) > 4000:
                    text = text[:4000] + "\n\n... (обрезано)"
                await event.respond(text, buttons=get_admin_menu())
        else:
            await event.respond("Лог-файл не найден", buttons=get_admin_menu())
    except Exception as e:
        await event.respond(f"❌ Ошибка: {e}", buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"back_to_main"))
async def back_to_main_cb(event):
    uid = event.sender_id
    days = get_remaining_days(uid)
    sub_type = get_subscription_type(uid)
    await event.respond(
        f"👋 Главное меню\n"
        f"📦 Подписка: {sub_type}\n"
        f"📅 Осталось: {days} дн.",
        buttons=get_main_menu(uid)
    )

@bot.on(events.CallbackQuery(data=b"buy_subscription"))
async def buy_sub_cb(event):
    uid = event.sender_id
    channels_ok, not_subscribed = await check_user_channels(uid)
    if not channels_ok:
        await event.respond(
            f"❌ Для покупки подписки необходимо подписаться на каналы:\n{chr(10).join(not_subscribed)}",
            buttons=get_main_menu(uid)
        )
        return
    
    await event.respond(
        f"💰 ПОКУПКА ПОДПИСКИ @{BOT_USERNAME}\n\n💵 {PRICE_PER_DAY} руб/день\n\nВыберите срок:",
        buttons=[
            [Button.inline("7 дней", b"sub_7"), Button.inline("30 дней", b"sub_30")],
            [Button.inline("90 дней", b"sub_90"), Button.inline("180 дней", b"sub_180")],
            [Button.inline("365 дней", b"sub_365"), Button.inline("🔥 Навсегда", b"sub_forever")],
            [Button.inline("✏️ Свой срок", b"sub_custom")]
        ]
    )

@bot.on(events.CallbackQuery(func=lambda e: e.data.startswith(b"sub_")))
async def subscription_choice_cb(event):
    uid = event.sender_id
    action = event.data.decode()
    
    channels_ok, not_subscribed = await check_user_channels(uid)
    if not channels_ok:
        await event.respond(
            f"❌ Для покупки подписки необходимо подписаться на каналы:\n{chr(10).join(not_subscribed)}",
            buttons=get_main_menu(uid)
        )
        return
    
    if action == "sub_custom":
        await event.respond("✏️ Введите количество дней (от 3 до 365):")
        user_states[uid] = {"action": "custom_days"}
        return
    
    days_map = {"sub_7": 7, "sub_30": 30, "sub_90": 90, "sub_180": 180, "sub_365": 365, "sub_forever": 9999}
    days = days_map.get(action, 0)
    if days == 0:
        await event.answer("❌ Ошибка", alert=True)
        return
    
    if days == 9999:
        amount = 99999
        days_text = "🔥 НАВСЕГДА"
    else:
        amount = days * PRICE_PER_DAY
        days_text = f"{days} дней"
    
    payment_id = save_payment(uid, days, amount)
    await event.respond(
        f"💳 ОПЛАТА @{BOT_USERNAME}\n\n📅 {days_text} = {amount} руб\n\n💳 Карта: `{CARD_NUMBER}`\n\n✅ После перевода нажмите кнопку\n🆔 Ваш ID: `{uid}`",
        buttons=[[Button.inline("✅ Я перевел", f"pay_{payment_id}")]]
    )

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states.get(e.sender_id, {}).get("action") == "custom_days"))
async def process_custom_days(event):
    uid = event.sender_id
    try:
        days = int(event.text.strip())
        if days < 3 or days > 365:
            await event.respond("❌ От 3 до 365 дней!")
            return
        amount = days * PRICE_PER_DAY
        payment_id = save_payment(uid, days, amount)
        await event.respond(
            f"💳 ОПЛАТА @{BOT_USERNAME}\n\n📅 {days} дней = {amount} руб\n\n💳 Карта: `{CARD_NUMBER}`\n\n✅ После перевода нажмите кнопку\n🆔 Ваш ID: `{uid}`",
            buttons=[[Button.inline("✅ Я перевел", f"pay_{payment_id}")]]
        )
        if uid in user_states:
            del user_states[uid]
    except ValueError:
        await event.respond("❌ Введите число!")

@bot.on(events.CallbackQuery(func=lambda e: e.data.startswith(b"pay_")))
async def payment_cb(event):
    payment_id = int(event.data.decode().split("_")[1])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"💰 Платеж!\n👤 {event.sender_id}\n✅ /confirm {payment_id}")
        except:
            pass
    await event.respond("✅ Заявка отправлена! Ожидайте подтверждения.", buttons=get_main_menu(event.sender_id))

@bot.on(events.CallbackQuery(data=b"info"))
async def info_cb(event):
    uid = event.sender_id
    days = get_remaining_days(uid)
    sub_type = get_subscription_type(uid)
    status = "🟢 Активна" if check_subscription(uid) else "🔴 Неактивна"
    required_channels = get_required_channels()
    channels_ok, not_subscribed = await check_user_channels(uid)
    channels_status = "✅ Подписан" if channels_ok else f"❌ Не подписан на: {', '.join(not_subscribed)}"
    
    await event.respond(
        f"ℹ️ ИНФОРМАЦИЯ @{BOT_USERNAME}\n\n"
        f"🤖 Бот: @{BOT_USERNAME}\n"
        f"📌 Версия: {VERSION}\n\n"
        f"📦 Подписка: {sub_type}\n"
        f"📅 Статус: {status}\n"
        f"📆 Осталось: {days} дн.\n"
        f"💰 Цена: {PRICE_PER_DAY} руб/день\n\n"
        f"📢 Обязательные каналы: {len(required_channels)}\n"
        f"📌 {channels_status}\n\n"
        f"📢 Подпись:\n`{SIGNATURE.strip()}`\n\n"
        f"💬 Поддержка: @sikvvg",
        buttons=get_main_menu(uid)
    )

@bot.on(events.CallbackQuery(data=b"show_history"))
async def history_cb(event):
    history = get_history(event.sender_id, 15)
    if not history:
        await event.respond("📭 История пуста", buttons=get_main_menu(event.sender_id))
        return
    text = "📜 ИСТОРИЯ РАССЫЛОК @{BOT_USERNAME}\n\n"
    for h in history:
        status_icon = "✅" if h[3] == "sent" else "❌"
        text += f"{status_icon} {h[0]}\n🕐 {h[1][:16]}\n💬 {truncate_text(h[2], 50)}\n"
        if h[4]:
            text += f"⚠️ {truncate_text(h[4], 50)}\n"
        text += "\n"
    await event.respond(text, buttons=get_main_menu(event.sender_id))

@bot.on(events.CallbackQuery(data=b"my_groups"))
async def my_groups_cb(event):
    groups = get_user_groups(event.sender_id)
    if not groups:
        await event.respond("❌ Нет добавленных групп!\n\nНажмите '📋 Добавить все группы'", buttons=get_main_menu(event.sender_id))
        return
    text = "👥 МОИ ГРУППЫ @{BOT_USERNAME}\n\n"
    for g in groups[:20]:
        text += f"📌 {g['title']}\n🆔 {g['id']}\n\n"
    await event.respond(text, buttons=get_main_menu(event.sender_id))

@bot.on(events.CallbackQuery(data=b"add_account"))
async def add_account_cb(event):
    await event.respond(
        "📱 Для добавления аккаунта, отправьте номер телефона:",
        buttons=[[Button.request_phone("📱 Отправить номер", resize=True)]]
    )
    phone_waiting[event.sender_id] = True

@bot.on(events.NewMessage(func=lambda e: e.sender_id in phone_waiting and e.contact))
async def process_phone_contact(event):
    uid = event.sender_id
    if not event.contact:
        await event.respond("❌ Используйте кнопку 'Отправить номер'")
        return
    phone = event.contact.phone_number
    if not phone:
        await event.respond("❌ Не удалось получить номер")
        return
    if not phone.startswith("+"):
        phone = "+" + phone
    
    client = TelegramClient(StringSession(), API_ID, API_HASH, connection_retries=5)
    user_clients[uid] = client
    user_phones[uid] = phone
    
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            session_str = client.session.save()
            save_session(uid, session_str)
            await event.respond(f"✅ Аккаунт @{me.username or me.first_name} добавлен!\n🎁 Вам начислена подписка BETA на {FREE_TRIAL_DAYS} дня!")
            if not check_subscription(uid):
                activate_beta_subscription(uid)
            await event.respond("👋 Главное меню:", buttons=get_main_menu(uid))
            cleanup_phone_session(uid)
            return
        
        await client.send_code_request(phone)
        code_waiting[uid] = phone
        if uid in phone_waiting:
            del phone_waiting[uid]
        
        await event.respond(
            f"✅ Код отправлен на номер {phone[-4:]}!\n\n📱 Введите код:",
            buttons=[
                [Button.inline("1️⃣", b"code_1"), Button.inline("2️⃣", b"code_2"), Button.inline("3️⃣", b"code_3")],
                [Button.inline("4️⃣", b"code_4"), Button.inline("5️⃣", b"code_5"), Button.inline("6️⃣", b"code_6")],
                [Button.inline("7️⃣", b"code_7"), Button.inline("8️⃣", b"code_8"), Button.inline("9️⃣", b"code_9")],
                [Button.inline("⌫ Удалить", b"code_backspace"), Button.inline("0️⃣", b"code_0"), Button.inline("✅ Готово", b"code_done")],
                [Button.inline("🔄 Запросить код снова", b"code_resend")]
            ]
        )
    except PhoneNumberInvalidError:
        await event.respond("❌ Неверный номер!")
        cleanup_phone_session(uid)
    except PhoneNumberFloodError:
        await event.respond("⚠️ Слишком много попыток! Подождите 5-10 минут.")
        cleanup_phone_session(uid)
    except FloodWaitError as e:
        await event.respond(f"⚠️ Подождите {e.seconds // 60} минут")
        cleanup_phone_session(uid)
    except Exception as e:
        await event.respond(f"❌ Ошибка: {str(e)[:200]}")
        cleanup_phone_session(uid)

def cleanup_phone_session(uid: int):
    for key in [phone_waiting, user_clients, user_phones, code_waiting]:
        if uid in key:
            del key[uid]

@bot.on(events.CallbackQuery(func=lambda e: e.data.startswith(b"code_")))
async def code_calculator_cb(event):
    uid = event.sender_id
    action = event.data.decode()
    
    if action == "code_resend":
        if uid not in user_phones:
            await event.answer("❌ Номер не найден", alert=True)
            return
        phone = user_phones[uid]
        if uid in user_clients:
            try:
                await user_clients[uid].disconnect()
            except:
                pass
            del user_clients[uid]
        client = TelegramClient(StringSession(), API_ID, API_HASH, connection_retries=5)
        await client.connect()
        user_clients[uid] = client
        try:
            await client.send_code_request(phone)
            code_waiting[uid] = phone
            user_temp_codes[uid] = ""
            await event.edit(
                f"✅ Код отправлен заново!\n\n📱 Введите код:",
                buttons=[
                    [Button.inline("1️⃣", b"code_1"), Button.inline("2️⃣", b"code_2"), Button.inline("3️⃣", b"code_3")],
                    [Button.inline("4️⃣", b"code_4"), Button.inline("5️⃣", b"code_5"), Button.inline("6️⃣", b"code_6")],
                    [Button.inline("7️⃣", b"code_7"), Button.inline("8️⃣", b"code_8"), Button.inline("9️⃣", b"code_9")],
                    [Button.inline("⌫ Удалить", b"code_backspace"), Button.inline("0️⃣", b"code_0"), Button.inline("✅ Готово", b"code_done")],
                    [Button.inline("🔄 Запросить код снова", b"code_resend")]
                ]
            )
            await event.answer("✅ Код отправлен!")
        except Exception as e:
            await event.answer(f"❌ Ошибка: {str(e)[:50]}", alert=True)
        return
    
    if uid not in user_temp_codes:
        user_temp_codes[uid] = ""
    
    if action == "code_backspace":
        user_temp_codes[uid] = user_temp_codes[uid][:-1]
    elif action == "code_done":
        code = user_temp_codes[uid]
        if len(code) < 5:
            await event.answer("❌ Минимум 5 цифр!", alert=True)
            return
        if uid not in code_waiting:
            await event.answer("❌ Сессия истекла", alert=True)
            return
        phone = code_waiting[uid]
        client = user_clients.get(uid)
        if not client:
            await event.answer("❌ Ошибка сессии", alert=True)
            return
        try:
            await client.sign_in(phone, code)
            session_str = client.session.save()
            save_session(uid, session_str)
            me = await client.get_me()
            await event.respond(f"✅ Аккаунт @{me.username or me.first_name} добавлен!\n🎁 Вам начислена подписка BETA на {FREE_TRIAL_DAYS} дня!")
            if not check_subscription(uid):
                activate_beta_subscription(uid)
            await event.respond("👋 Главное меню:", buttons=get_main_menu(uid))
            for key in [code_waiting, user_clients, user_temp_codes, user_phones]:
                if uid in key:
                    del key[uid]
            await event.answer()
            return
        except SessionPasswordNeededError:
            password_waiting[uid] = {"client": client, "phone": phone}
            await event.respond("🔐 Введите пароль 2FA (введите текстом):")
            if uid in user_temp_codes:
                del user_temp_codes[uid]
            await event.answer()
            return
        except PhoneCodeInvalidError:
            await event.respond("❌ Неверный код. Попробуйте снова:")
            user_temp_codes[uid] = ""
            await event.answer()
            return
        except Exception as e:
            error_msg = str(e)
            if "phone code invalid" in error_msg.lower():
                await event.respond("❌ Неверный код. Попробуйте снова:")
                user_temp_codes[uid] = ""
            else:
                await event.respond(f"❌ Ошибка: {error_msg[:200]}")
                if uid in user_temp_codes:
                    del user_temp_codes[uid]
            await event.answer()
            return
    else:
        digit = action.split("_")[1]
        if len(user_temp_codes[uid]) < 10:
            user_temp_codes[uid] += digit
    
    current_code = user_temp_codes[uid]
    display_code = current_code if current_code else "____"
    await event.answer(f"Код: {display_code}", alert=False)
    try:
        await event.edit(
            f"✅ Введите код:\n\n📱 Код: `{display_code}`",
            buttons=[
                [Button.inline("1️⃣", b"code_1"), Button.inline("2️⃣", b"code_2"), Button.inline("3️⃣", b"code_3")],
                [Button.inline("4️⃣", b"code_4"), Button.inline("5️⃣", b"code_5"), Button.inline("6️⃣", b"code_6")],
                [Button.inline("7️⃣", b"code_7"), Button.inline("8️⃣", b"code_8"), Button.inline("9️⃣", b"code_9")],
                [Button.inline("⌫ Удалить", b"code_backspace"), Button.inline("0️⃣", b"code_0"), Button.inline("✅ Готово", b"code_done")],
                [Button.inline("🔄 Запросить код снова", b"code_resend")]
            ]
        )
    except:
        pass

@bot.on(events.NewMessage(func=lambda e: e.sender_id in password_waiting))
async def process_password(event):
    uid = event.sender_id
    pwd = event.text.strip()
    data = password_waiting[uid]
    client = data["client"]
    try:
        await client.sign_in(password=pwd)
        session_str = client.session.save()
        save_session(uid, session_str)
        me = await client.get_me()
        await event.respond(f"✅ Аккаунт @{me.username or me.first_name} добавлен!\n🎁 Вам начислена подписка BETA на {FREE_TRIAL_DAYS} дня!")
        if not check_subscription(uid):
            activate_beta_subscription(uid)
        await event.respond("👋 Главное меню:", buttons=get_main_menu(uid))
        del password_waiting[uid]
        if uid in user_clients:
            del user_clients[uid]
        if uid in user_phones:
            del user_phones[uid]
    except Exception as e:
        await event.respond(f"❌ Ошибка: {str(e)[:200]}")

@bot.on(events.CallbackQuery(data=b"my_accounts"))
async def my_accounts_cb(event):
    session = get_session(event.sender_id)
    if not session:
        await event.respond("❌ Нет аккаунтов", buttons=get_main_menu(event.sender_id))
        return
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH)
        await client.connect()
        me = await client.get_me()
        await client.disconnect()
        await event.respond(
            f"📱 ВАШ АККАУНТ @{BOT_USERNAME}\n\n"
            f"👤 {me.first_name}\n"
            f"📝 @{me.username or 'нет'}\n"
            f"🆔 {me.id}",
            buttons=[[Button.inline("❌ Удалить", b"delete_account"), Button.inline("◀️ Назад", b"back_to_main")]]
        )
    except:
        await event.respond("❌ Ошибка загрузки", buttons=[[Button.inline("❌ Удалить", b"delete_account")]])

@bot.on(events.CallbackQuery(data=b"delete_account"))
async def delete_account_cb(event):
    delete_session(event.sender_id)
    clear_user_groups(event.sender_id)
    await event.respond("✅ Аккаунт и группы удалены", buttons=get_main_menu(event.sender_id))

@bot.on(events.CallbackQuery(data=b"add_all_groups"))
async def add_all_groups_cb(event):
    uid = event.sender_id
    if not check_subscription(uid):
        await event.respond("❌ Подписка истекла! Купите подписку.")
        return
    channels_ok, not_subscribed = await check_user_channels(uid)
    if not channels_ok:
        await event.respond(f"❌ Подпишитесь на каналы:\n{chr(10).join(not_subscribed)}", buttons=get_main_menu(uid))
        return
    session = get_session(uid)
    if not session:
        await event.respond("❌ Сначала добавьте аккаунт!", buttons=get_main_menu(uid))
        return
    await event.respond("🔄 Загрузка групп...")
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH)
        await client.connect()
        clear_user_groups(uid)
        dialogs = await client.get_dialogs()
        groups_found = 0
        group_names = []
        for dialog in dialogs:
            if dialog.is_group:
                group_id = dialog.entity.id
                group_name = dialog.name or "Без имени"
                add_group(uid, group_id, group_name, group_name, "group")
                groups_found += 1
                group_names.append(group_name)
        await client.disconnect()
        text = f"✅ Добавлены все группы!\n\n📋 Групп: {groups_found}"
        if group_names:
            preview = "\n".join(group_names[:10])
            if len(group_names) > 10:
                preview += f"\n... и еще {len(group_names) - 10} групп"
            text += f"\n\n📌 Найденные группы:\n{preview}"
        await event.respond(text, buttons=get_main_menu(uid))
    except Exception as e:
        await event.respond(f"❌ Ошибка: {str(e)[:200]}", buttons=get_main_menu(uid))

@bot.on(events.CallbackQuery(data=b"send_message"))
async def send_message_cb(event):
    uid = event.sender_id
    if not check_subscription(uid):
        await event.respond("❌ Подписка истекла! Купите подписку.")
        return
    channels_ok, not_subscribed = await check_user_channels(uid)
    if not channels_ok:
        await event.respond(f"❌ Подпишитесь на каналы:\n{chr(10).join(not_subscribed)}", buttons=get_main_menu(uid))
        return
    groups = get_user_groups(uid)
    if not groups:
        await event.respond("❌ Нет добавленных групп!", buttons=get_main_menu(uid))
        return
    buttons = []
    for group in groups[:20]:
        title = group['title'] or group['username'] or f"Группа {group['id']}"
        if len(title) > 30:
            title = title[:27] + "..."
        buttons.append([Button.inline(f"📌 {title}", f"select_group_{group['id']}")])
    buttons.append([Button.inline("✅ Отправить во все", b"send_all_groups")])
    buttons.append([Button.inline("❌ Отмена", b"cancel_select")])
    await event.respond(
        f"📨 ВЫБЕРИТЕ ГРУППЫ @{BOT_USERNAME}\n\n👥 Всего групп: {len(groups)}",
        buttons=buttons
    )
    user_states[uid] = {"action": "selecting_groups", "selected": []}

@bot.on(events.CallbackQuery(func=lambda e: e.data.startswith(b"select_group_")))
async def select_group_cb(event):
    uid = event.sender_id
    group_id = int(event.data.decode().split("_")[2])
    if uid not in user_states or user_states[uid].get("action") != "selecting_groups":
        await event.answer("❌ Сессия истекла", alert=True)
        return
    selected = user_states[uid].get("selected", [])
    if group_id in selected:
        selected.remove(group_id)
        await event.answer("❌ Удалено")
    else:
        selected.append(group_id)
        await event.answer("✅ Добавлено")
    user_states[uid]["selected"] = selected

@bot.on(events.CallbackQuery(data=b"send_all_groups"))
async def send_all_groups_cb(event):
    uid = event.sender_id
    if uid not in user_states:
        await event.answer("❌ Сессия истекла", alert=True)
        return
    selected = user_states[uid].get("selected", [])
    all_groups = get_user_groups(uid)
    if not selected:
        groups_to_send = all_groups
    else:
        groups_to_send = [g for g in all_groups if g['id'] in selected]
    if not groups_to_send:
        await event.respond("❌ Нет выбранных групп!", buttons=get_main_menu(uid))
        if uid in user_states:
            del user_states[uid]
        return
    user_states[uid] = {"action": "waiting_for_content", "groups": groups_to_send}
    await event.respond(
        f"📨 ОТПРАВКА СООБЩЕНИЯ @{BOT_USERNAME}\n\n"
        f"👥 Выбрано групп: {len(groups_to_send)}\n\n"
        f"📝 Отправьте текст или изображение",
        buttons=[[Button.inline("❌ Отмена", b"cancel_send")]]
    )

@bot.on(events.CallbackQuery(data=b"cancel_select"))
async def cancel_select_cb(event):
    if event.sender_id in user_states:
        del user_states[event.sender_id]
    await event.respond("❌ Отменено", buttons=get_main_menu(event.sender_id))

@bot.on(events.CallbackQuery(data=b"cancel_send"))
async def cancel_send_cb(event):
    if event.sender_id in user_states:
        del user_states[event.sender_id]
    await event.respond("❌ Отменено", buttons=get_main_menu(event.sender_id))

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states.get(e.sender_id, {}).get("action") == "waiting_for_content"))
async def process_send_content(event):
    uid = event.sender_id
    groups = user_states[uid].get("groups", [])
    if not groups:
        await event.respond("❌ Нет групп!")
        if uid in user_states:
            del user_states[uid]
        return
    image_data = None
    text = ""
    if event.photo:
        try:
            file = await event.download_media(file=bytes)
            image_data = file
            text = event.caption or ""
            await event.respond("✅ Изображение получено!")
        except Exception as e:
            await event.respond(f"❌ Ошибка: {str(e)[:100]}")
            return
    elif event.text:
        text = event.text.strip()
        if not text:
            await event.respond("❌ Сообщение не может быть пустым!")
            return
        await event.respond(f"✅ Текст получен!")
    else:
        await event.respond("❌ Отправьте текст или изображение!")
        return
    
    user_states[uid] = {"action": "choose_repeat", "groups": groups, "message": text, "image": image_data}
    await event.respond(
        f"📨 ГОТОВО К ОТПРАВКЕ @{BOT_USERNAME}\n\n"
        f"📢 Текст:\n{truncate_text(text, 200)}\n"
        f"🖼️ Изображение: {'✅' if image_data else '❌'}\n"
        f"👥 Групп: {len(groups)}\n\n"
        f"🔄 Выберите интервал:",
        buttons=[
            [Button.inline("⏰ Без повтора", b"repeat_0")],
            [Button.inline("🔄 Каждый час", b"repeat_1")],
            [Button.inline("🔄 Каждые 3 часа", b"repeat_3")],
            [Button.inline("🔄 Каждые 6 часов", b"repeat_6")],
            [Button.inline("🔄 Каждые 12 часов", b"repeat_12")],
            [Button.inline("🔄 Каждые 24 часа", b"repeat_24")],
            [Button.inline("❌ Отмена", b"cancel_repeat")]
        ]
    )

@bot.on(events.CallbackQuery(func=lambda e: e.data.startswith(b"repeat_")))
async def repeat_choice_cb(event):
    uid = event.sender_id
    action = event.data.decode()
    if uid not in user_states or user_states[uid].get("action") != "choose_repeat":
        await event.answer("❌ Сессия истекла", alert=True)
        return
    if action == "cancel_repeat":
        if uid in user_states:
            del user_states[uid]
        await event.respond("❌ Отменено", buttons=get_main_menu(uid))
        return
    hours = int(action.split("_")[1])
    groups = user_states[uid].get("groups", [])
    text = user_states[uid].get("message", "")
    image_data = user_states[uid].get("image", None)
    if uid in user_states:
        del user_states[uid]
    await event.respond(f"🔄 Отправка в {len(groups)} групп...")
    result = await send_message_to_groups(uid, groups, text, image_data, is_scheduled=False)
    result_text = f"✅ РАССЫЛКА ЗАВЕРШЕНА @{BOT_USERNAME}!\n\n"
    result_text += f"✅ Успешно: {result['success']}\n"
    result_text += f"❌ Ошибок: {result['fails']}\n"
    result_text += f"👥 Групп: {len(groups)}"
    if result['failed_groups']:
        result_text += f"\n\n❌ Ошибки в:\n" + "\n".join(result['failed_groups'][:10])
    if hours > 0:
        result_text += f"\n\n🔄 Повтор каждые {hours} часов"
        async def scheduled_send():
            if check_subscription(uid):
                result = await send_message_to_groups(uid, groups, text, image_data, is_scheduled=True)
                try:
                    await bot.send_message(uid, f"🔄 ЗАПЛАНИРОВАННАЯ РАССЫЛКА @{BOT_USERNAME}\n✅ Успешно: {result['success']}\n❌ Ошибок: {result['fails']}")
                except:
                    pass
        job_id = f"{uid}_{int(time.time())}"
        scheduler.add_job(scheduled_send, 'interval', hours=hours, id=job_id, replace_existing=True)
        scheduled_jobs[job_id] = {"user_id": uid, "job_id": job_id, "hours": hours}
        result_text += f"\n\n🔔 /cancel_repeat - отменить"
    await event.respond(result_text, buttons=get_main_menu(uid))

@bot.on(events.NewMessage(pattern="/cancel_repeat"))
async def cancel_repeat_cmd(event):
    uid = event.sender_id
    canceled = 0
    for job_id, job_info in list(scheduled_jobs.items()):
        if job_info.get("user_id") == uid:
            try:
                scheduler.remove_job(job_id)
                del scheduled_jobs[job_id]
                canceled += 1
            except:
                pass
    if canceled > 0:
        await event.respond(f"✅ Отменено {canceled} рассылок", buttons=get_main_menu(uid))
    else:
        await event.respond("❌ Нет активных рассылок", buttons=get_main_menu(uid))

# ============================================================================
# ЗАПУСК ПЛАНИРОВЩИКА
# ============================================================================
async def start_scheduler():
    scheduler.start()
    logger.info("✅ Планировщик запущен")

# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================
async def main():
    print("=" * 60)
    print(f"🚀 ЗАПУСК БОТА @{BOT_USERNAME}")
    print("=" * 60)
    
    init_database()
    init_sponsors()
    init_required_channels()
    init_settings()
    
    logger.add(LOG_FILE, rotation="10 MB", retention="7 days", encoding="utf-8")
    logger.info(f"🚀 Запуск бота {BOT_USERNAME} v{VERSION}")
    
    try:
        await bot.start(bot_token=BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ Бот @{me.username} запущен!")
        print(f"👑 Админы: {ADMIN_IDS}")
        print(f"📌 Версия: {VERSION}")
        print("=" * 60)
        
        await start_scheduler()
        print("📱 БОТ РАБОТАЕТ!")
        print("=" * 60)
        print(f"🔗 Ссылка: https://t.me/{BOT_USERNAME}")
        print("=" * 60)
        
        await bot.run_until_disconnected()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Бот остановлен")
        logger.info("⏹️ Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
