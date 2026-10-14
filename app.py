import datetime
import pandas as pd
import streamlit as st
from presupuesto import calcular, crear_pdf, calcular_iva
from oficios import OFICIOS
from pago import LIMITE_GRATIS, enlace_pago, enviar_codigo, verificar_codigo, url_portal, es_premium, usados_gratis, usar_gratis, cargar_precios, guardar_precios, borrar_precios

st.set_page_config(page_title="Estimio")
st.title("Estimio")
st.caption("Presupuestos profesionales en PDF, en un minuto.")

COLS = ["producto", "unidad", "precio", "cantidad", "descuento"]


def tabla_inicial():
    return pd.DataFrame({"producto": ["Concepto 1"], "unidad": ["ud"], "precio": [0.0], "cantidad": [1], "descuento": [0.0]})[COLS]


def conceptos_oficio(nombre):
    conceptos = OFICIOS[nombre]["conceptos"]
    if st.session_state.premium and st.session_state.email_ok:
        guardados = cargar_precios(st.session_state.email_ok, nombre)
        if guardados:
            return [(g[0], g[1], float(g[2])) for g in guardados]
    return conceptos


def cambiar_oficio():
    conceptos = conceptos_oficio(st.session_state.oficio)
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

st.session_state.setdefault("email_ok", "")
st.session_state.setdefault("usados", None)

st.sidebar.header("Tu plan")
if not st.session_state.email_ok:
    st.sidebar.write("Entra con tu email para usar Estimio. Plan gratis: " + str(LIMITE_GRATIS) + " presupuestos al mes.")
    email_pro = st.sidebar.text_input("Tu email")
    if st.sidebar.button("Enviar codigo"):
        ok, msg = enviar_codigo(email_pro)
        if ok:
            st.sidebar.info(msg)
        else:
            st.sidebar.error(msg)
    codigo_pro = st.sidebar.text_input("Codigo de 6 digitos", max_chars=6)
    if st.sidebar.button("Entrar"):
        ok, msg = verificar_codigo(email_pro, codigo_pro)
        if ok:
            email_limpio = email_pro.strip().lower()
            st.session_state.email_ok = email_limpio
            st.session_state.premium = es_premium(email_limpio)
            st.session_state.usados = None if st.session_state.premium else usados_gratis(email_limpio)
            if st.session_state.premium and "oficio" in st.session_state:
                cambiar_oficio()
            st.rerun()
        else:
            st.sidebar.error(msg)
else:
    st.sidebar.caption(st.session_state.email_ok)
    if st.session_state.premium:
        st.sidebar.success("Estimio Pro activo")
        if st.sidebar.button("Gestionar suscripcion"):
            u = url_portal(st.session_state.email_ok, "https://estimio.streamlit.app")
            if u:
                st.sidebar.link_button("Abrir portal de Stripe", u)
            else:
                st.sidebar.error("No he podido abrir el portal. Intentalo de nuevo.")
    else:
        usados = st.session_state.usados
        if usados is None:
            st.sidebar.warning("No he podido comprobar tu plan. Pulsa Salir y vuelve a entrar.")
        else:
            restantes = max(LIMITE_GRATIS - usados, 0)
            st.sidebar.write("Plan gratis: te quedan " + str(restantes) + " de " + str(LIMITE_GRATIS) + " presupuestos este mes")
        if enlace_pago():
            st.sidebar.link_button("Hazte Pro 6,99 EUR/mes", enlace_pago())
        if st.sidebar.button("Ya he pagado, actualizar"):
            st.session_state.premium = es_premium(st.session_state.email_ok)
            st.rerun()
    if st.sidebar.button("Salir"):
        st.session_state.email_ok = ""
        st.session_state.premium = False
        st.session_state.usados = None
        st.rerun()

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

if st.session_state.premium:
    cb1, cb2 = st.columns(2)
    if cb1.button("Guardar mis precios"):
        filas = []
        for _, f in editado.iterrows():
            nombre_c = str(f["producto"]).strip()
            if nombre_c and nombre_c != "nan":
                precio_c = pd.to_numeric(f["precio"], errors="coerce")
                filas.append([nombre_c[:120], str(f["unidad"])[:20], 0.0 if pd.isna(precio_c) else float(precio_c)])
        filas = filas[:60]
        if not filas:
            st.warning("No hay conceptos que guardar.")
        elif guardar_precios(st.session_state.email_ok, oficio, filas):
            st.success("Precios guardados para " + oficio)
        else:
            st.error("No he podido guardar. Intentalo de nuevo.")
    if cb2.button("Restablecer precios"):
        if borrar_precios(st.session_state.email_ok, oficio):
            cambiar_oficio()
            st.rerun()
        else:
            st.error("No he podido restablecer. Intentalo de nuevo.")
else:
    st.caption("Guardar tus precios para no repetirlos es parte de Estimio Pro.")

notas = st.text_area("Notas y condiciones de pago", value=datos["notas"], height=100)

if st.button("Generar presupuesto", type="primary"):
    if not st.session_state.email_ok:
        st.warning("Entra con tu email en la barra lateral para generar presupuestos.")
    else:
        try:
            df, total = calcular(editado)
        except ValueError as e:
            st.error(str(e))
        else:
            permitido = True
            if not st.session_state.premium:
                n = usar_gratis(st.session_state.email_ok, LIMITE_GRATIS)
                if n is None:
                    permitido = False
                    st.error("No he podido comprobar tu limite. Intentalo de nuevo en un momento.")
                elif n < 0:
                    permitido = False
                    st.session_state.usados = LIMITE_GRATIS
                    st.warning("Has usado tus " + str(LIMITE_GRATIS) + " presupuestos gratis de este mes. Hazte Pro para seguir sin limite y sin marca de agua.")
                    if enlace_pago():
                        st.link_button("Ir a Estimio Pro", enlace_pago())
                else:
                    st.session_state.usados = n
            if permitido:
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
                st.session_state.historial.insert(0, (nombre, pdf_bytes))
                st.download_button("Descargar PDF", pdf_bytes, file_name=nombre, mime="application/pdf", key="descarga_actual")
                if marca:
                    faltan = max(LIMITE_GRATIS - st.session_state.usados, 0)
                    st.info("Plan gratis: te quedan " + str(faltan) + " presupuestos este mes. El PDF lleva marca de agua.")

st.sidebar.header("Presupuestos de esta sesión")
if not st.session_state.historial:
    st.sidebar.write("Todavía no hay ninguno.")
for i, (nombre_pdf, datos_pdf) in enumerate(st.session_state.historial):
    st.sidebar.download_button(nombre_pdf, datos_pdf, file_name=nombre_pdf, mime="application/pdf", key="hist_" + str(i))
st.sidebar.caption("Se borran al cerrar la página. Descarga cada PDF.")


from pathlib import Path


def _leer(nombre):
    p = Path(__file__).parent / nombre
    return p.read_text(encoding="utf-8-sig") if p.exists() else "Documento no disponible."


st.divider()
with st.expander("Política de privacidad"):
    st.markdown(_leer("politica_privacidad.md"))
with st.expander("Términos y condiciones"):
    st.markdown(_leer("terminos.md"))

