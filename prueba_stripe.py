import tomllib
import stripe

with open(".streamlit/secrets.toml", "rb") as f:
    s = tomllib.load(f)

stripe.api_key = s["STRIPE_SECRET_KEY"]
clientes = stripe.Customer.list(limit=1)
subs = stripe.Subscription.list(limit=1)
busqueda = stripe.Customer.search(query='email:"prueba@correo.com"')
print("OK", len(clientes.data), len(subs.data), len(busqueda.data))
