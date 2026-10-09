import streamlit as st
import stripe

LIMITE_GRATIS = 3


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
