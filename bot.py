import requests
import time
import json
import os
from threading import Thread
from collections import defaultdict

BOT_TOKEN = "8201593101:AAH6g634OPKkLTrDNjPRyPwujua4COECZ7c"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOT_USERNAME = "TrrTTrrbot"

session = requests.Session()

DATA_FILE = "bot_data.json"

def load_all_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_all_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except:
        pass

bot_data = load_all_data()

DEFAULTS = {
    "config": {},
    "waiting_users": {},
    "spam_records": {},
    "group_settings": {}
}

for key, default_value in DEFAULTS.items():
    if key not in bot_data:
        bot_data[key] = default_value

config = bot_data["config"]
waiting_users = bot_data["waiting_users"]
spam_records = bot_data["spam_records"]
group_settings = bot_data["group_settings"]

SPAM_LIMIT = 3
SPAM_SECONDS = 4
MUTE_SECONDS = 60

def save():
    bot_data["config"] = config
    bot_data["waiting_users"] = waiting_users
    bot_data["spam_records"] = spam_records
    bot_data["group_settings"] = group_settings
    save_all_data(bot_data)

def is_spam(user_id, chat_id):
    key = f"{chat_id}_{user_id}"
    now = time.time()
    
    if key not in spam_records:
        spam_records[key] = []
    
    spam_records[key] = [t for t in spam_records[key] if now - t < SPAM_SECONDS]
    spam_records[key].append(now)
    save()
    
    return len(spam_records[key]) > SPAM_LIMIT

def mute_user(chat_id, user_id, seconds=MUTE_SECONDS):
    try:
        until_date = int(time.time()) + seconds if seconds > 0 else 2147483647
        session.post(f"{API_URL}/restrictChatMember", json={
            'chat_id': chat_id,
            'user_id': user_id,
            'until_date': until_date,
            'permissions': {
                'can_send_messages': False,
                'can_send_media_messages': False,
                'can_send_other_messages': False,
                'can_add_web_page_previews': False
            }
        }, timeout=0.3)
    except:
        pass

def delete_msg(chat_id, msg_id):
    try:
        session.post(f"{API_URL}/deleteMessage", 
                    json={'chat_id': chat_id, 'message_id': msg_id}, 
                    timeout=0.2)
    except:
        pass

def send_msg(chat_id, text, reply_markup=None):
    try:
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if reply_markup:
            data['reply_markup'] = reply_markup
        session.post(f"{API_URL}/sendMessage", json=data, timeout=0.3)
    except:
        pass

def demote_admin(chat_id, user_id):
    try:
        session.post(f"{API_URL}/promoteChatMember", json={
            'chat_id': chat_id,
            'user_id': user_id,
            'can_post_messages': False,
            'can_edit_messages': False,
            'can_delete_messages': False,
            'can_invite_users': False,
            'can_restrict_members': False,
            'can_pin_messages': False,
            'can_promote_members': False,
            'can_change_info': False,
            'can_manage_voice_chats': False
        }, timeout=0.3)
        return True
    except:
        return False

def is_admin(chat_id, user_id):
    try:
        r = session.post(f"{API_URL}/getChatMember", json={'chat_id': chat_id, 'user_id': user_id}, timeout=0.3)
        data = r.json()
        if data.get('ok'):
            status = data['result'].get('status')
            return status in ['administrator', 'creator']
        return False
    except:
        return False

def start_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "➕ اضافة البوت", "url": f"https://t.me/{BOT_USERNAME}?startgroup=new"}],
            [{"text": "👑 رفع مشرف", "callback_data": "promote"}],
            [{"text": "📋 الممنوعات", "callback_data": "features"}]
        ]
    }

def cancel_keyboard():
    return {"inline_keyboard": [[{"text": "❌ الغاء", "callback_data": "cancel"}]]}

def role_keyboard(group_id):
    return {
        "inline_keyboard": [
            [{"text": "🎤 مشرف صوتي", "callback_data": f"voice_{group_id}"}],
            [{"text": "👑 مشرف كامل", "callback_data": f"full_{group_id}"}],
            [{"text": "❌ الغاء", "callback_data": "cancel"}]
        ]
    }

def check_forbidden(msg):
    if 'photo' in msg:
        return True, "صورة"
    if 'sticker' in msg:
        return True, "ملصق"
    if 'video' in msg:
        return True, "فيديو"
    if 'animation' in msg:
        return True, "GIF متحرك"
    if 'document' in msg:
        return True, "ملف"
    if 'contact' in msg:
        return True, "جهة اتصال"
    if 'text' in msg:
        text = msg.get('text', '').lower()
        if 'http://' in text or 'https://' in text or 'www.' in text or 't.me/' in text:
            return True, "رابط"
    return False, None

def handle_violation(chat_id, user_id, user_name, v_type, msg_id):
    delete_msg(chat_id, msg_id)
    
    if is_admin(chat_id, user_id):
        demote_admin(chat_id, user_id)
        send_msg(chat_id, f"⚠️ تم تنزيل المشرف {user_name} بسبب مخالفة: {v_type}!")
        Thread(target=notify_owner_demote, args=(chat_id, user_id, user_name, v_type), daemon=True).start()
    else:
        if is_spam(user_id, chat_id):
            mute_user(chat_id, user_id, MUTE_SECONDS)
            send_msg(chat_id, f"⚠️ {user_name} تم كتمك بسبب تكرار المخالفات!")
        else:
            send_msg(chat_id, f"⚠️ {user_name} ممنوع ارسال {v_type}!", None)
    
    Thread(target=notify_owner, args=(chat_id, user_id, user_name, v_type), daemon=True).start()

def notify_owner_demote(chat_id, user_id, user_name, v_type):
    try:
        r = session.post(f"{API_URL}/getChatAdministrators", json={'chat_id': chat_id}, timeout=0.5)
        admins = r.json()
        if admins.get('ok'):
            for admin in admins['result']:
                if admin.get('status') == 'creator':
                    session.post(f"{API_URL}/sendMessage", json={
                        'chat_id': admin['user']['id'],
                        'text': f"⚠️⚠️ تنبيه مهم ⚠️⚠️\n\nتم تنزيل مشرف مخالف:\nمجموعة: {chat_id}\nالمشرف: {user_name}\nالمخالفة: {v_type}\n\nتمت إزالته من الإدارة فوراً!",
                    }, timeout=0.2)
                    break
    except:
        pass

def notify_owner(chat_id, user_id, user_name, v_type):
    try:
        r = session.post(f"{API_URL}/getChatAdministrators", json={'chat_id': chat_id}, timeout=0.5)
        admins = r.json()
        if admins.get('ok'):
            for admin in admins['result']:
                if admin.get('status') == 'creator':
                    session.post(f"{API_URL}/sendMessage", json={
                        'chat_id': admin['user']['id'],
                        'text': f"🛡️ تم حذف مخالفة\nمجموعة: {chat_id}\nعضو: {user_name}\nنوع: {v_type}",
                    }, timeout=0.2)
                    break
    except:
        pass

def handle_callback(call):
    data = call.get('data')
    chat_id = call.get('message', {}).get('chat', {}).get('id')
    msg_id = call.get('message', {}).get('message_id')
    user_id = call.get('from', {}).get('id')
    
    delete_msg(chat_id, msg_id)
    
    if data == "features":
        send_msg(chat_id, 
                "🚫 الممنوعات:\n\n"
                "❌ صور\n"
                "❌ ملصقات\n"
                "❌ فيديوهات\n"
                "❌ روابط\n"
                "❌ صور متحركة GIF\n"
                "❌ ملفات\n"
                "❌ جهات اتصال\n\n"
                "👑 المشرف المخالف:\n"
                "✓ يتم تنزيله فوراً\n"
                "✓ حذف مخالفته\n"
                "✓ إشعار المالك\n\n"
                "✅ المسموح:\n"
                "✓ نصوص (بدون روابط)\n"
                "✓ رسائل صوتية\n"
                "✓ استيكرات صوتية", 
                start_keyboard())
    
    elif data == "promote":
        waiting_users[str(user_id)] = {'action': 'waiting_group'}
        save()
        send_msg(chat_id, "ارسل معرف المجموعة:\nمثال: -100123456789", cancel_keyboard())
    
    elif data == "cancel":
        if str(user_id) in waiting_users:
            del waiting_users[str(user_id)]
            save()
        send_msg(chat_id, "تم الغاء", start_keyboard())
    
    elif data.startswith("voice_") or data.startswith("full_"):
        parts = data.split("_")
        role = parts[0]
        group_id = "_".join(parts[1:])
        waiting_users[str(user_id)] = {'action': 'waiting_user', 'group': group_id, 'role': role}
        save()
        send_msg(chat_id, "ارسل معرف العضو:\nمثال: @username او 123456789", cancel_keyboard())

def handle_message(msg):
    user_id = msg.get('from', {}).get('id')
    if not user_id:
        return
    
    user_name = msg.get('from', {}).get('first_name', 'Unknown')
    chat_id = msg.get('chat', {}).get('id')
    msg_id = msg.get('message_id')
    text = msg.get('text', '').strip() if 'text' in msg else ''
    chat_type = msg.get('chat', {}).get('type')
    
    if text == '/start':
        send_msg(chat_id, "🚀 بوت حماية المجموعات\n\nيمنع:\n📷 صور\n🎬 فيديوهات\n🎨 ملصقات\n🔗 روابط\n📁 ملفات\n📞 جهات اتصال\n\n👑 المشرف المخالف يتم تنزيله فوراً", start_keyboard())
        return
    
    user_key = str(user_id)
    if user_key in waiting_users:
        info = waiting_users[user_key]
        
        if info.get('action') == 'waiting_group':
            if not text.startswith('-'):
                send_msg(chat_id, "❌ خطأ! المعرف يبدأ بـ -", cancel_keyboard())
                return
            del waiting_users[user_key]
            save()
            send_msg(chat_id, "اختر الصلاحية:", role_keyboard(text))
            return
        
        elif info.get('action') == 'waiting_user':
            target_id = int(text) if text.isdigit() else text
            if target_id:
                role = info.get('role')
                if role == 'voice':
                    permissions = {'can_manage_voice_chats': True}
                else:
                    permissions = {
                        'can_change_info': True, 'can_delete_messages': True,
                        'can_invite_users': True, 'can_restrict_members': True,
                        'can_pin_messages': True, 'can_manage_voice_chats': True
                    }
                
                try:
                    result = session.post(f"{API_URL}/promoteChatMember", json={
                        'chat_id': info.get('group'), 'user_id': target_id, **permissions
                    }, timeout=0.5)
                    
                    if result.json().get('ok'):
                        send_msg(chat_id, "✅ تم رفع العضو بنجاح")
                    else:
                        send_msg(chat_id, "❌ فشل رفع العضو")
                except:
                    send_msg(chat_id, "❌ خطأ في الاتصال")
                
                del waiting_users[user_key]
                save()
                send_msg(chat_id, "القائمة الرئيسية", start_keyboard())
            return
    
    if chat_type in ['group', 'supergroup']:
        if text and text.startswith('/'):
            return
        
        is_forbidden, v_type = check_forbidden(msg)
        if is_forbidden:
            handle_violation(chat_id, user_id, user_name, v_type, msg_id)

print("⚡️ بوت الحماية شغال...")
last_id = 0

while True:
    try:
        response = session.get(f"{API_URL}/getUpdates", 
                              params={'timeout': 10, 'offset': last_id + 1, 'allowed_updates': 'message,callback_query'}, 
                              timeout=12)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                for update in data.get('result', []):
                    last_id = update.get('update_id', last_id) + 1
                    
                    if 'callback_query' in update:
                        handle_callback(update['callback_query'])
                    elif 'message' in update:
                        handle_message(update['message'])
        
    except requests.exceptions.Timeout:
        continue
    except Exception as e:
        print(f"⚠️ خطأ: {e}")
        time.sleep(0.1)
