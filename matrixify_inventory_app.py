import streamlit as st
import pandas as pd

st.set_page_config(page_title="Matrixify Inventory Validator", layout="wide")
st.title("Validador de Inventario CEDI → Matrixify")

# Uploads
shopify_file = st.file_uploader("Archivo Matrixify (Shopify)", type=["csv", "xlsx"])
cedi_file = st.file_uploader("Archivo Inventario CEDI", type=["xlsx", "csv"])

if shopify_file and cedi_file:

    # --- Load Shopify ---
    if shopify_file.name.endswith(".csv"):
        shopify = pd.read_csv(shopify_file)
    else:
        shopify = pd.read_excel(shopify_file)

    # --- Load CEDI ---
    if cedi_file.name.endswith(".csv"):
        cedi = pd.read_csv(cedi_file)
    else:
        cedi = pd.read_excel(cedi_file)

    # --- Normalize ---
    shopify["Variant SKU"] = shopify["Variant SKU"].astype(str).str.strip()
    cedi["Código Producto"] = cedi["Código Producto"].astype(str).str.strip()

    # --- Aggregate CEDI ---
    cedi_clean = (
        cedi.groupby("Código Producto", as_index=False)["Cant. Disponible"]
        .sum()
        .rename(columns={"Código Producto": "Variant SKU",
                         "Cant. Disponible": "CEDI Available"})
    )

    # --- Merge ---
    df = shopify.merge(cedi_clean, on="Variant SKU", how="left")
    df["CEDI Available"] = df["CEDI Available"].fillna(0)

    # --- Calculations ---
    df["Available New"] = df["CEDI Available"]
    df["Delta"] = df["Available New"] - df["Available"]

    def status(row):
        if row["Available"] == 0 and row["Available New"] > 0:
            return "Inventario Nuevo"
        if row["Delta"] > 0:
            return f"Inventario Sube (+{int(row['Delta'])})"
        if row["Delta"] < 0:
            return f"Inventario Decrece ({int(row['Delta'])})"
        return "Inventario Igual"

    df["Estado"] = df.apply(status, axis=1)

    # --- Alerts ---
    df["Alerta"] = ""
    df.loc[df["Available New"] < 0, "Alerta"] = "ERROR: Inventario Negativo"

    # --- Preview ---
    st.subheader("Vista previa de validación")
    st.dataframe(
        df[
            [
                "Variant SKU",
                "Location",
                "Available",
                "CEDI Available",
                "Available New",
                "Committed",
                "Delta",
                "Estado",
                "Alerta",
            ]
        ],
        use_container_width=True,
    )

    # --- Stop if errors ---
    if (df["Available New"] < 0).any():
        st.error("Existen inventarios negativos. Corrige antes de continuar.")
        st.stop()

    # --- Matrixify File ---
    matrixify_export = df[
        ["Variant SKU", "Location", "Available New"]
    ].rename(columns={"Available New": "Available"})

    # --- History File ---
    history = df[
        [
            "Variant SKU",
            "Location",
            "Available",
            "CEDI Available",
            "Available New",
            "Delta",
            "Estado",
        ]
    ]

    st.subheader("Descargas")

    st.download_button(
        "Descargar archivo Matrixify",
        matrixify_export.to_csv(index=False),
        file_name="Matrixify_Inventory_Update.csv",
        mime="text/csv",
    )

    st.download_button(
        "Descargar historial de ajustes",
        history.to_csv(index=False),
        file_name="Historial_Ajustes_Inventario.csv",
        mime="text/csv",
    )
