import datetime
import pandas as pd
import streamlit as st
from presupuesto import calcular, crear_pdf, calcular_iva
from oficios import OFICIOS
from pago import LIMITE_GRATIS, enlace_pago, es_premium

st.set_page_config(page_title="Estimio")
st.title("Estimio")
st.caption("Presupuestos profesionales en PDF, en un minuto.")

COLS = ["producto", "unidad", "precio", "cantidad", "descuento"]


def tabla_inicial():
    return pd.DataFrame({"producto": ["Concepto 1"], "unidad": ["ud"], "precio": [0.0], "cantidad": [1], "descuento": [0.0]})[COLS]


def cambiar_oficio():
    conceptos = OFICIOS[st.session_state.oficio]["conceptos"]
    if conceptos:
        t = pd.DataFrame(conceptos, columns=["producto", "unidad", "precio"])
        t["cantidad"] = 1
        t["descuento"] = 0.0
        st.session_state.base = t[COLS]
        st.session_state.version += 1


if "base" not in st.session_state:
    st.session_state.base = tabla_inicial()
    st.session_state.version = 0
    st.session_state.n = 1
    st.session_state.historial = []
    st.session_state.generados = 0
    st.session_state.premium = False

st.sidebar.header("Tu plan")
if st.session_state.premium:
    st.sidebar.success("Estimio Pro activo")
else:
    restantes = max(LIMITE_GRATIS - st.session_state.generados, 0)
    st.sidebar.write("Plan gratis: te quedan " + str(restantes) + " de " + str(LIMITE_GRATIS) + " presupuestos")
    if enlace_pago():
        st.sidebar.link_button("Hazte Pro 6,99 EUR/mes", enlace_pago())
    email_pro = st.sidebar.text_input("Email con el que pagaste")
    if st.sidebar.button("Activar Pro"):
        if es_premium(email_pro):
            st.session_state.premium = True
            st.rerun()
        else:
            st.sidebar.error("No encuentro una suscripcion activa con ese email.")

oficio = st.selectbox("Oficio", list(OFICIOS.keys()), key="oficio", on_change=cambiar_oficio)
datos = OFICIOS[oficio]

st.subheader("Tu empresa")
logo_file = st.file_uploader("Logo de tu empresa [PNG o JPG]", type=["png", "jpg", "jpeg"])
logo = logo_file.getvalue() if logo_file else None
if logo:
    st.image(logo, width=120)
emisor = st.text_area("Tus datos [nombre, NIF, dirección, teléfono]", height=100)

st.subheader("Presupuesto")
c1, c2, c3 = st.columns(3)
cliente = c1.text_input("Cliente")
sugerido = str(datetime.date.today().year) + "-" + format(st.session_state.n, "03d")
numero = c2.text_input("Nº presupuesto", value=sugerido)
iva = c3.number_input("IVA %", min_value=0.0, max_value=100.0, value=datos["iva"], step=1.0)

extras_vals = {}
for etiqueta in datos["extras"]:
    extras_vals[etiqueta] = st.text_input(etiqueta, key="extra_" + etiqueta)

st.subheader("Conceptos")
editado = st.data_editor(st.session_state.base, num_rows="dynamic", width="stretch", key="tabla_" + str(st.session_state.version))
editado = editado.dropna(how="all")

notas = st.text_area("Notas y condiciones de pago", value=datos["notas"], height=100)

if st.button("Generar presupuesto", type="primary"):
    limite = (not st.session_state.premium) and st.session_state.generados >= LIMITE_GRATIS
    if limite:
        st.warning("Has usado tus " + str(LIMITE_GRATIS) + " presupuestos gratis. Hazte Pro para seguir sin limite y sin marca de agua.")
        if enlace_pago():
            st.link_button("Ir a Estimio Pro", enlace_pago())
    else:
        try:
            df, total = calcular(editado)
        except ValueError as e:
            st.error(str(e))
        else:
            cuota, total_final = calcular_iva(total, iva)
            st.dataframe(df, width="stretch")
            st.write("Base imponible: " + format(total, ".2f") + " EUR")
            st.write("IVA " + str(iva) + "%: " + format(cuota, ".2f") + " EUR")
            st.success("TOTAL: " + format(total_final, ".2f") + " EUR")
            extras = "\n".join(k + ": " + v for k, v in extras_vals.items() if v.strip())
            nombre = "presupuesto_" + numero.replace("/", "-") + ".pdf"
            marca = not st.session_state.premium
            pdf_bytes = crear_pdf(df, total, None, cliente, numero, iva, emisor, notas, oficio, extras, logo, marca)
            if numero == sugerido:
                st.session_state.n += 1
            st.session_state.generados += 1
            st.session_state.historial.insert(0, (nombre, pdf_bytes))
            st.download_button("Descargar PDF", pdf_bytes, file_name=nombre, mime="application/pdf", key="descarga_actual")
            if marca:
                faltan = max(LIMITE_GRATIS - st.session_state.generados, 0)
                st.info("Plan gratis: te quedan " + str(faltan) + " presupuestos. El PDF lleva marca de agua.")

st.sidebar.header("Presupuestos de esta sesión")
if not st.session_state.historial:
    st.sidebar.write("Todavía no hay ninguno.")
for i, (nombre_pdf, datos_pdf) in enumerate(st.session_state.historial):
    st.sidebar.download_button(nombre_pdf, datos_pdf, file_name=nombre_pdf, mime="application/pdf", key="hist_" + str(i))
st.sidebar.caption("Se borran al cerrar la página. Descarga cada PDF.")
