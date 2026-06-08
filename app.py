from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import requests

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = str(BASE_DIR)
DATA_DIR = Path(os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)).resolve()
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    raise RuntimeError(f"Unable to create data directory: {DATA_DIR}")

DEFAULT_ADMIN_ID = 8757408896


def load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def load_runtime_config() -> tuple[str, int | None, list[str]]:
    load_local_env()
    bot_token = first_non_empty(os.environ.get("BOT_TOKEN"))
    admin_raw = first_non_empty(
        os.environ.get("ADMIN_ID"),
        os.environ.get("ADMIN_USER_ID"),
        DEFAULT_ADMIN_ID,
    )
    try:
        admin_id = int(admin_raw) if admin_raw else None
    except ValueError:
        admin_id = None

    missing_required: list[str] = []
    if not bot_token:
        missing_required.append("BOT_TOKEN")

    return bot_token, admin_id, missing_required


BOT_TOKEN, ADMIN_ID, MISSING_REQUIRED_CONFIG = load_runtime_config()
POLL_TIMEOUT = 60
ADMIN_ONLY_COMMANDS = {
    "!admin",
    "!help",
    "!mode",
    "!setupi",
    "!setmid",
    "!settarget",
    "!setdemo",
    "!setproof",
    "!setimage",
    "!setstart",
    "!setpaymenttext",
    "!setnote",
    "!setplanlink",
    "!addchannel",
    "!delchannel",
    "!broadcast",
    "!backupusers",
}

START_TEXT = (
    "<b>Premium Access Plans</b>\n\n"
    "Basic: Rs 49 - 7 day\n"
    "Standard: Rs 79 - 30 day\n"
    "Premium: Rs 99 - 60 day\n"
    "VIP: Rs 149 - Lifetime\n\n"
    "Choose a plan below to continue."
)
PAYMENT_TEXT = (
    "<b>Premium Access</b>\n\n"
    "Scan the QR code or click the Pay button to complete the payment.\nभुगतान करने के लिए QR कोड स्कैन करें या Pay बटन पर क्लिक करें।\n\n"
    "After completing the payment, please send the screenshot or UTR number for verification.\nभुगतान पूर्ण करने के बाद कृपया स्क्रीनशॉट या UTR नंबर सत्यापन के लिए भेजें।"
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "payment_mode": "manual",
    "payment_note": "Premium Access",
    "plans": {
        "basic": {
            "name": "Basic",
            "price": "49",
            "duration_days": 7,
            "redirect_url": "https://redirect-1-tau.vercel.app/49",
        },
        "standard": {
            "name": "Standard",
            "price": "79",
            "duration_days": 30,
            "redirect_url": "https://redirect-1-tau.vercel.app/79",
        },
        "premium": {
            "name": "Premium",
            "price": "99",
            "duration_days": 60,
            "redirect_url": "https://redirect-1-tau.vercel.app/99",
        },
        "vip": {
            "name": "VIP",
            "price": "149",
            "duration_days": 0,
            "redirect_url": "https://redirect-1-tau.vercel.app/149",
        },
    },
    "upi_id": "BHARATPE2J0U0Z1Z5J72815@unitype",
    "merchant_mid": "",
    "demo_link": "",
    "proof_link": "",
    "target_channel_id": "",
    "start_image": "",
    "start_text": START_TEXT,
    "payment_text": PAYMENT_TEXT,
    "extra_channels": [],
    "button_texts": {
        "demo": "CHECK DEMO",
        "proofs": "CHECK PROOFS",
        "join_channel": "JOIN CHANNEL",
        "premium": "BUY NOW",
        "verify_payment": "VERIFY PAYMENT",
        "back": "BACK",
        "private_link": "GET PRIVATE LINK",
    },
}

DEFAULT_USERS = {"users": {}}
DEFAULT_PAID: dict[str, Any] = {}
DEFAULT_AUTO_PAYMENT: dict[str, Any] = {}
DEFAULT_TRANSACTIONS: list[dict[str, Any]] = []


FILE_DEFAULTS: dict[str, Any] = {
    "settings.json": DEFAULT_SETTINGS,
    "users.json": DEFAULT_USERS,
    "paid.json": DEFAULT_PAID,
    "auto_payment.json": DEFAULT_AUTO_PAYMENT,
    "transactions.json": DEFAULT_TRANSACTIONS,
}

def deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def read_json(name: str, default: Any) -> Any:
    path = DATA_DIR / name
    if not path.exists():
        write_json(name, default)
        return deep_copy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        write_json(name, default)
        return deep_copy(default)


def write_json(name: str, payload: Any) -> None:
    path = DATA_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def merge_dict(defaults: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = deep_copy(defaults)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


for file_name, default_value in FILE_DEFAULTS.items():
    if not (DATA_DIR / file_name).exists():
        write_json(file_name, default_value)


def get_settings() -> dict[str, Any]:
    stored = read_json("settings.json", DEFAULT_SETTINGS)
    merged = merge_dict(DEFAULT_SETTINGS, stored if isinstance(stored, dict) else {})
    write_json("settings.json", merged)
    return merged


def save_settings(settings: dict[str, Any]) -> None:
    write_json("settings.json", merge_dict(DEFAULT_SETTINGS, settings))


def is_admin(user_id: int | str | None) -> bool:
    return ADMIN_ID is not None and str(user_id or "") == str(ADMIN_ID)


def is_admin_command(text: str) -> bool:
    command = text.partition(" ")[0].lower()
    return command in ADMIN_ONLY_COMMANDS


def bot_api(method: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN missing"}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, json=payload or {}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"ok": False, "description": str(exc)}


def send_message(chat_id: int | str, text: str, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return bot_api("sendMessage", payload)


def send_photo(chat_id: int | str, photo: str, caption: str = "", reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo, "parse_mode": "HTML"}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return bot_api("sendPhoto", payload)


def send_document(chat_id: int | str, file_path: Path, caption: str = "") -> dict[str, Any]:
    if not BOT_TOKEN:
        return {"ok": False, "description": "BOT_TOKEN missing"}
    if not file_path.exists():
        return {"ok": False, "description": f"File not found: {file_path.name}"}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    data: dict[str, Any] = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
        data["parse_mode"] = "HTML"
    try:
        with file_path.open("rb") as handle:
            response = requests.post(
                url,
                data=data,
                files={"document": (file_path.name, handle, "application/json")},
                timeout=60,
            )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"ok": False, "description": str(exc)}


def answer_callback(callback_id: str, text: str | None = None, show_alert: bool = False) -> None:
    payload: dict[str, Any] = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    bot_api("answerCallbackQuery", payload)


def create_invite_link() -> str | None:
    target = str(get_settings().get("target_channel_id", "")).strip()
    if not target:
        return None
    response = bot_api(
        "createChatInviteLink",
        {"chat_id": target, "expire_date": int(time.time()) + 900, "member_limit": 1},
    )
    if response.get("ok"):
        return response["result"].get("invite_link")
    return None


def remove_from_target_chat(user_id: int | str) -> bool:
    target = str(get_settings().get("target_channel_id", "")).strip()
    if not target:
        return False
    response = bot_api(
        "banChatMember",
        {"chat_id": target, "user_id": user_id, "revoke_messages": False},
    )
    if not response.get("ok"):
        return False
    bot_api("unbanChatMember", {"chat_id": target, "user_id": user_id, "only_if_banned": True})
    return True


def enforce_expired_access() -> None:
    paid = read_json("paid.json", DEFAULT_PAID)
    if not isinstance(paid, dict):
        return
    now = int(time.time())
    changed = False
    for key, entry in paid.items():
        if not isinstance(entry, dict) or entry.get("access_revoked"):
            continue
        expires_at = entry.get("access_expires_at")
        if not isinstance(expires_at, int) or expires_at <= 0 or expires_at > now:
            continue
        if remove_from_target_chat(key):
            entry["access_revoked"] = True
            entry["revoked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            changed = True
    if changed:
        write_json("paid.json", paid)


def users_store() -> dict[str, Any]:
    data = read_json("users.json", DEFAULT_USERS)
    if not isinstance(data, dict) or "users" not in data or not isinstance(data["users"], dict):
        data = deep_copy(DEFAULT_USERS)
    return data


def save_users(data: dict[str, Any]) -> None:
    write_json("users.json", data)


def maybe_send_users_backup(data: dict[str, Any], total_users: int) -> None:
    if ADMIN_ID is None or total_users <= 0 or total_users % 10 != 0:
        return
    last_backup_count = int(data.get("last_backup_count", 0) or 0)
    if last_backup_count >= total_users:
        return
    result = send_document(
        ADMIN_ID,
        DATA_DIR / "users.json",
        f"<b>Users backup</b>\n\nTotal users: <code>{total_users}</code>",
    )
    if result.get("ok"):
        data["last_backup_count"] = total_users
        save_users(data)


def update_user(user: dict[str, Any]) -> None:
    user_id = str(user.get("id", "")).strip()
    if not user_id:
        return
    data = users_store()
    is_new_user = user_id not in data["users"]
    info = data["users"].get(user_id, {})
    info.update(
        {
            "user_id": int(user_id),
            "username": user.get("username", info.get("username", "")),
            "full_name": " ".join(filter(None, [user.get("first_name", ""), user.get("last_name", "")])).strip(),
            "state": info.get("state", "idle"),
            "last_seen": int(time.time()),
        }
    )
    data["users"][user_id] = info
    save_users(data)
    if is_new_user:
        maybe_send_users_backup(data, len(data["users"]))


def get_user_info(user_id: int | str) -> dict[str, Any]:
    return users_store()["users"].get(str(user_id), {})


def set_user_info(user_id: int | str, **fields: Any) -> None:
    data = users_store()
    key = str(user_id)
    info = data["users"].get(key, {"user_id": int(key)})
    info.update(fields)
    data["users"][key] = info
    save_users(data)


def button_texts() -> dict[str, str]:
    return merge_dict(DEFAULT_SETTINGS["button_texts"], get_settings().get("button_texts", {}))


def get_plans() -> dict[str, dict[str, Any]]:
    raw_plans = get_settings().get("plans", {})
    default_plans = DEFAULT_SETTINGS["plans"]
    if not isinstance(raw_plans, dict):
        raw_plans = {}
    plans: dict[str, dict[str, Any]] = {}
    for plan_id, default_plan in default_plans.items():
        incoming = raw_plans.get(plan_id, {})
        if not isinstance(incoming, dict):
            incoming = {}
        plans[plan_id] = merge_dict(default_plan, incoming)
    return plans


def get_plan(plan_id: str | None) -> dict[str, Any]:
    plans = get_plans()
    if plan_id and plan_id in plans:
        plan = dict(plans[plan_id])
        plan["id"] = plan_id
        return plan
    fallback_id = next(iter(plans))
    plan = dict(plans[fallback_id])
    plan["id"] = fallback_id
    return plan


def plan_duration_text(plan: dict[str, Any]) -> str:
    days = int(plan.get("duration_days", 0) or 0)
    return "Lifetime" if days <= 0 else f"{days} day"


def plan_button_text(plan: dict[str, Any]) -> str:
    return f"{plan.get('name', 'Plan')} - Rs {plan.get('price', '')} - {plan_duration_text(plan)}"


def start_keyboard() -> dict[str, Any]:
    labels = button_texts()
    settings = get_settings()
    rows: list[list[dict[str, Any]]] = []
    demo = str(settings.get("demo_link", "")).strip()
    proof = str(settings.get("proof_link", "")).strip()
    if demo:
        rows.append([{"text": labels["demo"], "url": demo}])
    if proof:
        rows.append([{"text": labels["proofs"], "url": proof}])
    for item in settings.get("extra_channels", [])[:6]:
        if isinstance(item, dict) and item.get("link"):
            rows.append([{"text": labels["join_channel"], "url": item["link"]}])
    rows.append([{"text": labels["premium"], "callback_data": "get_premium", "style": "primary"}])
    return {"inline_keyboard": rows}


def plan_keyboard() -> dict[str, Any]:
    rows = [
        [{"text": plan_button_text(plan), "callback_data": f"select_plan_{plan_id}"}]
        for plan_id, plan in get_plans().items()
    ]
    rows.append([{"text": button_texts()["back"], "callback_data": "back_menu", "style": "danger"}])
    return {"inline_keyboard": rows}


def payment_keyboard(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    labels = button_texts()
    mode = get_settings().get("payment_mode", "manual")
    if mode == "auto":
        return {
            "inline_keyboard": [
                [{"text": labels["private_link"], "callback_data": "check_payment", "style": "success"}],
                [{"text": labels["back"], "callback_data": "back_menu", "style": "danger"}],
            ]
        }
    rows = []
    if plan:
        pay_text = f"Pay Rs {plan.get('price', '')} - {plan.get('name', 'Plan')}"
        rows.append([{"text": pay_text, "url": build_payment_redirect_url(plan)}])
    rows.extend(
        [
            [{"text": labels["verify_payment"], "callback_data": "send_manual_proof", "style": "success"}],
            [{"text": labels["back"], "callback_data": "back_menu", "style": "danger"}],
        ]
    )
    return {
        "inline_keyboard": rows
    }


def payment_text_fallback(plan: dict[str, Any]) -> str:
    settings = get_settings()
    caption = settings.get("payment_text") or PAYMENT_TEXT
    mode = settings.get("payment_mode", "manual")
    amount = str(plan.get("price", "")).strip()
    return (
        f"{caption}\n\nPlan: {plan.get('name')} ({plan_duration_text(plan)})"
        f"\nAmount: Rs {amount}\nMode: {'Auto Merchant' if mode == 'auto' else 'Manual UPI'}"
        f"\n\nUPI ID: <code>{settings.get('upi_id', '')}</code>"
        "\nPayment ke baad VERIFY PAYMENT dabao aur screenshot ya UTR bhejo."
    )


def send_start(chat_id: int | str) -> None:
    settings = get_settings()
    caption = settings.get("start_text") or START_TEXT
    image = str(settings.get("start_image", "")).strip()
    if image:
        response = send_photo(chat_id, image, caption, start_keyboard())
        if response.get("ok"):
            return
    send_message(chat_id, caption, start_keyboard())


def build_upi_link(plan: dict[str, Any]) -> str:
    settings = get_settings()
    amount = str(plan.get("price", "")).strip()
    upi_id = str(settings.get("upi_id", "")).strip()
    note_base = str(settings.get("payment_note", "Payment")).strip() or "Payment"
    note = f"{note_base} - {plan.get('name', 'Plan')}"
    encoded_note = quote(note, safe="")
    encoded_upi = quote(upi_id, safe="")
    return f"upi://pay?pa={encoded_upi}&pn=Payment&am={amount}&cu=INR&tn={encoded_note}"


def build_payment_redirect_url(plan: dict[str, Any]) -> str:
    settings = get_settings()
    amount = str(plan.get("price", "")).strip()
    template = str(plan.get("redirect_url", "")).strip()
    upi_link = build_upi_link(plan)
    if not template:
        return upi_link
    if not any(token in template for token in ("{amount}", "{plan}", "{plan_name}", "{duration}", "{upi_id}", "{note}", "{upi_link}")):
        parts = urlsplit(template)
        if parts.path.rstrip("/").endswith(f"/{amount}"):
            return template
        path = f"{parts.path.rstrip('/')}/{quote(amount, safe='')}"
        return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
    return (
        template
        .replace("{amount}", quote(str(amount), safe=""))
        .replace("{plan}", quote(str(plan.get("id", "")), safe=""))
        .replace("{plan_name}", quote(str(plan.get("name", "")), safe=""))
        .replace("{duration}", quote(plan_duration_text(plan), safe=""))
        .replace("{upi_id}", quote(str(settings.get("upi_id", "")).strip(), safe=""))
        .replace("{note}", quote(str(settings.get("payment_note", "Payment")).strip() or "Payment", safe=""))
        .replace("{upi_link}", quote(upi_link, safe=""))
    )


def qr_image_for_data(data: str) -> str:
    return f"https://api.qrserver.com/v1/create-qr-code/?size=320x320&data={quote(data, safe='')}"


def ensure_auto_session(user_id: int | str, plan: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    amount = str(plan.get("price", "")).strip()
    upi_id = str(settings.get("upi_id", "")).strip()
    merchant_mid = str(settings.get("merchant_mid", "")).strip()
    note_base = str(settings.get("payment_note", "Premium Access")).strip() or "Premium Access"
    note = f"{note_base} - {plan.get('name', 'Plan')}"
    if not amount:
        raise RuntimeError("Price set nahi hai.")
    if not upi_id:
        raise RuntimeError("UPI ID set nahi hai.")
    if not merchant_mid:
        raise RuntimeError("Merchant MID set nahi hai.")

    auto_data = read_json("auto_payment.json", DEFAULT_AUTO_PAYMENT)
    key = str(user_id)
    existing = auto_data.get(key)
    if isinstance(existing, dict) and existing.get("status") == "pending":
        created_at = int(existing.get("created_at", 0) or 0)
        if existing.get("plan_id") == plan.get("id") and time.time() - created_at < 1800:
            return existing

    try:
        response = requests.get(
            "https://payment.pikaapis.workers.dev/",
            params={"id": merchant_mid, "upi": upi_id, "amount": amount, "note": note},
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Merchant QR generate nahi hua: {exc}") from exc

    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or "Merchant QR generate nahi hua.")

    session_data = {
        "track_id": data.get("trackId", ""),
        "plan_id": plan.get("id", ""),
        "plan_name": plan.get("name", ""),
        "duration_days": plan.get("duration_days", 0),
        "amount": amount,
        "qr_image_url": data.get("qrImageUrl", ""),
        "status": "pending",
        "claimed": False,
        "created_at": int(time.time()),
    }
    auto_data[key] = session_data
    write_json("auto_payment.json", auto_data)
    return session_data


def send_plan_list(chat_id: int | str) -> None:
    lines = ["<b>Choose Your Plan</b>"]
    for plan in get_plans().values():
        lines.append(f"\n<b>{plan.get('name')}</b> - Rs {plan.get('price')} - {plan_duration_text(plan)}")
    send_message(chat_id, "\n".join(lines), plan_keyboard())


def send_payment_details(chat_id: int | str, user_id: int | str, plan_id: str) -> None:
    settings = get_settings()
    plan = get_plan(plan_id)
    amount = str(plan.get("price", "")).strip() or "99"
    mode = settings.get("payment_mode", "manual")
    caption = settings.get("payment_text") or PAYMENT_TEXT
    caption = (
        f"{caption}\n\nPlan: {plan.get('name')} ({plan_duration_text(plan)})"
        f"\nAmount: Rs {amount}\nMode: {'Auto Merchant' if mode == 'auto' else 'Manual UPI'}"
    )
    set_user_info(user_id, selected_plan=plan.get("id"))

    if mode == "auto":
        session_data = ensure_auto_session(user_id, plan)
        qr_url = session_data.get("qr_image_url", "")
        if qr_url:
            response = send_photo(chat_id, qr_url, caption, payment_keyboard(plan))
            if response.get("ok"):
                return
        response = send_message(chat_id, caption, payment_keyboard(plan))
        if response.get("ok"):
            return
        raise RuntimeError(response.get("description") or "Payment details send nahi ho paye.")
        return

    upi_link = build_upi_link(plan)
    qr_url = qr_image_for_data(upi_link)
    extra = (
        f"\n\nUPI ID: <code>{get_settings().get('upi_id', '')}</code>"
        "\nPayment ke baad VERIFY PAYMENT dabao aur screenshot ya UTR bhejo."
    )
    response = send_photo(chat_id, qr_url, caption + extra, payment_keyboard(plan))
    if response.get("ok"):
        return
    response = send_message(chat_id, payment_text_fallback(plan), payment_keyboard(plan))
    if response.get("ok"):
        return
    raise RuntimeError(response.get("description") or "Payment details send nahi ho paye.")


def append_transaction(entry: dict[str, Any]) -> None:
    items = read_json("transactions.json", DEFAULT_TRANSACTIONS)
    if not isinstance(items, list):
        items = []
    items.append(entry)
    write_json("transactions.json", items[-500:])


def plan_expiry_timestamp(plan: dict[str, Any]) -> int | None:
    days = int(plan.get("duration_days", 0) or 0)
    if days <= 0:
        return None
    return int(time.time()) + days * 86400


def mark_paid(user_id: int | str, mode: str, transaction_ref: str, plan_id: str | None = None) -> str | None:
    plan = get_plan(plan_id or str(get_user_info(user_id).get("selected_plan", "")))
    invite_link = create_invite_link()
    if not invite_link:
        return None
    paid = read_json("paid.json", DEFAULT_PAID)
    key = str(user_id)
    info = get_user_info(user_id)
    access_expires_at = plan_expiry_timestamp(plan)
    paid[key] = {
        "user_id": int(key),
        "username": info.get("username", ""),
        "approved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "plan_id": plan.get("id", ""),
        "plan_name": plan.get("name", ""),
        "amount": plan.get("price", ""),
        "duration_days": plan.get("duration_days", 0),
        "access_expires_at": access_expires_at,
        "access_expires_on": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(access_expires_at)) if access_expires_at else "lifetime",
        "transaction_ref": transaction_ref,
        "invite_link": invite_link,
    }
    write_json("paid.json", paid)
    append_transaction(paid[key])
    return invite_link


def verify_auto_payment(user_id: int | str) -> tuple[bool, str]:
    settings = get_settings()
    merchant_mid = str(settings.get("merchant_mid", "")).strip()
    if not merchant_mid:
        return False, "Merchant MID set nahi hai."

    auto_data = read_json("auto_payment.json", DEFAULT_AUTO_PAYMENT)
    key = str(user_id)
    session_data = auto_data.get(key)
    if not isinstance(session_data, dict):
        return False, "Auto payment session missing hai. Naya QR generate karo."
    if session_data.get("claimed"):
        return False, "Payment already claim ho chuka hai."

    try:
        response = requests.get(
            "https://verify.pikaapis.workers.dev/",
            params={"id": merchant_mid, "trn": session_data.get("track_id", "")},
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return False, "Payment verify service tak reach nahi hua."

    status = str(data.get("STATUS", "")).upper()
    if status in {"FAILURE", "TXN_FAILED"}:
        return False, "Payment failed dikh raha hai."
    if status == "PENDING":
        return False, "Payment abhi pending hai."
    if status != "TXN_SUCCESS":
        return False, "Payment abhi receive nahi hua."
    if str(data.get("TXNAMOUNT", "")) != str(session_data.get("amount", "")):
        return False, f"Amount mismatch. Expected Rs {session_data.get('amount')}"

    invite_link = mark_paid(user_id, "auto", str(session_data.get("track_id", "")), str(session_data.get("plan_id", "")))
    if not invite_link:
        return False, "Target channel ID set nahi hai."
    session_data["status"] = "paid"
    session_data["claimed"] = True
    auto_data[key] = session_data
    write_json("auto_payment.json", auto_data)
    set_user_info(user_id, state="idle")
    return True, invite_link


def forward_manual_review(user_id: int | str, proof_type: str, proof_value: str, caption: str = "") -> None:
    user_info = get_user_info(user_id)
    plan = get_plan(str(user_info.get("selected_plan", "")))
    caption_text = (
        "<b>Manual Payment Review</b>\n\n"
        f"User ID: <code>{user_id}</code>\n"
        f"Username: @{user_info.get('username', 'unknown')}\n"
        f"Plan: <b>{plan.get('name')}</b> | Rs {plan.get('price')} | {plan_duration_text(plan)}\n"
        f"Type: {proof_type}\n"
    )
    if proof_type == "photo":
        if caption:
            caption_text += f"Caption: {caption}\n"
        bot_api(
            "sendPhoto",
            {
                "chat_id": ADMIN_ID,
                "photo": proof_value,
                "caption": caption_text,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "Approve", "callback_data": f"approve_{user_id}", "style": "success"},
                        {"text": "Reject", "callback_data": f"reject_{user_id}", "style": "danger"},
                    ]]
                },
            },
        )
        return
    caption_text += f"Proof: <code>{proof_value}</code>"
    send_message(
        ADMIN_ID,
        caption_text,
        {
            "inline_keyboard": [[
                {"text": "Approve", "callback_data": f"approve_{user_id}", "style": "success"},
                {"text": "Reject", "callback_data": f"reject_{user_id}", "style": "danger"},
            ]]
        },
    )


def approve_manual_payment(user_id: int | str) -> tuple[bool, str]:
    info = get_user_info(user_id)
    ref = str(info.get("last_manual_proof", "manual-approved"))
    plan = get_plan(str(info.get("selected_plan", "")))
    invite_link = mark_paid(user_id, "manual", ref, str(plan.get("id", "")))
    if not invite_link:
        return False, "Target channel ID set nahi hai."
    set_user_info(user_id, state="idle", last_manual_proof=ref)
    send_message(
        user_id,
        f"<b>Payment approved.</b>\n\n"
        f"Plan: <b>{plan.get('name')}</b> ({plan_duration_text(plan)})\n"
        f"Yeh raha aapka private link:\n{invite_link}",
    )
    return True, invite_link


def reject_manual_payment(user_id: int | str) -> None:
    set_user_info(user_id, state="idle")
    send_message(user_id, "<b>Payment rejected.</b>\n\nClear screenshot ya sahi UTR ke saath dubara bhejo.")


def settings_summary() -> str:
    settings = get_settings()
    plan_lines = "\n".join(
        f"- {plan_id}: Rs {plan.get('price')} | {plan_duration_text(plan)} | {plan.get('redirect_url') or '-'}"
        for plan_id, plan in get_plans().items()
    )
    return (
        "<b>Admin Panel</b>\n\n"
        f"Admin ID: <code>{ADMIN_ID}</code>\n"
        f"Mode: <code>{settings.get('payment_mode')}</code>\n"
        f"Plans:\n<code>{plan_lines}</code>\n"
        f"UPI: <code>{settings.get('upi_id') or '-'}</code>\n"
        f"MID: <code>{settings.get('merchant_mid') or '-'}</code>\n"
        f"Demo: <code>{settings.get('demo_link') or '-'}</code>\n"
        f"Proof: <code>{settings.get('proof_link') or '-'}</code>\n"
        f"Target Channel: <code>{settings.get('target_channel_id') or '-'}</code>\n"
        f"Users: <code>{len(users_store().get('users', {}))}</code>\n\n"
        "Commands:\n"
        "!mode manual or !mode auto\n"
        "!setplanlink basic https://...\n"
        "!setupi yourupi@bank\n"
        "!setmid MID\n"
        "!settarget -100...\n"
        "!setdemo https://...\n"
        "!setproof https://...\n"
        "!setimage https://...\n"
        "!setstart your text\n"
        "!setpaymenttext your text\n"
        "!setnote Premium Access\n"
        "!addchannel https://...\n"
        "!delchannel 1\n"
        "!broadcast message"
    )


def admin_help_text() -> str:
    settings = get_settings()
    plan_lines = "\n".join(
        f"<code>{plan_id}</code> - Rs {plan.get('price')} - {plan_duration_text(plan)}"
        for plan_id, plan in get_plans().items()
    )
    return (
        "<b>Admin Help</b>\n\n"
        "Yeh bot Telegram se hi fully manage hoga. Sirf admin commands se settings change hongi.\n\n"
        "<b>Current Setup</b>\n"
        f"Mode: <code>{settings.get('payment_mode')}</code>\n"
        f"Plans:\n{plan_lines}\n"
        f"UPI: <code>{settings.get('upi_id') or '-'}</code>\n"
        f"MID: <code>{settings.get('merchant_mid') or '-'}</code>\n"
        f"Target Channel: <code>{settings.get('target_channel_id') or '-'}</code>\n\n"
        "<b>Main Commands</b>\n"
        "<code>!admin</code> - current settings aur quick status dikhata hai\n"
        "<code>!help</code> - yeh full help message dikhata hai\n"
        "<code>!broadcast your message</code> - sab users ko message bhejta hai\n\n"
        "<code>!backupusers</code> - current users.json admin chat me document ke form me bhejta hai\n\n"
        "<b>Payment Mode Commands</b>\n"
        "<code>!mode manual</code> - normal UPI payment + screenshot/UTR + admin approve/reject\n"
        "<code>!mode auto</code> - merchant detect payment mode on karta hai\n"
        "<code>!setnote Premium Access</code> - payment note/remark set karta hai\n"
        "<code>!setplanlink basic https://...</code> - plan ka redirect link set karta hai\n"
        "<code>!setupi xlgr@ptyes</code> - UPI ID set karta hai\n"
        "<code>!setmid YOUR_MID</code> - merchant MID set karta hai, auto mode ke liye zaroori\n\n"
        "<b>Channel And Links</b>\n"
        "<code>!settarget -100...</code> - private channel/group ID set karta hai jahan se invite link banega\n"
        "<code>!setdemo https://...</code> - demo button ka link set karta hai\n"
        "<code>!setproof https://...</code> - proof button ka link set karta hai\n"
        "<code>!addchannel https://...</code> - extra join channel button add karta hai\n"
        "<code>!delchannel 1</code> - extra channel list me given number wala item remove karta hai\n\n"
        "<b>Content Commands</b>\n"
        "<code>!setimage https://...</code> - start screen image set karta hai\n"
        "<code>!setstart your text</code> - /start par dikhne wala message set karta hai\n"
        "<code>!setpaymenttext your text</code> - payment page ka caption set karta hai\n\n"
        "<b>Manual Payment Flow</b>\n"
        "1. <code>!mode manual</code> use karo\n"
        "2. User plan choose karega aur Pay button se us plan ke redirect link par jayega\n"
        "3. User payment karega aur VERIFY PAYMENT dabayega\n"
        "4. User screenshot ya UTR bhejega\n"
        "5. Admin ko Approve/Reject buttons milenge\n"
        "6. Approve par private invite link user ko chala jayega\n\n"
        "<b>Auto Payment Flow</b>\n"
        "1. <code>!mode auto</code> use karo\n"
        "2. <code>!setupi</code> aur <code>!setmid</code> dono set hone chahiye\n"
        "3. User ke liye merchant QR generate hoga\n"
        "4. User GET PRIVATE LINK button se verify karega\n"
        "5. Successful payment par link automatically mil jayega\n\n"
        "<b>UPI QR Format</b>\n"
        "Manual mode me QR is type ke UPI link se banta hai:\n"
        "<code>upi://pay?pa=BHARATPE2J0U0Z1Z5J72815@unitype&pn=Payment&am=49&cu=INR</code>\n\n"
        "<b>Note</b>\n"
        "Approve/Reject button sirf admin ke liye kaam karega. Normal user settings change nahi kar sakta."
    )


def handle_admin_command(message: dict[str, Any], text: str) -> bool:
    chat_id = message["chat"]["id"]
    command, _, arg = text.partition(" ")
    arg = arg.strip()
    settings = get_settings()

    if command == "!admin":
        send_message(chat_id, settings_summary())
        return True
    if command == "!help":
        send_message(chat_id, admin_help_text())
        return True
    if command == "!backupusers":
        total_users = len(users_store().get("users", {}))
        result = send_document(
            chat_id,
            DATA_DIR / "users.json",
            f"<b>Manual users backup</b>\n\nTotal users: <code>{total_users}</code>",
        )
        if result.get("ok"):
            send_message(chat_id, "Users backup bhej diya gaya hai.")
        else:
            send_message(chat_id, result.get("description") or "Users backup send nahi ho paya.")
        return True
    if command == "!mode" and arg.lower() in {"manual", "auto"}:
        settings["payment_mode"] = arg.lower()
        save_settings(settings)
        send_message(chat_id, f"Payment mode set to <b>{arg.lower()}</b>.")
        return True
    if command == "!setupi" and arg:
        settings["upi_id"] = arg
        save_settings(settings)
        send_message(chat_id, f"UPI updated to <code>{arg}</code>.")
        return True
    if command == "!setmid" and arg:
        settings["merchant_mid"] = arg
        save_settings(settings)
        send_message(chat_id, f"Merchant MID updated to <code>{arg}</code>.")
        return True
    if command == "!settarget" and arg:
        settings["target_channel_id"] = arg
        save_settings(settings)
        send_message(chat_id, "Target channel updated.")
        return True
    if command == "!setdemo" and arg:
        settings["demo_link"] = arg
        save_settings(settings)
        send_message(chat_id, "Demo link updated.")
        return True
    if command == "!setproof" and arg:
        settings["proof_link"] = arg
        save_settings(settings)
        send_message(chat_id, "Proof link updated.")
        return True
    if command == "!setimage" and arg:
        settings["start_image"] = arg
        save_settings(settings)
        send_message(chat_id, "Start image updated.")
        return True
    if command == "!setstart" and arg:
        settings["start_text"] = arg
        save_settings(settings)
        send_message(chat_id, "Start text updated.")
        return True
    if command == "!setpaymenttext" and arg:
        settings["payment_text"] = arg
        save_settings(settings)
        send_message(chat_id, "Payment text updated.")
        return True
    if command == "!setnote" and arg:
        settings["payment_note"] = arg
        save_settings(settings)
        send_message(chat_id, "Payment note updated.")
        return True
    if command == "!setplanlink" and arg:
        plan_id, _, link = arg.partition(" ")
        plan_id = plan_id.strip().lower()
        link = link.strip()
        plans = get_plans()
        if plan_id not in plans or not link:
            send_message(chat_id, "Use: <code>!setplanlink basic https://...</code>\nPlans: basic, standard, premium, vip")
            return True
        settings["plans"] = plans
        settings["plans"][plan_id]["redirect_url"] = link
        save_settings(settings)
        send_message(chat_id, f"{plans[plan_id].get('name')} redirect URL updated.")
        return True
    if command == "!addchannel" and arg:
        channels = settings.get("extra_channels", [])
        channels.append({"link": arg, "added_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        settings["extra_channels"] = channels[-10:]
        save_settings(settings)
        send_message(chat_id, "Extra channel added.")
        return True
    if command == "!delchannel" and arg.isdigit():
        index = int(arg) - 1
        channels = settings.get("extra_channels", [])
        if 0 <= index < len(channels):
            channels.pop(index)
            settings["extra_channels"] = channels
            save_settings(settings)
            send_message(chat_id, "Extra channel removed.")
        else:
            send_message(chat_id, "Invalid channel index.")
        return True
    if command == "!broadcast" and arg:
        recipients = list(users_store().get("users", {}).keys())
        sent = 0
        for user_id in recipients:
            response = send_message(user_id, arg)
            if response.get("ok"):
                sent += 1
            time.sleep(0.05)
        send_message(chat_id, f"Broadcast complete. Sent: {sent}/{len(recipients)}")
        return True
    return False


def handle_start(message: dict[str, Any]) -> None:
    send_start(message["chat"]["id"])


def handle_text_message(message: dict[str, Any]) -> None:
    chat_id = message["chat"]["id"]
    user = message.get("from") or {}
    user_id = user.get("id")
    text = (message.get("text") or "").strip()
    update_user(user)

    if text.startswith("/start"):
        handle_start(message)
        return

    if is_admin(user_id) and text.startswith("!") and handle_admin_command(message, text):
        return

    if text.startswith("!"):
        if is_admin_command(text):
            send_message(chat_id, "Yeh command sirf admin use kar sakta hai.")
            return
        send_message(chat_id, "Normal users ke liye sirf /start available hai.")
        return

    if text.startswith("/"):
        if is_admin_command("!" + text[1:]):
            send_message(chat_id, "Admin commands ab ! prefix se chalti hain.")
            return
        send_message(chat_id, "Normal users ke liye sirf /start available hai.")
        return

    info = get_user_info(user_id)
    state = info.get("state", "idle")
    mode = get_settings().get("payment_mode", "manual")

    if state == "awaiting_manual_proof" and mode == "manual":
        set_user_info(user_id, state="pending_admin_review", last_manual_proof=text)
        forward_manual_review(user_id, "text", text)
        send_message(chat_id, "Proof admin ko bhej diya gaya hai. Approval ke baad private link milega.")
        return

    send_start(chat_id)


def handle_photo_message(message: dict[str, Any]) -> None:
    chat_id = message["chat"]["id"]
    user = message.get("from") or {}
    user_id = user.get("id")
    update_user(user)
    info = get_user_info(user_id)
    if info.get("state") != "awaiting_manual_proof":
        send_message(chat_id, "Pehle payment flow open karo aur VERIFY PAYMENT dabao.")
        return
    photos = message.get("photo") or []
    if not photos:
        send_message(chat_id, "Photo read nahi hua. Dobara bhejo.")
        return
    file_id = photos[-1].get("file_id")
    set_user_info(user_id, state="pending_admin_review", last_manual_proof=file_id)
    forward_manual_review(user_id, "photo", file_id, message.get("caption", ""))
    send_message(chat_id, "Screenshot admin ko bhej diya gaya hai. Approval ke baad private link milega.")


def handle_callback_query(callback_query: dict[str, Any]) -> None:
    data = callback_query.get("data", "")
    callback_id = callback_query.get("id", "")
    message = callback_query.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    user = callback_query.get("from") or {}
    user_id = user.get("id")
    update_user(user)

    if data == "back_menu":
        answer_callback(callback_id)
        if chat_id:
            send_start(chat_id)
        return

    if data == "get_premium":
        answer_callback(callback_id)
        if chat_id:
            send_plan_list(chat_id)
        return

    if data.startswith("select_plan_"):
        plan_id = data.split("select_plan_", 1)[1]
        answer_callback(callback_id)
        try:
            send_payment_details(chat_id, user_id, plan_id)
        except RuntimeError as exc:
            if chat_id:
                send_message(chat_id, str(exc))
        return

    if data == "send_manual_proof":
        info = get_user_info(user_id)
        if not info.get("selected_plan"):
            set_user_info(user_id, selected_plan=get_plan(None).get("id"))
        set_user_info(user_id, state="awaiting_manual_proof")
        answer_callback(callback_id)
        if chat_id:
            send_message(chat_id, "Screenshot ya UTR bhejo. Admin manually approve ya reject karega.")
        return

    if data == "check_payment":
        answer_callback(callback_id)
        ok, result = verify_auto_payment(user_id)
        if chat_id:
            if ok:
                send_message(chat_id, f"Payment successful. Yeh raha aapka private link:\n{result}")
            else:
                send_message(chat_id, result)
        return

    if data.startswith("approve_"):
        if not is_admin(user_id):
            answer_callback(callback_id, "Access denied", True)
            return
        target_user_id = data.split("_", 1)[1]
        ok, result = approve_manual_payment(target_user_id)
        answer_callback(callback_id, "Approved" if ok else result, not ok)
        if chat_id:
            send_message(chat_id, f"Approval result: {result}")
        return

    if data.startswith("reject_"):
        if not is_admin(user_id):
            answer_callback(callback_id, "Access denied", True)
            return
        target_user_id = data.split("_", 1)[1]
        reject_manual_payment(target_user_id)
        answer_callback(callback_id, "Rejected")
        if chat_id:
            send_message(chat_id, f"Payment rejected for user {target_user_id}.")
        return

    answer_callback(callback_id)


def set_bot_commands() -> None:
    public_commands = [
        {"command": "start", "description": "Open user menu"},
    ]
    bot_api("setMyCommands", {"commands": public_commands})
    if ADMIN_ID is not None:
        bot_api(
            "setMyCommands",
            {
                "scope": {"type": "chat", "chat_id": ADMIN_ID},
                "commands": public_commands,
            },
        )


def process_update(update: dict[str, Any]) -> None:
    if message := update.get("message"):
        if message.get("photo"):
            handle_photo_message(message)
        else:
            handle_text_message(message)
    elif callback_query := update.get("callback_query"):
        handle_callback_query(callback_query)


def poll_forever() -> None:
    offset = 0
    last_expiry_check = 0.0
    while True:
        if time.time() - last_expiry_check >= 60:
            enforce_expired_access()
            last_expiry_check = time.time()
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"timeout": POLL_TIMEOUT, "offset": offset},
                timeout=POLL_TIMEOUT + 10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:
            time.sleep(3)
            continue

        for update in data.get("result", []):
            offset = update["update_id"] + 1
            process_update(update)


def delete_webhook(drop_pending_updates: bool = False) -> dict[str, Any]:
    return bot_api(
        "deleteWebhook",
        {"drop_pending_updates": drop_pending_updates},
    )


def main() -> None:
    if MISSING_REQUIRED_CONFIG:
        missing = ", ".join(MISSING_REQUIRED_CONFIG)
        raise RuntimeError(
            f"Missing required config: {missing}. Fill .env."
        )
    delete_result = delete_webhook(drop_pending_updates=False)
    if delete_result.get("ok"):
        print("Telegram webhook cleared; starting long polling.")
    else:
        print(f"Webhook clear failed: {delete_result.get('description', delete_result)}")
    set_bot_commands()
    print(f"Bot running with admin ID {ADMIN_ID or 'not-set'} and data dir {DATA_DIR}")
    poll_forever()


if __name__ == "__main__":
    main()
