import streamlit as st
import pandas as pd
from io import BytesIO

# -------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -------------------------------------------------
st.set_page_config(page_title="Actualizador Matrixify", layout="wide")
st.title("🔄 Actualizador de Inventario Matrixify (Por SKU)")
st.markdown("""
Esta herramienta actualiza la columna **Inventory Available: Ecommerce** cruzando el **Variant SKU** con el inventario del CEDI.
""")

# -------------------------------------------------
# CARGA DE ARCHIVOS
# -------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    matrixify_file = st.file_uploader("1️⃣ Cargar Archivo Matrixify (Excel)", type=["xlsx"])

with col2:
    cedi_file = st.file_uploader("2️⃣ Cargar Archivo CEDI (Excel)", type=["xlsx"])

# -------------------------------------------------
# LÓGICA DE PROCESAMIENTO
# -------------------------------------------------
if matrixify_file and cedi_file:
    try:
        # 1. Leer Matrixify
        # Usamos engine='openpyxl' explícitamente
        df_matrixify = pd.read_excel(matrixify_file, engine="openpyxl")
        
        # 2. Leer CEDI
        # Nota: A veces los archivos CEDI tienen encabezados en filas inferiores. 
        # Aquí intentamos leer normal, pero limpiamos nombres de columnas.
        df_cedi = pd.read_excel(cedi_file, engine="openpyxl")

        # --- Limpieza de Nombres de Columnas ---
        df_matrixify.columns = df_matrixify.columns.astype(str).str.strip()
        df_cedi.columns = df_cedi.columns.astype(str).str.strip()

        # --- Validación de Columnas Requeridas ---
        col_sku_matrixify = "Variant SKU"
        col_target_matrixify = "Inventory Available: Ecommerce"
        
        # Intentar detectar las columnas del CEDI (basado en tus archivos de muestra)
        # Buscamos 'Código Producto' o 'Variant SKU' y 'Cant. Disponible' o similar
        posibles_cols_sku_cedi = ["Código Producto", "Variant SKU", "SKU"]
        posibles_cols_qty_cedi = ["Cant. Disponible", "Suma de Cant. Disponible", "Disponible", "Inventory"]

        col_sku_cedi = next((c for c in posibles_cols_sku_cedi if c in df_cedi.columns), None)
        col_qty_cedi = next((c for c in posibles_cols_qty_cedi if c in df_cedi.columns), None)

        if not col_sku_cedi or not col_qty_cedi:
            st.error(f"❌ No se encontraron las columnas esperadas en el archivo CEDI.")
            st.write("Columnas detectadas en CEDI:", df_cedi.columns.tolist())
            st.stop()

        # --- Normalización de Datos ---
        # Convertir SKUs a texto y quitar espacios para asegurar el cruce
        df_matrixify[col_sku_matrixify] = df_matrixify[col_sku_matrixify].astype(str).str.strip()
        df_cedi[col_sku_cedi] = df_cedi[col_sku_cedi].astype(str).str.strip()

        # Convertir cantidades a números
        df_cedi[col_qty_cedi] = pd.to_numeric(df_cedi[col_qty_cedi], errors='coerce').fillna(0)

        # --- Creación del Diccionario de Inventario (CEDI) ---
        # Si hay duplicados en CEDI, sumamos las cantidades por SKU
        inventario_cedi = df_cedi.groupby(col_sku_cedi)[col_qty_cedi].sum().to_dict()

        # --- Actualización (EL CRUCE) ---
        # Función para aplicar fila por fila
        def actualizar_stock(row):
            sku = row[col_sku_matrixify]
            # Si el SKU existe en CEDI, devolvemos el valor de CEDI
            if sku in inventario_cedi:
                return inventario_cedi[sku]
            else:
                # Si NO existe en CEDI, ¿qué hacemos?
                # Opción A: Devolver 0 (Asumimos que si no está en CEDI no hay stock)
                return 0 
                # Opción B: Mantener el valor original (Descomenta la línea de abajo si prefieres esto)
                # return row[col_target_matrixify]

        # Verificar si la columna destino existe en Matrixify, si no, crearla
        if col_target_matrixify not in df_matrixify.columns:
            df_matrixify[col_target_matrixify] = 0

        # Aplicar la actualización
        df_matrixify[col_target_matrixify] = df_matrixify.apply(actualizar_stock, axis=1)

        # --- Mostrar Resultados ---
        st.success("✅ ¡Cruce realizado con éxito!")
        
        st.subheader("Vista Previa (Primeras 5 filas actualizadas)")
        st.dataframe(df_matrixify[[col_sku_matrixify, col_target_matrixify]].head())

        # --- Descarga del Archivo ---
        # Guardar en memoria como Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_matrixify.to_excel(writer, index=False)
        
        st.download_button(
            label="⬇️ Descargar Excel para Matrixify",
            data=buffer.getvalue(),
            file_name="Matrixify_Import_Ready.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los archivos: {e}")

else:
    st.info("👆 Por favor sube ambos archivos para comenzar.")