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

    # ---------- Normalización ----------
    shopify["Variant SKU"] = shopify["Variant SKU"].astype(str).str.strip()
    cedi["Código Producto"] = cedi["Código Producto"].astype(str).str.strip()

    shopify["Available"] = pd.to_numeric(shopify["Available"], errors="coerce").fillna(0)
    shopify["Committed"] = pd.to_numeric(shopify["Committed"], errors="coerce").fillna(0)

    cedi["Cant. Disponible"] = pd.to_numeric(
        cedi["Cant. Disponible"], errors="coerce"
    ).fillna(0)

    # ---------- Consolidar CEDI ----------
    cedi_agg = (
        cedi
        .groupby("Código Producto", as_index=False)["Cant. Disponible"]
        .sum()
        .rename(columns={
            "Código Producto": "Variant SKU",
            "Cant. Disponible": "CEDI Available"
        })
    )

    # ---------- Cruce ----------
    df = shopify.merge(
        cedi_agg,
        on="Variant SKU",
        how="left"
    )

    df["CEDI Available"] = df["CEDI Available"].fillna(0)

    # ---------- Lógica Matrixify ----------
    # IMPORTANTE:
    # Matrixify actualiza SOLO Available
    # Committed NO se toca
    df["Available New"] = df["CEDI Available"]
    df["Delta"] = df["Available New"] - df["Available"]

    # ---------- Estado ----------
    def estado(row):
        if row["Available"] == 0 and row["Available New"] > 0:
            return "Inventario Nuevo"
        if row["Delta"] > 0:
            return f"Inventario Sube (+{int(row['Delta'])})"
        if row["Delta"] < 0:
            return f"Inventario Decrece ({int(row['Delta'])})"
        return "Inventario Igual"

    df["Estado"] = df.apply(estado, axis=1)

    # ---------- Alertas ----------
    df["Alerta"] = ""

    df.loc[df["Available New"] < 0, "Alerta"] = "ERROR: Inventario negativo"

    if (df["Available New"] < 0).any():
        st.error("❌ Existen inventarios
