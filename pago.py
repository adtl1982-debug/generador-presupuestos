import hashlib
import hmac
import json
import secrets
import time
import urllib.request

import streamlit as st
import stripe

LIMITE_GRATIS = 3
CODIGO_VALIDEZ = 600
MAX_ENVIOS = 3
MAX_INTENTOS = 5
ESPERA_ENVIO = 60


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
        "html": "<p>Tu codigo para activar Estimio Pro es:</p><h2>" + codigo + "</h2><p>Caduca en 10 minutos. Si no lo has pedido, ignora este correo.</p>",
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
    if "@" not in email or "." not in email:
        return False, "Escribe un email valido."
    s = st.session_state
    ahora = time.time()
    if s.get("cod_envios", 0) >= MAX_ENVIOS:
        return False, "Has pedido demasiados codigos. Intentalo mas tarde."
    if ahora - s.get("cod_ultimo", 0) < ESPERA_ENVIO:
        return False, "Espera un minuto antes de pedir otro codigo."
    s["cod_envios"] = s.get("cod_envios", 0) + 1
    s["cod_ultimo"] = ahora
    if es_premium(email):
        codigo = format(secrets.randbelow(1000000), "06d")
        if _enviar_email(email, codigo):
            s["cod_hash"] = _hash(email, codigo)
            s["cod_expira"] = ahora + CODIGO_VALIDEZ
            s["cod_intentos"] = 0
    return True, "Si hay una suscripcion activa con ese email, te hemos enviado un codigo. Mira tambien en spam."


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
