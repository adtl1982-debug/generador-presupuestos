import datetime
import hashlib
import hmac
import json
import re
import secrets
import time
import urllib.parse
import urllib.request

import streamlit as st
import stripe

LIMITE_GRATIS = 3
CODIGO_VALIDEZ = 600
MAX_ENVIOS = 3
MAX_INTENTOS = 5
ESPERA_ENVIO = 60
MAX_ENVIOS_EMAIL_HORA = 3
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@st.cache_resource
def _registro_envios():
    return {}


def _limite_email(email):
    ahora = time.time()
    reg = _registro_envios()
    for k in [k for k, v in reg.items() if not v or ahora - v[-1] > 3600]:
        reg.pop(k, None)
    veces = [x for x in reg.get(email, []) if ahora - x < 3600]
    if len(veces) >= MAX_ENVIOS_EMAIL_HORA:
        reg[email] = veces
        return False
    veces.append(ahora)
    reg[email] = veces
    return True


def _secreto(nombre):
    try:
        return st.secrets.get(nombre, "")
    except Exception:
        return ""


def enlace_pago():
    return _secreto("STRIPE_PAYMENT_LINK")


def es_premium(email):
    clave = _secreto("STRIPE_SECRET_KEY")
    email = (email or "").strip().replace('"', "")
    if not clave or not email:
        return False
    stripe.api_key = clave
    try:
        clientes = stripe.Customer.search(query='email:"' + email + '"')
        for c in clientes.data:
            subs = stripe.Subscription.list(customer=c.id, status="active", limit=5)
            if subs.data:
                return True
    except Exception:
        return False
    return False


def _hash(email, codigo):
    return hashlib.sha256((email.lower() + ":" + codigo).encode("utf-8")).hexdigest()


def _enviar_email(email, codigo):
    clave = _secreto("RESEND_API_KEY")
    if not clave:
        return False
    cuerpo = json.dumps({
        "from": "Estimio <no-reply@estimio.app>",
        "to": [email],
        "subject": "Tu codigo de Estimio: " + codigo,
        "html": "<p>Tu codigo para entrar en Estimio es:</p><h2>" + codigo + "</h2><p>Caduca en 10 minutos. Si no lo has pedido, ignora este correo.</p>",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=cuerpo,
        headers={"Authorization": "Bearer " + clave, "Content-Type": "application/json", "User-Agent": "Estimio/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def enviar_codigo(email):
    email = (email or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        return False, "Escribe un email valido."
    s = st.session_state
    ahora = time.time()
    if s.get("cod_envios", 0) >= MAX_ENVIOS:
        return False, "Has pedido demasiados codigos. Intentalo mas tarde."
    if ahora - s.get("cod_ultimo", 0) < ESPERA_ENVIO:
        return False, "Espera un minuto antes de pedir otro codigo."
    s["cod_envios"] = s.get("cod_envios", 0) + 1
    s["cod_ultimo"] = ahora
    if not _limite_email(email):
        return False, "Has pedido demasiados codigos para ese email. Intentalo mas tarde."
    if not _limite_global():
        return False, "Servicio ocupado. Intentalo mas tarde."
    codigo = format(secrets.randbelow(1000000), "06d")
    if not _enviar_email(email, codigo):
        return False, "No he podido enviar el codigo. Intentalo de nuevo."
    s["cod_hash"] = _hash(email, codigo)
    s["cod_expira"] = ahora + CODIGO_VALIDEZ
    s["cod_intentos"] = 0
    return True, "Te hemos enviado un codigo. Mira tambien en spam."


def verificar_codigo(email, codigo):
    email = (email or "").strip().lower()
    codigo = (codigo or "").strip()
    s = st.session_state
    esperado = s.get("cod_hash")
    if not esperado or time.time() > s.get("cod_expira", 0):
        return False, "Codigo no valido o caducado. Pide uno nuevo."
    if s.get("cod_intentos", 0) >= MAX_INTENTOS:
        return False, "Demasiados intentos. Pide un codigo nuevo."
    s["cod_intentos"] = s.get("cod_intentos", 0) + 1
    if not hmac.compare_digest(_hash(email, codigo), esperado):
        return False, "Codigo incorrecto."
    s.pop("cod_hash", None)
    return True, ""


def url_portal(email, volver):
    clave = _secreto("STRIPE_SECRET_KEY")
    email = (email or "").strip().replace('"', "")
    if not clave or not email:
        return ""
    stripe.api_key = clave
    try:
        clientes = stripe.Customer.search(query='email:"' + email + '"')
        for c in clientes.data:
            subs = stripe.Subscription.list(customer=c.id, status="active", limit=1)
            if subs.data:
                s = stripe.billing_portal.Session.create(customer=c.id, return_url=volver)
                return s.url
    except Exception:
        return ""
    return ""


MAX_ENVIOS_DIA = 80


@st.cache_resource
def _contador_dia():
    return {"dia": "", "n": 0}


def _limite_global():
    c = _contador_dia()
    hoy = datetime.date.today().isoformat()
    if c["dia"] != hoy:
        c["dia"] = hoy
        c["n"] = 0
    if c["n"] >= MAX_ENVIOS_DIA:
        return False
    c["n"] += 1
    return True


def _mes():
    return datetime.date.today().strftime("%Y-%m")


def _supabase(metodo, ruta, cuerpo=None):
    url = _secreto("SUPABASE_URL")
    clave = _secreto("SUPABASE_SECRET_KEY")
    if not url or not clave:
        return None
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(
        url + "/rest/v1/" + ruta,
        data=datos,
        headers={"apikey": clave, "Content-Type": "application/json", "User-Agent": "Estimio/1.0"},
        method=metodo,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    except Exception:
        return None


def usados_gratis(email):
    email = (email or "").strip().lower()
    if not email:
        return None
    r = _supabase("GET", "uso_gratis?select=usados&email=eq." + urllib.parse.quote(email, safe="") + "&mes=eq." + _mes())
    if r is None:
        return None
    return int(r[0]["usados"]) if r else 0


def usar_gratis(email, limite):
    email = (email or "").strip().lower()
    if not email:
        return None
    r = _supabase("POST", "rpc/usar_gratis", {"p_email": email, "p_mes": _mes(), "p_limite": limite})
    if r is None:
        return None
    return int(r)
