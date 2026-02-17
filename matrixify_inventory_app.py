import streamlit as st
import pandas as pd

# -------------------------------------------------
# CONFIGURACIÓN GENERAL
# -------------------------------------------------
st.set_page_config(
    page_title="Validador Inventario CEDI → Matrixify",
    layout="wide"
)

st.title("Validador de Inventario CEDI → Matrixify")
st.caption("Actualiza Available en Shopify respetando Committed (Matrixify ready)")

# -------------------------------------------------
# CARGA DE ARCHIVOS
# -------------------------------------------------
shopify_file = st.file_uploader(
    "1️⃣ Archivo Matrixify (Inventario Shopify - Excel)",
    type=["xlsx"]
)

cedi_file = st.file_uploader(
    "2️⃣ Archivo Inventario CEDI (Excel)",
    type=["xlsx"]
)

# -------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------
def clean_columns(df):
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.replace("\n", " ", regex=False)
    )
    return df


def load_excel(file):
    return pd.read_excel(file, engine="openpyxl")


# -------------------------------------------------
# PROCESAMIENTO
# -------------------------------------------------
if shopify_file and cedi_file:

    # ---------- Leer archivos ----------
    shopify = load_excel(shopify_file)
    cedi = load_excel(cedi_file)

    shopify = clean_columns(shopify)
    cedi = clean_columns(cedi)

    # ---------- Validaciones mínimas ----------
    required_shopify_cols = {
        "Variant SKU",
        "Location",
        "Available",
        "Committed"
    }

    required_cedi_cols = {
        "Código Producto",
        "Cant. Disponible"
    }

    if not required_shopify_cols.issubset(shopify.columns):
        st.error(
            f"El archivo Matrixify debe contener las columnas: {required_shopify_cols}"
        )
        st.stop()

    if not required_cedi_cols.issubset(cedi.columns):
        st.error(
            f"El archivo CEDI debe contener las columnas: {required_cedi_cols}"
        )
        st.stop()

    # ---------- Normalización ---
