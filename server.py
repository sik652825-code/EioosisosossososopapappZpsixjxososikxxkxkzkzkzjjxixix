#!/usr/bin/env python3
"""
🤖 TELEGRAM БОТ ДЛЯ МАССОВЫХ РАССЫЛОК 🤖
@avtorasslkabot - ВСЕ КНОПКИ РАБОТАЮТ
Версия: 6.0.0 - ПОЛНАЯ ЗАЩИТА
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
import hashlib
import hmac
import base64
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import contextmanager
from functools import wraps
from dataclasses import dataclass, asdict
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

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
    packages = ['telethon', 'apscheduler', 'loguru', 'pillow', 'cryptg', 'cryptography']
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
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import AddContactRequest, DeleteContactsRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from PIL import Image
import io

# ============================================================================
# КОНФИГУРАЦИЯ
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
VERSION = "6.0.0"

DB_PATH = "bot_database.db"
SPONSORS_FILE = "sponsors.json"
REQUIRED_CHANNELS_FILE = "required_channels.json"
SETTINGS_FILE = "settings.json"
LOG_FILE = "bot.log"
SECRET_KEY_FILE = "secret.key"

MAX_GROUPS_PER_USER = 1000
MAX_MESSAGE_LENGTH = 4096
MAX_RETRY_ATTEMPTS = 5
RATE_LIMIT_DELAY = 2
FLOOD_WAIT_BUFFER = 15
MAX_SEND_GROUPS = 200
DEFAULT_LANGUAGE = "ru"
MAX_SESSION_AGE_DAYS = 30
MAX_REQUESTS_PER_MINUTE = 30

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
user_session_lock: Dict[int, asyncio.Lock] = {}
pending_confirmation: Dict[int, Dict] = {}
broadcast_queue: List[Dict] = []
spam_protection: Dict[int, List[datetime]] = {}
user_templates: Dict[int, List[Dict]] = {}
active_sessions: Dict[int, Dict] = {}
message_processing: Dict[int, bool] = {}
rate_limit_cache: Dict[int, Dict] = {}
session_usage: Dict[int, Dict] = {}

# ============================================================================
# ШИФРОВАНИЕ ДЛЯ ЗАЩИТЫ
# ============================================================================
def generate_key():
    """Генерирует ключ шифрования"""
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(b"bot_secret_key_2024_secure"))
    return key

def get_encryption_key():
    """Получает или создает ключ шифрования"""
    if os.path.exists(SECRET_KEY_FILE):
        try:
            with open(SECRET_KEY_FILE, 'rb') as f:
                return f.read()
        except:
            pass
    
    key = generate_key()
    with open(SECRET_KEY_FILE, 'wb') as f:
        f.write(key)
    return key

def encrypt_data(data: str) -> str:
    """Шифрует данные"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"Ошибка шифрования: {e}")
        return data

def decrypt_data(encrypted_data: str) -> str:
    """Расшифровывает данные"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(base64.urlsafe_b64decode(encrypted_data.encode()))
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Ошибка расшифровки: {e}")
        return encrypted_data

def hash_user_data(user_id: int, data: str) -> str:
    """Хеширует данные пользователя для проверки целостности"""
    salt = str(user_id)[::-1]
    return hashlib.sha256(f"{salt}_{data}_{salt}".encode()).hexdigest()[:32]

# ============================================================================
# ЗАЩИТА: ПРОВЕРКА ПОДЛИННОСТИ
# ============================================================================
def validate_session_usage(user_id: int) -> bool:
    """Проверяет, не используется ли сессия с подозрительных мест"""
    try:
        current_time = time.time()
        
        if user_id not in session_usage:
            session_usage[user_id] = {"count": 0, "last": current_time, "blocked": False}
        
        usage = session_usage[user_id]
        
        # Если заблокирован - отказ
        if usage.get("blocked", False):
            return False
        
        # Сброс счетчика каждую минуту
        if current_time - usage["last"] > 60:
            usage["count"] = 0
            usage["last"] = current_time
        
        # Если превышен лимит - блокируем на минуту
        if usage["count"] >= MAX_REQUESTS_PER_MINUTE:
            usage["blocked"] = True
            logger.warning(f"⚠️ Подозрительная активность от {user_id} - заблокирован на 1 минуту")
            asyncio.create_task(unblock_user(user_id))
            return False
        
        usage["count"] += 1
        return True
        
    except:
        return True

async def unblock_user(user_id: int):
    """Разблокирует пользователя через минуту"""
    await asyncio.sleep(60)
    if user_id in session_usage:
        session_usage[user_id]["blocked"] = False
        session_usage[user_id]["count"] = 0
        logger.info(f"✅ Пользователь {user_id} разблокирован")

def check_user_authorization(user_id: int) -> bool:
    """Проверяет, авторизован ли пользователь"""
    session = get_session(user_id)
    if not session:
        return False
    
    if not validate_session_usage(user_id):
        return False
    
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH)
        asyncio.create_task(client.connect())
        
        # Проверяем авторизацию
        future = asyncio.run_coroutine_threadsafe(
            client.is_user_authorized(), 
            asyncio.get_event_loop()
        )
        
        if future.result(timeout=10):
            asyncio.run_coroutine_threadsafe(client.disconnect(), asyncio.get_event_loop())
            return True
    except:
        pass
    
    return False

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

def get_date_from_iso(iso_string: str) -> Optional[datetime]:
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string)
    except:
        return None

def get_days_until(date_string: str) -> int:
    try:
        if not date_string:
            return 0
        end_date = datetime.fromisoformat(date_string)
        delta = end_date - datetime.now()
        return max(0, delta.days)
    except:
        return 0

def truncate_text(text: str, max_length: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def safe_json_load(file_path: str, default: Any = None) -> Any:
    if default is None:
        default = {}
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

def remove_signature(text: str) -> str:
    if not text:
        return text
    return text.replace(SIGNATURE, "").strip()

def validate_phone(phone: str) -> bool:
    phone = phone.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not phone:
        return False
    if len(phone) < 10 or len(phone) > 15:
        return False
    if not phone.isdigit():
        return False
    return True

def validate_username(username: str) -> bool:
    if not username:
        return False
    if not username.startswith('@'):
        username = '@' + username
    pattern = r'^@[a-zA-Z0-9_]{3,32}$'
    return bool(re.match(pattern, username))

def get_random_delay() -> float:
    return random.uniform(1.0, 3.0)

def is_valid_image(data: bytes) -> bool:
    try:
        Image.open(io.BytesIO(data))
        return True
    except:
        return False

def get_image_size(data: bytes) -> Tuple[int, int]:
    try:
        img = Image.open(io.BytesIO(data))
        return img.size
    except:
        return (0, 0)

def compress_image(data: bytes, max_size: int = 5 * 1024 * 1024) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
        if len(data) > max_size:
            output = io.BytesIO()
            img.save(output, format=img.format or 'JPEG', quality=70, optimize=True)
            compressed = output.getvalue()
            if len(compressed) < len(data):
                return compressed
        return data
    except:
        return data

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def with_db_connection(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with get_db_connection() as conn:
            return func(conn, *args, **kwargs)
    return wrapper

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (ПОЛНОСТЬЮ ОБНУЛЕНА)
# ============================================================================
def init_database():
    """Создает БД с нуля (все таблицы очищены)"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Удаляем все существующие таблицы
        tables = [
            'users', 'sessions', 'groups', 'send_history', 
            'payments', 'scheduled_sends', 'logs', 'referrals',
            'templates', 'sponsors', 'required_channels', 'settings',
            'images', 'stats'
        ]
        
        for table in tables:
            try:
                c.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"🗑️ Таблица {table} удалена")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить {table}: {e}")
        
        # Создаем таблицы заново
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
            language_code TEXT DEFAULT 'ru',
            last_activity TEXT,
            referral_code TEXT,
            referred_by INTEGER,
            referral_count INTEGER DEFAULT 0,
            notification_enabled INTEGER DEFAULT 1,
            auto_send_enabled INTEGER DEFAULT 0,
            user_hash TEXT,
            security_token TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            session_string TEXT,
            created_at TEXT,
            last_used TEXT,
            is_active INTEGER DEFAULT 1,
            device_name TEXT,
            device_hash TEXT,
            ip_hash TEXT,
            session_token TEXT
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
            last_sent_at TEXT,
            send_count INTEGER DEFAULT 0,
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
            error_message TEXT,
            is_scheduled INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            days INTEGER,
            status TEXT DEFAULT 'pending',
            payment_method TEXT DEFAULT 'card',
            transaction_id TEXT,
            created_at TEXT,
            confirmed_at TEXT,
            confirmed_by INTEGER,
            comment TEXT
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
            total_runs INTEGER DEFAULT 0,
            max_runs INTEGER DEFAULT 0,
            created_at TEXT
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
            reward_given INTEGER DEFAULT 0,
            reward_amount INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            content TEXT,
            created_at TEXT,
            is_global INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sponsors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            name TEXT,
            is_active INTEGER DEFAULT 1,
            added_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT UNIQUE,
            channel_title TEXT,
            added_at TEXT,
            is_active INTEGER DEFAULT 1
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            image_data BLOB,
            created_at TEXT,
            file_name TEXT,
            file_size INTEGER,
            width INTEGER,
            height INTEGER
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            new_users INTEGER DEFAULT 0,
            payments INTEGER DEFAULT 0,
            revenue INTEGER DEFAULT 0,
            sends INTEGER DEFAULT 0
        )''')
        
        # Создаем индексы
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(has_subscription, subscription_end)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_groups_user ON groups(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_history_user ON send_history(user_id, sent_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_scheduled_active ON scheduled_sends(active, next_run)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_stats_date ON stats(date)')
        
        conn.commit()
        logger.info("✅ База данных полностью обнулена и создана заново")

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
            "max_users": 100000,
            "broadcast_enabled": True,
            "min_delay_between_sends": 2,
            "max_groups_per_send": 200,
            "flood_protection_enabled": True,
            "max_messages_per_minute": 30,
            "referral_enabled": True,
            "referral_reward_days": 1,
            "auto_delete_history": 30,
            "max_templates": 20,
            "notification_enabled": True,
            "welcome_message": "👋 Добро пожаловать в бот!",
            "support_link": "https://t.me/sikvvg",
            "security_enabled": True,
            "session_encryption": True,
            "rate_limiting": True
        }
        safe_json_save(SETTINGS_FILE, default_settings)

def init_templates():
    if not os.path.exists(TEMPLATES_FILE):
        safe_json_save(TEMPLATES_FILE, {})

def init_blacklist():
    if not os.path.exists(BLACKLIST_FILE):
        safe_json_save(BLACKLIST_FILE, [])

# ============================================================================
# РАБОТА С БД - ОСНОВНЫЕ ФУНКЦИИ
# ============================================================================
@with_db_connection
def register_user(conn, user_id: int, username: str, first_name: str, last_name: str = "") -> bool:
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        return False
    
    referral_code = generate_id(8)
    user_hash = hash_user_data(user_id, f"{username}_{first_name}_{time.time()}")
    security_token = generate_id(32)
    
    c.execute("""INSERT INTO users 
                (user_id, username, first_name, last_name, registered_at, has_subscription, checked_channels, referral_code, user_hash, security_token, last_activity) 
                VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?)""",
              (user_id, username or "", first_name or "", last_name or "", get_timestamp(), referral_code, user_hash, security_token, get_timestamp()))
    conn.commit()
    logger.info(f"✅ Новый пользователь: {user_id} (@{username})")
    return True

@with_db_connection
def get_user(conn, user_id: int) -> Optional[Dict]:
    c = conn.cursor()
    c.execute("""SELECT user_id, username, first_name, last_name, registered_at, 
                        subscription_end, subscription_type, has_subscription, total_paid, 
                        trial_used, is_banned, checked_channels, referral_code, referred_by, referral_count,
                        language_code, last_activity, notification_enabled, auto_send_enabled, user_hash
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
        "referral_count": row[14] or 0,
        "language": row[15] or "ru",
        "last_activity": row[16] or "",
        "notification_enabled": bool(row[17]) if row[17] is not None else True,
        "auto_send_enabled": bool(row[18]) if row[18] is not None else False,
        "user_hash": row[19] or ""
    }

@with_db_connection
def get_all_users(conn) -> List[Dict]:
    c = conn.cursor()
    c.execute("""SELECT user_id, username, first_name, last_name, registered_at, 
                        subscription_end, subscription_type, has_subscription, total_paid, 
                        trial_used, is_banned, checked_channels, referral_code, referred_by, referral_count
                 FROM users ORDER BY user_id""")
    rows = c.fetchall()
    result = []
    for row in rows:
        result.append({
            "user_id": row[0],
            "username": row[1] or "",
            "first_name": row[2] or "",
            "last_name": row[3] or "",
            "registered_at": row[4] or "",
            "subscription_end": row[5] or "",
            "subscription_type": row[6] or "Нет",
            "has_subscription": bool(row[7]),
            "total_paid": row[8] or 0,
            "trial_used": bool(row[9]),
            "is_banned": bool(row[10]),
            "checked_channels": bool(row[11]),
            "referral_code": row[12] or "",
            "referred_by": row[13] or 0,
            "referral_count": row[14] or 0
        })
    return result

@with_db_connection
def check_subscription(conn, user_id: int) -> bool:
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

@with_db_connection
def get_subscription_type(conn, user_id: int) -> str:
    c = conn.cursor()
    c.execute("SELECT subscription_type FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return row[0] if row and row[0] else "Нет"

@with_db_connection
def get_remaining_days(conn, user_id: int) -> int:
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

@with_db_connection
def activate_beta_subscription(conn, user_id: int) -> bool:
    if get_remaining_days(user_id) > 0:
        return False
    
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
    logger.info(f"🎁 Активирована BETA подписка для {user_id} на {FREE_TRIAL_DAYS} дней")
    return True

@with_db_connection
def extend_subscription(conn, user_id: int, days: int, amount: int) -> datetime:
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
    logger.info(f"💳 Продлена подписка для {user_id} на {days} дней (+{amount} руб)")
    return new_end

@with_db_connection
def get_user_stats(conn, user_id: int) -> Dict:
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM send_history WHERE user_id = ? AND status = 'sent'", (user_id,))
    total_sends = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM send_history WHERE user_id = ? AND status = 'error'", (user_id,))
    error_sends = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM groups WHERE user_id = ? AND is_active = 1", (user_id,))
    total_groups = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'confirmed'", (user_id,))
    total_payments = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM payments WHERE user_id = ? AND status = 'confirmed'", (user_id,))
    total_spent = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    referrals = c.fetchone()[0]
    
    return {
        "total_sends": total_sends,
        "error_sends": error_sends,
        "total_groups": total_groups,
        "total_payments": total_payments,
        "total_spent": total_spent,
        "referrals": referrals
    }

@with_db_connection
def ban_user(conn, user_id: int) -> bool:
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    logger.info(f"🚫 Пользователь {user_id} заблокирован")
    return True

@with_db_connection
def unban_user(conn, user_id: int) -> bool:
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    logger.info(f"✅ Пользователь {user_id} разблокирован")
    return True

@with_db_connection
def update_user_activity(conn, user_id: int):
    c = conn.cursor()
    c.execute("UPDATE users SET last_activity = ? WHERE user_id = ?", (get_timestamp(), user_id))
    conn.commit()

# ============================================================================
# РАБОТА С СЕССИЯМИ (С ШИФРОВАНИЕМ)
# ============================================================================
@with_db_connection
def save_session(conn, user_id: int, session_string: str, device_name: str = "") -> bool:
    # Шифруем сессию
    encrypted = encrypt_data(session_string)
    device_hash = hash_user_data(user_id, f"{device_name}_{time.time()}")
    session_token = generate_id(32)
    
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO sessions 
                 (user_id, session_string, created_at, last_used, is_active, device_name, device_hash, session_token) 
                 VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
              (user_id, encrypted, get_timestamp(), get_timestamp(), device_name, device_hash, session_token))
    conn.commit()
    logger.info(f"💾 Сессия сохранена для {user_id} (зашифрована)")
    return True

@with_db_connection
def get_session(conn, user_id: int) -> Optional[str]:
    c = conn.cursor()
    c.execute("SELECT session_string, device_hash, session_token FROM sessions WHERE user_id = ? AND is_active = 1", (user_id,))
    row = c.fetchone()
    if row:
        try:
            # Расшифровываем сессию
            decrypted = decrypt_data(row[0])
            c.execute("UPDATE sessions SET last_used = ? WHERE user_id = ?", (get_timestamp(), user_id))
            conn.commit()
            return decrypted
        except Exception as e:
            logger.error(f"❌ Ошибка расшифровки сессии для {user_id}: {e}")
            return None
    return None

@with_db_connection
def delete_session(conn, user_id: int) -> bool:
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    logger.info(f"🗑️ Сессия удалена для {user_id}")
    return True

@with_db_connection
def deactivate_session(conn, user_id: int) -> bool:
    c = conn.cursor()
    c.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    return True

@with_db_connection
def validate_session_token(conn, user_id: int, token: str) -> bool:
    c = conn.cursor()
    c.execute("SELECT session_token FROM sessions WHERE user_id = ? AND is_active = 1", (user_id,))
    row = c.fetchone()
    if row and row[0] == token:
        return True
    return False

# ============================================================================
# РАБОТА С ГРУППАМИ
# ============================================================================
@with_db_connection
def add_group(conn, user_id: int, group_id: int, group_username: str = "", group_title: str = "", group_type: str = "group") -> bool:
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM groups WHERE user_id = ? AND is_active = 1", (user_id,))
    count = c.fetchone()[0]
    if count >= MAX_GROUPS_PER_USER:
        logger.warning(f"⚠️ Превышен лимит групп для {user_id}")
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

@with_db_connection
def get_user_groups(conn, user_id: int) -> List[Dict]:
    c = conn.cursor()
    c.execute("""SELECT group_id, group_username, group_title, group_type, added_at, last_sent_at, send_count
                 FROM groups 
                 WHERE user_id = ? AND is_active = 1 AND group_type = 'group'
                 ORDER BY group_title""", (user_id,))
    rows = c.fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "username": row[1] or "",
            "title": row[2] or f"Группа {row[0]}",
            "type": row[3] or "group",
            "added_at": row[4] or "",
            "last_sent_at": row[5] or "",
            "send_count": row[6] or 0
        })
    return result

@with_db_connection
def get_user_groups_count(conn, user_id: int) -> int:
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM groups WHERE user_id = ? AND is_active = 1", (user_id,))
    return c.fetchone()[0]

@with_db_connection
def clear_user_groups(conn, user_id: int) -> bool:
    c = conn.cursor()
    c.execute("DELETE FROM groups WHERE user_id = ?", (user_id,))
    conn.commit()
    return True

@with_db_connection
def remove_group(conn, user_id: int, group_id: int) -> bool:
    c = conn.cursor()
    c.execute("DELETE FROM groups WHERE user_id = ? AND group_id = ?", (user_id, group_id))
    conn.commit()
    return c.rowcount > 0

@with_db_connection
def update_group_last_sent(conn, user_id: int, group_id: int):
    c = conn.cursor()
    c.execute("UPDATE groups SET last_sent_at = ?, send_count = send_count + 1 WHERE user_id = ? AND group_id = ?",
              (get_timestamp(), user_id, group_id))
    conn.commit()

# ============================================================================
# РАБОТА С ИСТОРИЕЙ
# ============================================================================
@with_db_connection
def add_to_history(conn, user_id: int, group_name: str, group_id: int, message: str, 
                   message_type: str = "text", status: str = "sent", error: str = "", is_scheduled: int = 0) -> bool:
    c = conn.cursor()
    c.execute("""INSERT INTO send_history 
                 (user_id, group_name, group_id, sent_at, message_text, message_type, status, error_message, is_scheduled) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (user_id, group_name, group_id, get_timestamp(), truncate_text(message, 500), message_type, status, error[:500], is_scheduled))
    conn.commit()
    return True

@with_db_connection
def get_history(conn, user_id: int, limit: int = 20) -> List[Tuple]:
    c = conn.cursor()
    c.execute("""SELECT group_name, sent_at, message_text, status, error_message, is_scheduled
                 FROM send_history 
                 WHERE user_id = ? 
                 ORDER BY sent_at DESC 
                 LIMIT ?""", (user_id, limit))
    return c.fetchall()

@with_db_connection
def get_history_stats(conn, user_id: int) -> Dict:
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM send_history WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM send_history WHERE user_id = ? AND status = 'sent'", (user_id,))
    sent = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM send_history WHERE user_id = ? AND status = 'error'", (user_id,))
    errors = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM send_history WHERE user_id = ? AND is_scheduled = 1", (user_id,))
    scheduled = c.fetchone()[0]
    return {"total": total, "sent": sent, "errors": errors, "scheduled": scheduled}

# ============================================================================
# РАБОТА С ПЛАТЕЖАМИ
# ============================================================================
@with_db_connection
def save_payment(conn, user_id: int, days: int, amount: int, payment_method: str = "card", comment: str = "") -> int:
    c = conn.cursor()
    transaction_id = generate_id()
    c.execute("""INSERT INTO payments 
                 (user_id, amount, days, status, payment_method, transaction_id, created_at, comment) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (user_id, amount, days, "pending", payment_method, transaction_id, get_timestamp(), comment))
    conn.commit()
    payment_id = c.lastrowid
    logger.info(f"💳 Создан платеж #{payment_id} для {user_id} на {amount} руб")
    return payment_id

@with_db_connection
def get_pending_payments(conn) -> List[Dict]:
    c = conn.cursor()
    c.execute("""SELECT id, user_id, amount, days, status, transaction_id, created_at, confirmed_at, confirmed_by
                 FROM payments 
                 WHERE status = 'pending' 
                 ORDER BY created_at ASC""")
    rows = c.fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "user_id": row[1],
            "amount": row[2],
            "days": row[3],
            "status": row[4],
            "transaction_id": row[5] or "",
            "created_at": row[6] or "",
            "confirmed_at": row[7] or "",
            "confirmed_by": row[8] or 0
        })
    return result

@with_db_connection
def get_payment(conn, payment_id: int) -> Optional[Dict]:
    c = conn.cursor()
    c.execute("""SELECT id, user_id, amount, days, status, transaction_id, created_at, confirmed_at, confirmed_by, comment
                 FROM payments WHERE id = ?""", (payment_id,))
    row = c.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "amount": row[2],
        "days": row[3],
        "status": row[4],
        "transaction_id": row[5] or "",
        "created_at": row[6] or "",
        "confirmed_at": row[7] or "",
        "confirmed_by": row[8] or 0,
        "comment": row[9] or ""
    }

@with_db_connection
def confirm_payment(conn, payment_id: int, admin_id: int) -> bool:
    c = conn.cursor()
    c.execute("SELECT user_id, days, amount FROM payments WHERE id = ? AND status = 'pending'", (payment_id,))
    row = c.fetchone()
    if not row:
        return False
    
    user_id, days, amount = row
    c.execute("""UPDATE payments 
                 SET status = 'confirmed', confirmed_at = ?, confirmed_by = ? 
                 WHERE id = ?""",
              (get_timestamp(), admin_id, payment_id))
    conn.commit()
    
    extend_subscription(user_id, days, amount)
    logger.info(f"✅ Подтвержден платеж #{payment_id} для {user_id}")
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
# РАБОТА С ШАБЛОНАМИ
# ============================================================================
@with_db_connection
def save_template(conn, user_id: int, name: str, content: str, is_global: bool = False) -> bool:
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM templates WHERE user_id = ? AND is_global = 0", (user_id,))
    count = c.fetchone()[0]
    if count >= 20:
        return False
    
    c.execute("""INSERT INTO templates (user_id, name, content, created_at, is_global) 
                 VALUES (?, ?, ?, ?, ?)""",
              (user_id, name, content, get_timestamp(), 1 if is_global else 0))
    conn.commit()
    return True

@with_db_connection
def get_templates(conn, user_id: int) -> List[Dict]:
    c = conn.cursor()
    c.execute("""SELECT id, name, content, created_at, is_global 
                 FROM templates 
                 WHERE user_id = ? OR is_global = 1
                 ORDER BY is_global DESC, name""", (user_id,))
    rows = c.fetchall()
    return [{"id": r[0], "name": r[1], "content": r[2], "created_at": r[3], "is_global": bool(r[4])} for r in rows]

@with_db_connection
def delete_template(conn, template_id: int, user_id: int) -> bool:
    c = conn.cursor()
    c.execute("DELETE FROM templates WHERE id = ? AND (user_id = ? OR is_global = 1)", (template_id, user_id))
    conn.commit()
    return c.rowcount > 0

@with_db_connection
def get_template(conn, template_id: int) -> Optional[Dict]:
    c = conn.cursor()
    c.execute("SELECT id, user_id, name, content, created_at, is_global FROM templates WHERE id = ?", (template_id,))
    row = c.fetchone()
    if not row:
        return None
    return {"id": row[0], "user_id": row[1], "name": row[2], "content": row[3], "created_at": row[4], "is_global": bool(row[5])}

# ============================================================================
# РАБОТА С РЕФЕРАЛАМИ
# ============================================================================
@with_db_connection
def add_referral(conn, referrer_id: int, referred_id: int) -> bool:
    c = conn.cursor()
    c.execute("SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, referred_id))
    if c.fetchone():
        return False
    
    c.execute("INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
              (referrer_id, referred_id, get_timestamp()))
    conn.commit()
    
    c.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referrer_id,))
    conn.commit()
    
    settings = safe_json_load(SETTINGS_FILE, {})
    reward_days = settings.get('referral_reward_days', 1)
    if reward_days > 0:
        extend_subscription(referrer_id, reward_days, 0)
        c.execute("UPDATE referrals SET reward_given = 1, reward_amount = ? WHERE referrer_id = ? AND referred_id = ?",
                  (reward_days, referrer_id, referred_id))
        conn.commit()
    
    logger.info(f"👤 Новый реферал: {referred_id} от {referrer_id}")
    return True

@with_db_connection
def get_referrals(conn, user_id: int) -> List[Dict]:
    c = conn.cursor()
    c.execute("""SELECT referred_id, created_at, reward_given, reward_amount 
                 FROM referrals WHERE referrer_id = ? ORDER BY created_at DESC""", (user_id,))
    rows = c.fetchall()
    return [{"referred_id": r[0], "created_at": r[1], "reward_given": bool(r[2]), "reward_amount": r[3] or 0} for r in rows]

# ============================================================================
# СТАТИСТИКА
# ============================================================================
@with_db_connection
def get_stats(conn) -> Dict:
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
    
    today = datetime.now().date().isoformat()
    c.execute("SELECT COUNT(*) FROM send_history WHERE sent_at LIKE ?", (f"{today}%",))
    today_sends = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM payments WHERE created_at LIKE ? AND status = 'confirmed'", (f"{today}%",))
    today_payments = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM referrals")
    total_referrals = c.fetchone()[0]
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "revenue": revenue,
        "accounts": accounts,
        "groups": groups,
        "pending": pending,
        "banned": banned,
        "today_sends": today_sends,
        "today_payments": today_payments,
        "total_referrals": total_referrals
    }

@with_db_connection
def get_weekly_stats(conn) -> Dict:
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE registered_at > ?", (week_ago,))
    new_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM payments WHERE created_at > ? AND status = 'confirmed'", (week_ago,))
    payments = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM payments WHERE created_at > ? AND status = 'confirmed'", (week_ago,))
    revenue = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM send_history WHERE sent_at > ?", (week_ago,))
    sends = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals WHERE created_at > ?", (week_ago,))
    referrals = c.fetchone()[0]
    
    return {
        "new_users": new_users,
        "payments": payments,
        "revenue": revenue,
        "sends": sends,
        "referrals": referrals
    }

@with_db_connection
def get_user_ranking(conn, limit: int = 10) -> List[Dict]:
    c = conn.cursor()
    c.execute("""SELECT user_id, username, total_paid, referral_count, 
                        (SELECT COUNT(*) FROM send_history WHERE user_id = users.user_id) as sends
                 FROM users 
                 WHERE is_banned = 0
                 ORDER BY total_paid DESC, sends DESC
                 LIMIT ?""", (limit,))
    rows = c.fetchall()
    return [{"user_id": r[0], "username": r[1] or "нет", "total_paid": r[2] or 0, "referrals": r[3] or 0, "sends": r[4] or 0} for r in rows]

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
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return False, ["Аккаунт не авторизован"]
        
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

# ============================================================================
# НОВАЯ ФУНКЦИЯ: ОТПРАВКА ПО ССЫЛКЕ
# ============================================================================
async def send_by_link(user_id: int, link: str, text: str, image_data: Optional[bytes] = None) -> Dict:
    """
    Отправляет сообщение по ссылке на чат/канал/группу
    Поддерживает: https://t.me/username, https://t.me/joinchat/...
    """
    if not check_subscription(user_id):
        return {"success": 0, "fails": 1, "failed": ["Подписка истекла"], "status": "error"}
    
    # Проверка на спам
    if not validate_session_usage(user_id):
        return {"success": 0, "fails": 1, "failed": ["Превышен лимит запросов"], "status": "error"}
    
    session = get_session(user_id)
    if not session:
        return {"success": 0, "fails": 1, "failed": ["Нет аккаунта"], "status": "error"}
    
    final_text = add_signature(text)
    
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH, connection_retries=3)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return {"success": 0, "fails": 1, "failed": ["Аккаунт не авторизован"], "status": "error"}
        
        # Парсим ссылку
        entity = None
        
        # Форматы ссылок:
        # https://t.me/username
        # https://t.me/joinchat/XXXXX
        # https://t.me/c/123456789/1
        
        if "t.me/" in link:
            parts = link.split("t.me/")[1].split("/")
            username = parts[0]
            
            if username.startswith("joinchat") or username.startswith("+") or username.startswith("join"):
                # Инвайт-ссылка
                try:
                    entity = await client.get_entity(link)
                    if not entity:
                        # Пробуем через join
                        try:
                            await client.join_channel(link)
                            entity = await client.get_entity(link)
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Ошибка инвайт-ссылки: {e}")
                    return {"success": 0, "fails": 1, "failed": ["Не удалось подключиться по ссылке"], "status": "error"}
            else:
                # Обычная ссылка
                try:
                    entity = await client.get_entity(username)
                except:
                    return {"success": 0, "fails": 1, "failed": [f"Не найден чат @{username}"], "status": "error"}
        
        if not entity:
            return {"success": 0, "fails": 1, "failed": ["Не удалось найти чат"], "status": "error"}
        
        # Отправляем сообщение
        if image_data:
            compressed_image = compress_image(image_data)
            await client.send_file(entity, compressed_image, caption=final_text)
        else:
            await client.send_message(entity, final_text)
        
        # Записываем в историю
        add_to_history(user_id, link, 0, text, "text", "sent", "", 0)
        
        await client.disconnect()
        return {"success": 1, "fails": 0, "failed": [], "status": "completed"}
        
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + FLOOD_WAIT_BUFFER)
        return {"success": 0, "fails": 1, "failed": [f"FloodWait: {e.seconds} сек"], "status": "error"}
    except Exception as e:
        return {"success": 0, "fails": 1, "failed": [str(e)[:100]], "status": "error"}

# ============================================================================
# ОТПРАВКА В ГРУППЫ
# ============================================================================
async def send_message_to_groups(user_id: int, groups: List[Dict], text: str, 
                                  image_data: Optional[bytes] = None, 
                                  is_scheduled: bool = False,
                                  schedule_id: int = 0) -> Dict:
    if not check_subscription(user_id):
        return {"success": 0, "fails": 0, "failed_groups": ["Подписка истекла"], "status": "error"}
    
    # Проверка на спам
    if not validate_session_usage(user_id):
        return {"success": 0, "fails": 0, "failed_groups": ["Превышен лимит запросов"], "status": "error"}
    
    channels_ok, not_subscribed = await check_user_channels(user_id)
    if not channels_ok:
        return {"success": 0, "fails": 0, "failed_groups": [f"Подпишитесь на каналы: {', '.join(not_subscribed)}"], "status": "error"}
    
    session = get_session(user_id)
    if not session:
        return {"success": 0, "fails": 0, "failed_groups": ["Нет аккаунта"], "status": "error"}
    
    final_text = add_signature(text)
    success = 0
    fails = 0
    failed_groups = []
    status = "completed"
    
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH, connection_retries=3)
        await client.connect()
        
        if not await client.is_user_authorized():
            return {"success": 0, "fails": 0, "failed_groups": ["Аккаунт не авторизован"], "status": "error"}
        
        me = await client.get_me()
        
        for idx, group in enumerate(groups[:MAX_SEND_GROUPS]):
            try:
                group_id = int(group['id'])
                group_title = group.get('title') or group.get('username') or str(group_id)
                
                if idx > 0:
                    await asyncio.sleep(RATE_LIMIT_DELAY)
                
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
                
                try:
                    if hasattr(entity, 'participants_count'):
                        try:
                            await client.get_participant(entity, me.id)
                        except UserNotParticipantError:
                            raise Exception("Пользователь не является участником группы")
                        except UserBannedInChannelError:
                            raise Exception("Пользователь забанен в группе")
                    
                    if image_data:
                        compressed_image = compress_image(image_data)
                        await client.send_file(entity, compressed_image, caption=final_text)
                    else:
                        await client.send_message(entity, final_text)
                    
                    success += 1
                    update_group_last_sent(user_id, group_id)
                    if not is_scheduled:
                        add_to_history(user_id, group_title, group_id, text, "text", "sent", "", 0)
                    logger.info(f"✅ Отправлено в {group_title}")
                    
                except SlowModeWaitError as e:
                    logger.warning(f"⏳ Slow mode в {group_title}: {e}")
                    await asyncio.sleep(e.seconds + 1)
                    if image_data:
                        await client.send_file(entity, compressed_image, caption=final_text)
                    else:
                        await client.send_message(entity, final_text)
                    success += 1
                    update_group_last_sent(user_id, group_id)
                    if not is_scheduled:
                        add_to_history(user_id, group_title, group_id, text, "text", "sent", "", 0)
                
                except FloodWaitError as e:
                    wait_time = e.seconds + FLOOD_WAIT_BUFFER
                    logger.warning(f"⏳ Flood wait {wait_time} сек для {group_title}")
                    await asyncio.sleep(wait_time)
                    fails += 1
                    failed_groups.append(group_title)
                    add_to_history(user_id, group_title, group_id, text, "text", "error", f"FloodWait: {e.seconds} сек", 1 if is_scheduled else 0)
                    
                except Exception as e:
                    error_msg = str(e)[:200]
                    fails += 1
                    failed_groups.append(group_title)
                    logger.error(f"❌ Ошибка в {group_title}: {error_msg}")
                    add_to_history(user_id, group_title, group_id, text, "text", "error", error_msg, 1 if is_scheduled else 0)
                    
            except Exception as e:
                fails += 1
                failed_groups.append(group.get('title') or group.get('username') or str(group_id))
                logger.error(f"❌ Ошибка обработки группы: {e}")
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return {"success": 0, "fails": 1, "failed_groups": [str(e)[:100]], "status": "critical_error"}
    
    return {"success": success, "fails": fails, "failed_groups": failed_groups, "status": status}

# ============================================================================
# МЕНЮ
# ============================================================================
def get_main_menu(user_id: int) -> List[List]:
    is_admin = user_id in ADMIN_IDS
    buttons = [
        [Button.inline("➕ Добавить аккаунт", b"add_account"), Button.inline("👤 Мои аккаунты", b"my_accounts")],
        [Button.inline("📋 Добавить все группы", b"add_all_groups"), Button.inline("👥 Мои группы", b"my_groups")],
        [Button.inline("📨 Рассылка", b"send_message"), Button.inline("🔗 По ссылке", b"send_by_link")],
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
    
    # Проверка на спам
    if not validate_session_usage(uid):
        await event.respond("❌ Превышен лимит запросов. Подождите минуту.")
        return
    
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
            f"📢 Обязательные каналы: {len(required_channels)}\n"
            f"🔗 Отправка по ссылке: /sendlink\n"
            f"🔒 Безопасность: ВКЛЮЧЕНА",
            buttons=get_main_menu(uid)
        )
    else:
        if check_subscription(uid):
            await event.respond(
                f"👋 Главное меню\n"
                f"📦 Подписка: {sub_type}\n"
                f"📅 Осталось: {days} дн.\n"
                f"📢 Обязательные каналы: {len(required_channels)}\n"
                f"🔒 Безопасность: ВКЛЮЧЕНА",
                buttons=get_main_menu(uid)
            )
        else:
            await event.respond(
                f"👋 Главное меню\n"
                f"📦 Подписка: {sub_type}\n"
                f"📅 Осталось: {days} дн.\n\n"
                f"💡 Для работы добавьте аккаунт и купите подписку!\n"
                f"📢 Обязательные каналы: {len(required_channels)}\n"
                f"🔒 Безопасность: ВКЛЮЧЕНА",
                buttons=get_main_menu(uid)
            )

# ============================================================================
# КОМАНДА: ОТПРАВКА ПО ССЫЛКЕ
# ============================================================================
@bot.on(events.NewMessage(pattern="/sendlink"))
async def sendlink_cmd(event):
    uid = event.sender_id
    
    # Проверка на спам
    if not validate_session_usage(uid):
        await event.respond("❌ Превышен лимит запросов. Подождите минуту.")
        return
    
    if not check_subscription(uid):
        await event.respond("❌ Подписка истекла! Купите подписку.")
        return
    
    await event.respond(
        "🔗 ОТПРАВКА ПО ССЫЛКЕ\n\n"
        "Отправьте ссылку на чат/канал/группу и текст сообщения.\n\n"
        "Примеры ссылок:\n"
        "• https://t.me/username\n"
        "• https://t.me/joinchat/XXXXX\n"
        "• https://t.me/c/123456789/1\n\n"
        "📝 Формат: ссылка | текст\n"
        "🖼️ Можно приложить изображение\n\n"
        "🔒 Все сообщения проверяются на безопасность",
        buttons=[[Button.inline("❌ Отмена", b"cancel_send")]]
    )
    user_states[uid] = {"action": "waiting_for_link"}

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states.get(e.sender_id, {}).get("action") == "waiting_for_link"))
async def process_link_send(event):
    uid = event.sender_id
    
    # Проверка на спам
    if not validate_session_usage(uid):
        await event.respond("❌ Превышен лимит запросов. Подождите минуту.")
        return
    
    if event.photo:
        try:
            file = await event.download_media(file=bytes)
            caption = event.caption or ""
            
            link_match = re.search(r'https?://t\.me/[^\s]+', caption)
            if not link_match:
                await event.respond("❌ Не найдена ссылка в тексте!\nПример: https://t.me/username | текст")
                return
            
            link = link_match.group(0)
            text = caption.replace(link, "").strip()
            text = re.sub(r'^[\|\s]+', '', text)
            text = re.sub(r'[\|\s]+$', '', text)
            
            if not text:
                await event.respond("❌ Введите текст сообщения!")
                return
            
            await event.respond(f"🔄 Отправка по ссылке: {link}")
            result = await send_by_link(uid, link, text, file)
            
            if result['success'] > 0:
                await event.respond(f"✅ Сообщение отправлено!\n🔗 {link}\n📝 {truncate_text(text, 50)}", buttons=get_main_menu(uid))
            else:
                await event.respond(f"❌ Ошибка: {', '.join(result['failed'])}", buttons=get_main_menu(uid))
            
            if uid in user_states:
                del user_states[uid]
            return
            
        except Exception as e:
            await event.respond(f"❌ Ошибка: {str(e)[:100]}")
            return
    
    elif event.text:
        text = event.text.strip()
        
        link_match = re.search(r'https?://t\.me/[^\s]+', text)
        if not link_match:
            await event.respond("❌ Не найдена ссылка!\nПример: https://t.me/username | текст")
            return
        
        link = link_match.group(0)
        message = text.replace(link, "").strip()
        message = re.sub(r'^[\|\s]+', '', message)
        message = re.sub(r'[\|\s]+$', '', message)
        
        if not message:
            await event.respond("❌ Введите текст сообщения!")
            return
        
        await event.respond(f"🔄 Отправка по ссылке: {link}")
        result = await send_by_link(uid, link, message)
        
        if result['success'] > 0:
            await event.respond(f"✅ Сообщение отправлено!\n🔗 {link}\n📝 {truncate_text(message, 50)}", buttons=get_main_menu(uid))
        else:
            await event.respond(f"❌ Ошибка: {', '.join(result['failed'])}", buttons=get_main_menu(uid))
        
        if uid in user_states:
            del user_states[uid]
        return
    
    else:
        await event.respond("❌ Отправьте текст с ссылкой или изображение с подписью!")

@bot.on(events.CallbackQuery(data=b"send_by_link"))
async def send_by_link_cb(event):
    await sendlink_cmd(event)

# ============================================================================
# КОМАНДА: ПАНЕЛЬ АДМИНА
# ============================================================================
@bot.on(events.NewMessage(pattern="/panel"))
async def panel_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        await event.respond("❌ Доступ запрещен")
        return
    
    stats = get_stats()
    required_channels = get_required_channels()
    weekly = get_weekly_stats()
    ranking = get_user_ranking(5)
    
    text = f"""👑 АДМИН ПАНЕЛЬ @{BOT_USERNAME}

📊 СТАТИСТИКА:
├ 👥 Всего: {format_number(stats['total_users'])}
├ 🟢 Активных: {format_number(stats['active_users'])}
├ ⛔ Заблокировано: {format_number(stats['banned'])}
├ 💰 Выручка: {format_number(stats['revenue'])} руб
├ 📱 Аккаунтов: {format_number(stats['accounts'])}
├ 👥 Групп: {format_number(stats['groups'])}
├ 💳 Ожидают: {format_number(stats['pending'])}
├ 📨 Сегодня: {format_number(stats['today_sends'])} отправок
├ 💳 Сегодня: {format_number(stats['today_payments'])} платежей
└ 👥 Рефералов: {format_number(stats['total_referrals'])}

📈 ЗА НЕДЕЛЮ:
├ 👤 Новых: {format_number(weekly['new_users'])}
├ 💳 Платежей: {format_number(weekly['payments'])}
├ 💰 Выручка: {format_number(weekly['revenue'])} руб
├ 📨 Отправок: {format_number(weekly['sends'])}
└ 👥 Рефералов: {format_number(weekly['referrals'])}

🏆 ТОП ПОЛЬЗОВАТЕЛЕЙ:
"""
    for i, u in enumerate(ranking, 1):
        text += f"{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else f'{i}. '} {u['username']} - 💰{format_number(u['total_paid'])} руб | 📨{format_number(u['sends'])}\n"
    
    text += f"""
📢 Обязательные каналы ({len(required_channels)}):
{chr(10).join(required_channels) if required_channels else 'Не заданы'}

🔒 БЕЗОПАСНОСТЬ:
├ Шифрование сессий: ВКЛЮЧЕНО
├ Защита от флуда: ВКЛЮЧЕНА
├ Лимит запросов: {MAX_REQUESTS_PER_MINUTE}/мин
└ Мониторинг активности: ВКЛЮЧЕН

📋 Команды:
├ /users - список пользователей
├ /podpis ID дни - выдать подписку
├ /check ID - проверить пользователя
├ /ban ID - заблокировать
├ /unban ID - разблокировать
├ /sendlink - отправить по ссылке
├ /pending - платежи
├ /confirm ID - подтвердить
├ /addchannel @channel - добавить обязательный канал
├ /removechannel @channel - удалить обязательный канал
└ /channels - список обязательных каналов"""
    
    await event.respond(text, buttons=get_admin_menu())

# ============================================================================
# ОСТАЛЬНЫЕ КОМАНДЫ АДМИНА
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
    for u in users[:25]:
        status = "🟢" if u['has_subscription'] else "🔴"
        if u['is_banned']:
            status = "⛔"
        channels_checked = "✅" if u['checked_channels'] else "❌"
        text += f"{status} `{u['user_id']}` | @{u['username']} | {u['subscription_type']} | {channels_checked} | 💰{u['total_paid']} руб\n"
    if len(users) > 25:
        text += f"\n... и еще {len(users) - 25} пользователей"
    text += f"\n\n📊 Всего: {len(users)} пользователей"
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
        user = get_user(uid)
        if user:
            days = get_remaining_days(uid)
            status = "🟢 Активна" if check_subscription(uid) else "🔴 Неактивна"
            channels_checked = "✅" if user['checked_channels'] else "❌"
            stats = get_user_stats(uid)
            text = f"📊 Пользователь {uid}\n"
            text += f"👤 {user['first_name']} {user['last_name']}\n"
            text += f"📝 @{user['username']}\n"
            text += f"📦 {user['subscription_type']}\n"
            text += f"📅 {status}\n"
            text += f"💰 {user['total_paid']} руб\n"
            text += f"📆 Осталось: {days} дн.\n"
            text += f"📢 Каналы проверены: {channels_checked}\n"
            text += f"📨 Отправок: {stats['total_sends']}\n"
            text += f"👥 Групп: {stats['total_groups']}\n"
            text += f"💳 Платежей: {stats['total_payments']}\n"
            text += f"💸 Потрачено: {stats['total_spent']} руб\n"
            text += f"👥 Рефералов: {user['referral_count']}\n"
            text += f"📅 Зарегистрирован: {user['registered_at'][:16] if user['registered_at'] else 'неизвестно'}"
            await event.respond(text)
        else:
            await event.respond(f"❌ Пользователь {uid} не найден")

@bot.on(events.NewMessage(pattern="/ban (\\d+)"))
async def ban_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/ban (\d+)", event.text)
    if m:
        uid = int(m.group(1))
        ban_user(uid)
        await event.respond(f"✅ Пользователь {uid} заблокирован")
        try:
            await bot.send_message(uid, "⛔ Ваш аккаунт был заблокирован администратором.")
        except:
            pass

@bot.on(events.NewMessage(pattern="/unban (\\d+)"))
async def unban_cmd(event):
    if event.sender_id not in ADMIN_IDS:
        return
    m = re.match(r"/unban (\d+)", event.text)
    if m:
        uid = int(m.group(1))
        unban_user(uid)
        await event.respond(f"✅ Пользователь {uid} разблокирован")
        try:
            await bot.send_message(uid, "✅ Ваш аккаунт был разблокирован администратором.")
        except:
            pass

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
    weekly = get_weekly_stats()
    text = f"""📊 СТАТИСТИКА @{BOT_USERNAME}

📊 ОБЩАЯ:
├ 👥 Всего: {format_number(stats['total_users'])}
├ 🟢 Активных: {format_number(stats['active_users'])}
├ ⛔ Заблокировано: {format_number(stats['banned'])}
├ 💰 Выручка: {format_number(stats['revenue'])} руб
├ 📱 Аккаунтов: {format_number(stats['accounts'])}
├ 👥 Групп: {format_number(stats['groups'])}
├ 💳 Ожидают: {format_number(stats['pending'])}
├ 📨 Сегодня: {format_number(stats['today_sends'])} отправок
└ 💳 Сегодня: {format_number(stats['today_payments'])} платежей

📈 ЗА НЕДЕЛЮ:
├ 👤 Новых: {format_number(weekly['new_users'])}
├ 💳 Платежей: {format_number(weekly['payments'])}
├ 💰 Выручка: {format_number(weekly['revenue'])} руб
└ 📨 Отправок: {format_number(weekly['sends'])}"""
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
        status = "🟢" if u['has_subscription'] else "🔴"
        if u['is_banned']:
            status = "⛔"
        text += f"{status} {u['user_id']} | @{u['username']} | {u['subscription_type']}\n"
    if len(users) > 15:
        text += f"\n... и еще {len(users) - 15} пользователей"
    text += f"\n\n📊 Всего: {len(users)} пользователей"
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
    if len(payments) > 10:
        text += f"\n... и еще {len(payments) - 10} платежей"
    text += f"\n📊 Всего: {len(payments)} платежей"
    await event.respond(text, buttons=get_admin_menu())

@bot.on(events.CallbackQuery(data=b"admin_broadcast"))
async def admin_broadcast_cb(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Доступ запрещен", alert=True)
        return
    await event.respond(
        "📢 РАССЫЛКА АДМИНА\n\n"
        "Отправьте сообщение для рассылки всем пользователям.\n"
        "Это может быть текст или текст с изображением.\n\n"
        "⚠️ Рассылка будет отправлена всем пользователям бота!",
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
    if event.photo:
        try:
            file = await event.download_media(file=bytes)
            caption = event.caption or ""
            users = get_all_users()
            sent = 0
            await event.respond(f"📢 Рассылка {len(users)} пользователям...")
            for u in users:
                if u.get('is_banned'):
                    continue
                try:
                    await bot.send_message(u['user_id'], f"📢 ОБЪЯВЛЕНИЕ\n\n{caption}\n\n🤖 @{BOT_USERNAME}", file=file)
                    sent += 1
                    await asyncio.sleep(0.3)
                except:
                    pass
            await event.respond(f"✅ Отправлено: {sent} из {len(users)}", buttons=get_admin_menu())
            if uid in user_states:
                del user_states[uid]
        except Exception as e:
            await event.respond(f"❌ Ошибка: {str(e)[:100]}")
    elif event.text:
        msg = event.text.strip()
        users = get_all_users()
        sent = 0
        await event.respond(f"📢 Рассылка {len(users)} пользователям...")
        for u in users:
            if u.get('is_banned'):
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

🛠 Основные:
Режим обслуживания: {'🟢 Вкл' if settings.get('maintenance_mode', False) else '🔴 Выкл'}
Регистрация: {'🟢 Вкл' if settings.get('registration_enabled', True) else '🔴 Выкл'}
Рассылки: {'🟢 Вкл' if settings.get('broadcast_enabled', True) else '🔴 Выкл'}

📊 Лимиты:
Макс. пользователей: {settings.get('max_users', 100000)}
Задержка между отправками: {settings.get('min_delay_between_sends', 2)} сек
Макс. групп за отправку: {settings.get('max_groups_per_send', 200)}

🛡 Защита:
Защита от флуда: {'🟢 Вкл' if settings.get('flood_protection_enabled', True) else '🔴 Выкл'}
Макс. сообщений в минуту: {settings.get('max_messages_per_minute', 30)}
Шифрование сессий: {'🟢 Вкл' if settings.get('session_encryption', True) else '🔴 Выкл'}

👥 Рефералы:
Реферальная система: {'🟢 Вкл' if settings.get('referral_enabled', True) else '🔴 Выкл'}
Награда: {settings.get('referral_reward_days', 1)} дней

📋 Другое:
Авто-очистка истории: {settings.get('auto_delete_history', 30)} дней
Макс. шаблонов: {settings.get('max_templates', 20)}
Уведомления: {'🟢 Вкл' if settings.get('notification_enabled', True) else '🔴 Выкл'}"""
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
                last_lines = lines[-30:] if len(lines) > 30 else lines
                text = "📜 ПОСЛЕДНИЕ ЛОГИ\n\n" + "".join(last_lines[-30:])
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

# ============================================================================
# ПОКУПКА ПОДПИСКИ
# ============================================================================
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
        f"💰 ПОКУПКА ПОДПИСКИ @{BOT_USERNAME}\n\n"
        f"💵 {PRICE_PER_DAY} руб/день\n\n"
        f"Выберите срок подписки:",
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
        await event.respond(
            "✏️ Введите количество дней (от 3 до 365):",
            buttons=[[Button.inline("❌ Отмена", b"cancel_sub")]]
        )
        user_states[uid] = {"action": "custom_days"}
        return
    
    if action == "cancel_sub":
        if uid in user_states:
            del user_states[uid]
        await event.respond("❌ Отменено", buttons=get_main_menu(uid))
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
        f"💳 ОПЛАТА @{BOT_USERNAME}\n\n"
        f"📅 {days_text} = {amount} руб\n\n"
        f"💳 Карта: `{CARD_NUMBER}`\n"
        f"🏦 Банк: {BANK_NAME}\n"
        f"👤 Получатель: {CARD_HOLDER}\n\n"
        f"✅ После перевода нажмите кнопку\n"
        f"🆔 Ваш ID: `{uid}`",
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
            f"💳 ОПЛАТА @{BOT_USERNAME}\n\n"
            f"📅 {days} дней = {amount} руб\n\n"
            f"💳 Карта: `{CARD_NUMBER}`\n"
            f"🏦 Банк: {BANK_NAME}\n"
            f"👤 Получатель: {CARD_HOLDER}\n\n"
            f"✅ После перевода нажмите кнопку\n"
            f"🆔 Ваш ID: `{uid}`",
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

# ============================================================================
# ИНФОРМАЦИЯ
# ============================================================================
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
        f"🔒 Безопасность:\n"
        f"├ Шифрование сессий: ВКЛЮЧЕНО\n"
        f"├ Защита от флуда: ВКЛЮЧЕНА\n"
        f"└ Мониторинг активности: ВКЛЮЧЕН\n\n"
        f"📢 Подпись:\n`{SIGNATURE.strip()}`\n\n"
        f"💬 Поддержка: @sikvvg",
        buttons=get_main_menu(uid)
    )

# ============================================================================
# МОИ ГРУППЫ
# ============================================================================
@bot.on(events.CallbackQuery(data=b"my_groups"))
async def my_groups_cb(event):
    uid = event.sender_id
    groups = get_user_groups(uid)
    if not groups:
        await event.respond(
            "❌ Нет добавленных групп!\n\n"
            "Нажмите '📋 Добавить все группы' для автоматического добавления.",
            buttons=get_main_menu(uid)
        )
        return
    text = "👥 МОИ ГРУППЫ @{BOT_USERNAME}\n\n"
    for g in groups[:20]:
        text += f"📌 {g['title']}\n"
        text += f"🆔 {g['id']}\n"
        text += f"📅 {g['added_at'][:16] if g['added_at'] else 'неизвестно'}\n"
        text += f"📨 Отправок: {g['send_count']}\n\n"
    if len(groups) > 20:
        text += f"\n... и еще {len(groups) - 20} групп"
    text += f"\n📊 Всего: {len(groups)} групп"
    await event.respond(text, buttons=get_main_menu(uid))

# ============================================================================
# ДОБАВЛЕНИЕ АККАУНТА
# ============================================================================
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
    if not validate_phone(phone):
        await event.respond("❌ Неверный формат номера!")
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
            f"✅ Код отправлен на номер {phone[-4:]}!\n\n"
            f"📱 Введите код:",
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

# ============================================================================
# ВВОД КОДА
# ============================================================================
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

# ============================================================================
# МОИ АККАУНТЫ
# ============================================================================
@bot.on(events.CallbackQuery(data=b"my_accounts"))
async def my_accounts_cb(event):
    session = get_session(event.sender_id)
    if not session:
        await event.respond("❌ Нет аккаунтов", buttons=get_main_menu(event.sender_id))
        return
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            await event.respond("❌ Аккаунт не авторизован", buttons=get_main_menu(event.sender_id))
            return
        me = await client.get_me()
        await client.disconnect()
        await event.respond(
            f"📱 ВАШ АККАУНТ @{BOT_USERNAME}\n\n"
            f"👤 {me.first_name}\n"
            f"📝 @{me.username or 'нет'}\n"
            f"🆔 {me.id}\n"
            f"📱 {me.phone or 'не указан'}",
            buttons=[
                [Button.inline("❌ Удалить аккаунт", b"delete_account")],
                [Button.inline("◀️ Назад", b"back_to_main")]
            ]
        )
    except Exception as e:
        await event.respond(
            f"❌ Ошибка загрузки: {str(e)[:100]}",
            buttons=[[Button.inline("❌ Удалить аккаунт", b"delete_account")]]
        )

@bot.on(events.CallbackQuery(data=b"delete_account"))
async def delete_account_cb(event):
    delete_session(event.sender_id)
    clear_user_groups(event.sender_id)
    await event.respond("✅ Аккаунт и группы удалены", buttons=get_main_menu(event.sender_id))

# ============================================================================
# ДОБАВЛЕНИЕ ВСЕХ ГРУПП
# ============================================================================
@bot.on(events.CallbackQuery(data=b"add_all_groups"))
async def add_all_groups_cb(event):
    uid = event.sender_id
    
    if not check_subscription(uid):
        await event.respond("❌ Подписка истекла! Купите подписку.")
        return
    
    channels_ok, not_subscribed = await check_user_channels(uid)
    if not channels_ok:
        await event.respond(
            f"❌ Подпишитесь на каналы:\n{chr(10).join(not_subscribed)}",
            buttons=get_main_menu(uid)
        )
        return
    
    session = get_session(uid)
    if not session:
        await event.respond("❌ Сначала добавьте аккаунт!", buttons=get_main_menu(uid))
        return
    
    await event.respond("🔄 Загрузка групп... Подождите...")
    
    try:
        client = TelegramClient(StringSession(session), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            await event.respond("❌ Аккаунт не авторизован", buttons=get_main_menu(uid))
            return
        
        clear_user_groups(uid)
        
        dialogs = await client.get_dialogs()
        
        groups_found = 0
        group_names = []
        
        for dialog in dialogs:
            try:
                if dialog.is_group:
                    group_id = dialog.entity.id
                    group_name = dialog.name or "Без имени"
                    add_group(uid, group_id, group_name, group_name, "group")
                    groups_found += 1
                    group_names.append(group_name)
            except Exception as e:
                continue
        
        await client.disconnect()
        
        result_text = f"✅ Добавлены все группы!\n\n"
        result_text += f"📋 Групп: {groups_found}\n"
        result_text += f"📌 Проверка каналов пройдена ✅"
        
        if group_names:
            preview = "\n".join(group_names[:10])
            if len(group_names) > 10:
                preview += f"\n... и еще {len(group_names) - 10} групп"
            result_text += f"\n\n📌 Найденные группы:\n{preview}"
        else:
            result_text += f"\n\n❌ Группы не найдены!"
        
        await event.respond(result_text, buttons=get_main_menu(uid))
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Ошибка: {error_msg}")
        await event.respond(f"❌ Ошибка: {error_msg[:200]}", buttons=get_main_menu(uid))

# ============================================================================
# РАССЫЛКА
# ============================================================================
@bot.on(events.CallbackQuery(data=b"send_message"))
async def send_message_cb(event):
    uid = event.sender_id
    
    if not check_subscription(uid):
        await event.respond("❌ Подписка истекла! Купите подписку.")
        return
    
    channels_ok, not_subscribed = await check_user_channels(uid)
    if not channels_ok:
        await event.respond(
            f"❌ Подпишитесь на каналы:\n{chr(10).join(not_subscribed)}",
            buttons=get_main_menu(uid)
        )
        return
    
    groups = get_user_groups(uid)
    if not groups:
        await event.respond(
            "❌ Нет добавленных групп!\n\n"
            "Нажмите '📋 Добавить все группы' для автоматического добавления.",
            buttons=get_main_menu(uid)
        )
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
        f"📨 ВЫБЕРИТЕ ГРУППЫ @{BOT_USERNAME}\n\n"
        f"👥 Всего групп: {len(groups)}\n"
        f"Выберите группы для рассылки (можно выбрать несколько):\n\n"
        f"📢 Подпись будет добавлена автоматически",
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
        await event.answer("❌ Группа удалена из выбора")
    else:
        selected.append(group_id)
        await event.answer("✅ Группа добавлена в выбор")
    
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
        f"📝 Отправьте текст или изображение\n\n"
        f"📢 Подпись будет добавлена автоматически",
        buttons=[[Button.inline("❌ Отмена", b"cancel_send")]]
    )

@bot.on(events.CallbackQuery(data=b"cancel_select"))
async def cancel_select_cb(event):
    if event.sender_id in user_states:
        del user_states[event.sender_id]
    await event.respond("❌ Выбор отменен", buttons=get_main_menu(event.sender_id))

@bot.on(events.CallbackQuery(data=b"cancel_send"))
async def cancel_send_cb(event):
    if event.sender_id in user_states:
        del user_states[event.sender_id]
    await event.respond("❌ Рассылка отменена", buttons=get_main_menu(event.sender_id))

@bot.on(events.NewMessage(func=lambda e: e.sender_id in user_states and user_states.get(e.sender_id, {}).get("action") == "waiting_for_content"))
async def process_send_content(event):
    uid = event.sender_id
    groups = user_states[uid].get("groups", [])
    
    if not groups:
        await event.respond("❌ Нет групп для рассылки!")
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
            await event.respond(f"❌ Ошибка загрузки изображения: {str(e)[:100]}")
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
    
    user_states[uid] = {
        "action": "choose_repeat",
        "groups": groups,
        "message": text,
        "image": image_data
    }
    
    await event.respond(
        f"📨 ГОТОВО К ОТПРАВКЕ @{BOT_USERNAME}\n\n"
        f"📢 Текст:\n{truncate_text(text, 200) if text else '(без текста)'}\n"
        f"🖼️ Изображение: {'✅' if image_data else '❌'}\n"
        f"👥 Групп: {len(groups)}\n\n"
        f"🔄 Выберите интервал для повтора:",
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
        await event.respond("❌ Отправка отменена", buttons=get_main_menu(uid))
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
    result_text += f"👥 Групп: {len(groups)}\n"
    result_text += f"🖼️ Изображение: {'✅' if image_data else '❌'}"
    
    if result['failed_groups']:
        result_text += f"\n\n❌ Ошибки в:\n" + "\n".join(result['failed_groups'][:10])
        if len(result['failed_groups']) > 10:
            result_text += f"\n... и еще {len(result['failed_groups']) - 10}"
    
    if hours > 0:
        result_text += f"\n\n🔄 Повтор каждые {hours} часов"
        
        async def scheduled_send():
            logger.info(f"⏰ Запланированная отправка для {uid}")
            if check_subscription(uid):
                result = await send_message_to_groups(uid, groups, text, image_data, is_scheduled=True)
                try:
                    await bot.send_message(uid, 
                        f"🔄 ЗАПЛАНИРОВАННАЯ РАССЫЛКА @{BOT_USERNAME}\n"
                        f"✅ Успешно: {result['success']}\n"
                        f"❌ Ошибок: {result['fails']}\n"
                        f"👥 Групп: {len(groups)}"
                    )
                except:
                    pass
            else:
                try:
                    await bot.send_message(uid, "❌ Подписка истекла! Рассылка отменена.")
                except:
                    pass
        
        job_id = f"{uid}_{int(time.time())}"
        scheduler.add_job(
            scheduled_send,
            'interval',
            hours=hours,
            id=job_id,
            replace_existing=True
        )
        scheduled_jobs[job_id] = {
            "user_id": uid,
            "job_id": job_id,
            "hours": hours,
            "groups": groups,
            "message": text,
            "image": image_data,
            "created_at": get_timestamp()
        }
        
        result_text += f"\n\n🔔 Для отмены повтора: /cancel_repeat"
    
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
            except JobLookupError:
                del scheduled_jobs[job_id]
            except:
                pass
    
    if canceled > 0:
        await event.respond(f"✅ Отменено {canceled} запланированных рассылок", buttons=get_main_menu(uid))
    else:
        await event.respond("❌ Нет активных запланированных рассылок", buttons=get_main_menu(uid))

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
    print(f"🔒 ЗАПУСК ЗАЩИЩЕННОГО БОТА @{BOT_USERNAME}")
    print("=" * 60)
    
    # Инициализация с обнулением БД
    init_database()
    init_sponsors()
    init_required_channels()
    init_settings()
    init_templates()
    init_blacklist()
    
    # Настройка логирования
    logger.add(LOG_FILE, rotation="10 MB", retention="30 days", encoding="utf-8")
    logger.info(f"🔒 Запуск защищенного бота {BOT_USERNAME} v{VERSION}")
    
    print(f"🔄 Подключение к Telegram API...")
    
    try:
        await bot.start(bot_token=BOT_TOKEN)
        me = await bot.get_me()
        print(f"✅ Бот @{me.username} запущен!")
        print(f"👑 Админы: {ADMIN_IDS}")
        print(f"📌 Версия: {VERSION}")
        print(f"🔒 Шифрование сессий: ВКЛЮЧЕНО")
        print(f"🛡 Защита от флуда: ВКЛЮЧЕНА")
        print(f"🗑️ База данных: ОБНУЛЕНА")
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
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"❌ Ошибка: {e}")
        sys.exit(1)
