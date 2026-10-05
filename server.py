import os
import secrets
import threading
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import telebot

# ==========================================
# CONFIGURACIÓN DEL BOT DE TELEGRAM
# ==========================================
# Lee el token directamente de las variables de entorno de Render
BOT_TOKEN = os.getenv("BOT_TOKEN", "8988443162:AAEXTBLvNR2YLb_jbY-ejE3zjhKY-egMY3k")
bot = telebot.TeleBot(BOT_TOKEN)

# Estructura de KEYS:
KEYS_DB = {
    "KEY-TEST-15": {"days": 15, "device_id": None, "expires_at": None},
    "KEY-TEST-30": {"days": 30, "device_id": None, "expires_at": None}
}

# Estructura de TOKENS ACTIVOS DE SESIÓN:
ACTIVE_TOKENS = {}

# Directorio de archivos
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

# Mapeo exacto de identificadores a archivos en /uploads
FILE_MAP = {
    "holograma_pj": "resources.assets",
    "wallhack": "Archive_modificado.zip",
    "armas_neblina": "shaders_P0K3UG2TfecMBhWMMV2Fu8ReudIk3D NEBLUSA EXCLUSIVE",
    "armas_rgb": "shaders.P0K3UG2TfecMBhWMMV~2Fu8ReudIk~3D RGB EXCLUSIVE",
    "armas_cuadros": "shaders.P0K3UG2TfecMBhWMMV~2Fu8ReudIk~3D CUADROS EXCLUSIVE",
    "armas_tocino": "shaders.P0K3UG2TfecMBhWMMV~2Fu8ReudIk~3D CARNE EXCLUSIVE",
    "aimbot_body": "assetindexer.U6Zffc4YIR3DslNj3cXvYGAqz58~3D BODY DISIMULADO",
    "aimbot_neck": "assetindexer.U6Zffc4YIR3DslNj3cXvYGAqz58~3D NECK",
    "aimbot_head": "assetindexer.U6Zffc4YIR3DslNj3cXvYGAqz58~3D HEAD",
    "aimbot_drag": "assetindexer.U6Zffc4YIR3DslNj3cXvYGAqz58~3D AIM DRAG"
}

# ==========================================
# COMANDOS DEL BOT DE TELEGRAM
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    texto = (
        "🔥 *BIENVENIDO AL BOT DRT IOS VIP* 🔥\n\n"
        "Comandos para generar Keys VIP:\n"
        "🔑 /genkey 15 - Generar Key de 15 días\n"
        "🔑 /genkey 20 - Generar Key de 20 días\n"
        "🔑 /genkey 30 - Generar Key de 30 días\n\n"
        "📋 /listkeys - Ver estado de las keys"
    )
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['genkey'])
def generate_key_cmd(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Uso incorrecto. Especifica los días: /genkey 15, /genkey 20 o /genkey 30", parse_mode="Markdown")
            return

        days = int(args[1])
        if days not in [15, 20, 30]:
            bot.reply_to(message, "⚠️ La duración solo puede ser de 15, 20 o 30 días.")
            return

        new_key = f"DRT-{secrets.token_hex(4).upper()}"
        KEYS_DB[new_key] = {
            "days": days,
            "device_id": None,
            "expires_at": None
        }

        bot.reply_to(
            message,
            f"✅ *KEY VIP GENERADA EXITOSAMENTE*\n\n"
            f"🔑 Key: `{new_key}`\n"
            f"⏳ Duración: {days} días (inicia al usarse)\n"
            f"📱 Límite: 1 solo dispositivo",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error al generar key: {str(e)}")

@bot.message_handler(commands=['listkeys'])
def list_keys_cmd(message):
    if not KEYS_DB:
        bot.reply_to(message, "⚠️ No hay keys activas.")
        return

    text = "🔑 *KEYS REGISTRADAS EN EL SISTEMA:*\n\n"
    now = datetime.now()
    for key, data in KEYS_DB.items():
        if data["expires_at"]:
            if now > data["expires_at"]:
                estado = "❌ EXPIRADA"
            else:
                restante = (data["expires_at"] - now).days
                estado = f"🟢 ACTIVA ({restante} días restantes)"
        else:
            estado = f"🟡 SIN USAR ({data['days']} días)"

        text += f"• {key} | {estado}\n"

    bot.reply_to(message, text, parse_mode="Markdown")

def start_bot():
    print("🤖 Bot de Telegram iniciado...")
    bot.infinity_polling()

# ==========================================
# API FASTAPI / SERVIDOR WEB
# ==========================================
app = FastAPI(title="DRT IOS PANEL VIP")

class KeyRequest(BaseModel):
    key: str
    device_id: str

@app.post("/api/verify")
async def verify_key(req: KeyRequest):
    key_upper = req.key.strip().upper()

    if key_upper not in KEYS_DB:
        raise HTTPException(status_code=401, detail="Key inválida o no existe")

    key_data = KEYS_DB[key_upper]
    now = datetime.now()

    # 1. Si es la primera vez que se usa la Key
    if key_data["device_id"] is None:
        key_data["device_id"] = req.device_id
        key_data["expires_at"] = now + timedelta(days=key_data["days"])
    
    # 2. Verificar que no haya expirado
    if now > key_data["expires_at"]:
        raise HTTPException(status_code=401, detail="La Key ha expirado")

    # 3. Verificar que se use en el mismo dispositivo
    if key_data["device_id"] != req.device_id:
        raise HTTPException(status_code=401, detail="Key en uso en otro dispositivo")

    # Generar token de sesión
    token = secrets.token_hex(16)
    ACTIVE_TOKENS[token] = {
        "key": key_upper,
        "device_id": req.device_id,
        "expires_at": key_data["expires_at"]
    }

    return {
        "token": token,
        "expires_at": key_data["expires_at"].strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/api/download/{file_key}")
async def download_file(file_key: str, token: str = Query(...), device_id: str = Query(...)):
    if token not in ACTIVE_TOKENS:
        raise HTTPException(status_code=403, detail="Sesión no válida o expirada")

    session = ACTIVE_TOKENS[token]
    now = datetime.now()

    # Validar si el token ya expiró
    if now > session["expires_at"]:
        del ACTIVE_TOKENS[token]
        raise HTTPException(status_code=403, detail="Sesión o Key expirada")

    # Validar dispositivo
    if session["device_id"] != device_id:
        raise HTTPException(status_code=403, detail="Dispositivo no autorizado")

    if file_key not in FILE_MAP:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")

    filename = FILE_MAP[file_key]
    file_path = os.path.join(UPLOADS_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="El archivo no existe en el servidor")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

    # Lee el puerto dinámico asignado por Render (por defecto 8000 si se ejecuta local)
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)