import io
import os
import sys
import datetime
import pandas as pd
from fpdf import FPDF

COLUMNAS = ["producto", "precio", "cantidad"]


def limpiar(texto):
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def recortar(texto, n):
    texto = limpiar(texto)
    return texto if len(texto) <= n else texto[: n - 1] + "."


def calcular(df):
    df = df.copy().reset_index(drop=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError("Faltan columnas: " + ", ".join(faltan))
    if len(df) == 0:
        raise ValueError("No hay conceptos en la tabla")

    for col in ["precio", "cantidad"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        if df[col].isna().any():
            filas = (df[df[col].isna()].index + 1).tolist()
            raise ValueError("Valores no numericos en '" + col + "', filas de la tabla: " + str(filas))

    if "unidad" not in df.columns:
        df["unidad"] = "ud"
    df["unidad"] = df["unidad"].fillna("ud").astype(str)
    if "descuento" not in df.columns:
        df["descuento"] = 0
    df["descuento"] = pd.to_numeric(df["descuento"], errors="coerce").fillna(0)
    df["subtotal"] = (df["precio"] * df["cantidad"] * (1 - df["descuento"] / 100)).round(2)
    total = round(df["subtotal"].sum(), 2)
    return df, total


def generar_presupuesto(ruta="productos.csv"):
    try:
        df = pd.read_csv(ruta, encoding="utf-8-sig")
    except FileNotFoundError:
        raise ValueError("No se encuentra el archivo " + ruta)
    except Exception as e:
        raise ValueError("No se pudo leer el archivo: " + str(e))
    return calcular(df)


def calcular_iva(total, iva):
    cuota = round(total * iva / 100, 2)
    return cuota, round(total + cuota, 2)


def mostrar_presupuesto(df, total, iva=21.0):
    cuota, total_final = calcular_iva(total, iva)
    print("\nPRESUPUESTO")
    print("-" * 40)
    for _, f in df.iterrows():
        print(str(f["producto"]) + ": " + format(f["cantidad"], "g") + " " + str(f["unidad"]) + " x " + format(f["precio"], ".2f") + " EUR = " + format(f["subtotal"], ".2f") + " EUR")
    print("-" * 40)
    print("Base imponible: " + format(total, ".2f") + " EUR")
    print("IVA " + str(iva) + "%: " + format(cuota, ".2f") + " EUR")
    print("TOTAL: " + format(total_final, ".2f") + " EUR")


def crear_pdf(df, total, ruta="presupuesto.pdf", cliente="", numero="", iva=21.0, emisor="", notas="", oficio="", extras="", logo=None):
    cuota, total_final = calcular_iva(total, iva)
    fecha = datetime.date.today().strftime("%d/%m/%Y")
    pdf = FPDF()
    pdf.add_page()
    if logo:
        try:
            pdf.image(io.BytesIO(logo), x=10, y=10, h=20)
            pdf.set_y(34)
        except Exception:
            pdf.set_y(10)
    if emisor.strip():
        pdf.set_font("Helvetica", "B", 12)
        for linea in emisor.splitlines():
            pdf.cell(0, 6, limpiar(linea), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "PRESUPUESTO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    if oficio and oficio != "General":
        pdf.cell(0, 7, limpiar(oficio), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "N: " + limpiar(numero), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "Fecha: " + fecha, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "Cliente: " + limpiar(cliente), new_x="LMARGIN", new_y="NEXT")
    for linea in extras.splitlines():
        pdf.cell(0, 7, limpiar(linea), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    for texto, ancho in [("Concepto", 75), ("Ud", 15), ("Cant.", 18), ("Precio", 28), ("Dto", 14), ("Subtotal", 30)]:
        pdf.cell(ancho, 9, texto, border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for _, f in df.iterrows():
        pdf.cell(75, 8, recortar(f["producto"], 44), border=1)
        pdf.cell(15, 8, recortar(f["unidad"], 7), border=1)
        pdf.cell(18, 8, format(f["cantidad"], "g"), border=1)
        pdf.cell(28, 8, format(f["precio"], ".2f") + " EUR", border=1)
        pdf.cell(14, 8, format(f["descuento"], ".0f") + "%", border=1)
        pdf.cell(30, 8, format(f["subtotal"], ".2f") + " EUR", border=1)
        pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(150, 9, "Base imponible", border=1, align="R")
    pdf.cell(30, 9, format(total, ".2f") + " EUR", border=1)
    pdf.ln()
    pdf.cell(150, 9, "IVA " + str(iva) + "%", border=1, align="R")
    pdf.cell(30, 9, format(cuota, ".2f") + " EUR", border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(150, 10, "TOTAL", border=1, align="R")
    pdf.cell(30, 10, format(total_final, ".2f") + " EUR", border=1)
    if notas.strip():
        pdf.ln(14)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Notas y condiciones", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, limpiar(notas), new_x="LMARGIN", new_y="NEXT")
    if ruta is None:
        return bytes(pdf.output())
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    pdf.output(ruta)


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "productos.csv"
    try:
        df, total = generar_presupuesto(ruta)
    except ValueError as e:
        print("ERROR: " + str(e))
        sys.exit(1)
    mostrar_presupuesto(df, total)
    crear_pdf(df, total, cliente="Cliente de prueba", numero="PRUEBA")
    print("\nPDF creado: presupuesto.pdf")
