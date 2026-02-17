import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import time

# -------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# -------------------------------------------------
st.set_page_config(
    page_title="Clemont Stock Manager",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS personalizados para mejorar la apariencia
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        background-color: #000000;
        color: white;
        border-radius: 5px;
        height: 50px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #333333;
        color: white;
        border: none;
    }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    h1 { color: #1a1a1a; }
    h3 { color: #333333; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 Clemont Stock Manager")
st.caption("Herramienta de sincronización de inventario: CEDI ➡️ Matrixify (Shopify)")
st.markdown("---")

# -------------------------------------------------
# 2. FUNCIONES DE CARGA INTELIGENTE
# -------------------------------------------------
def cargar_cedi_inteligente(file, columna_clave="Código Producto"):
    """Busca la fila que contiene 'Código Producto' para usarla como encabezado."""
    try:
        df_preview = pd.read_excel(file, engine="openpyxl", header=None, nrows=20)
        fila_header = None
        for i, row in df_preview.iterrows():
            fila_texto = [str(celda).strip() for celda in row.values]
            if columna_clave in fila_texto:
                fila_header = i
                break
        
        file.seek(0)
        if fila_header is not None:
            return pd.read_excel(file, engine="openpyxl", header=fila_header)
        else:
            return pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        return None

# -------------------------------------------------
# 3. INTERFAZ DE CARGA (PASOS 1 y 2)
# -------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    # INTENTA CARGAR ICONO SI EXISTE, SI NO USA EMOJI
    # st.image("shopify_icon.svg", width=50) # Descomentar si tienes el archivo
    st.subheader("🛍️ Paso 1: Shopify")
    st.markdown("**Carga el archivo exportado de Matrixify**")
    matrixify_file = st.file_uploader("Subir Excel Matrixify", type=["xlsx"], key="mat")

with col2:
    # INTENTA CARGAR ICONO SI EXISTE, SI NO USA EMOJI
    # st.image("cedi_icon.png", width=50) # Descomentar si tienes el archivo
    st.subheader("🏭 Paso 2: CEDI")
    st.markdown("**Carga el inventario del CEDI**")
    cedi_file = st.file_uploader("Subir Excel CEDI", type=["xlsx"], key="cedi")

# -------------------------------------------------
# 4. PROCESAMIENTO
# -------------------------------------------------
if matrixify_file and cedi_file:
    st.markdown("---")
    
    # Botón grande para iniciar
    if st.button("🚀 ANALIZAR Y ACTUALIZAR INVENTARIO"):
        
        # --- FASE 1: ANALIZANDO ---
        with st.status("🔍 Procesando archivos...", expanded=True) as status:
            
            st.write("📂 Leyendo archivo Matrixify...")
            df_matrixify = pd.read_excel(matrixify_file, engine="openpyxl")
            time.sleep(0.5) # Pequeña pausa para UX
            
            st.write("📂 Analizando estructura del CEDI...")
            df_cedi = cargar_cedi_inteligente(cedi_file, "Código Producto")
            
            if df_cedi is None:
                status.update(label="❌ Error al leer CEDI", state="error")
                st.stop()

            # Limpieza de columnas
            df_matrixify.columns = df_matrixify.columns.astype(str).str.strip()
            df_cedi.columns = df_cedi.columns.astype(str).str.strip()

            # Definición de Columnas
            col_sku_mat = "Variant SKU"
            col_inv_mat = "Inventory Available: Ecommerce"
            col_sku_cedi = "Código Producto"
            
            posibles_cant = ["Cant. Disponible", "Suma de Cant. Disponible", "Disponible", "Saldo"]
            col_cant_cedi = next((c for c in posibles_cant if c in df_cedi.columns), None)

            # Validaciones
            errores = []
            if col_sku_mat not in df_matrixify.columns:
                errores.append(f"Falta columna '{col_sku_mat}' en Matrixify")
            if col_sku_cedi not in df_cedi.columns:
                errores.append(f"Falta columna '{col_sku_cedi}' en CEDI")
            if not col_cant_cedi:
                errores.append("No se encontró columna de cantidad en CEDI")

            if errores:
                for e in errores:
                    st.error(f"❌ {e}")
                status.update(label="❌ Error en validación", state="error")
                st.stop()
            
            st.write("✅ Estructura validada correctamente.")
            
            # --- FASE 2: ACTUALIZANDO ---
            st.write("🔄 Cruzando bases de datos...")
            
            # Normalización
            df_matrixify[col_sku_mat] = df_matrixify[col_sku_mat].astype(str).str.strip()
            df_cedi[col_sku_cedi] = df_cedi[col_sku_cedi].astype(str).str.strip()
            df_cedi[col_cant_cedi] = pd.to_numeric(df_cedi[col_cant_cedi], errors='coerce').fillna(0)

            # Diccionario de Inventario CEDI
            inventario_dict = df_cedi.groupby(col_sku_cedi)[col_cant_cedi].sum().to_dict()

            # Contadores para reporte
            total_skus = len(df_matrixify)
            skus_encontrados = 0
            skus_no_encontrados = 0
            cambios_realizados = 0

            # Lógica de Actualización
            nuevos_valores = []
            estados = []

            for idx, row in df_matrixify.iterrows():
                sku = row[col_sku_mat]
                stock_actual_shopify = row.get(col_inv_mat, 0)
                
                if sku in inventario_dict:
                    nuevo_stock = inventario_dict[sku]
                    skus_encontrados += 1
                else:
                    nuevo_stock = 0 # OJO: Asume 0 si no está en CEDI
                    skus_no_encontrados += 1
                
                # Detectar si hubo cambio real
                if stock_actual_shopify != nuevo_stock:
                    cambios_realizados += 1
                    estados.append("Actualizado")
                else:
                    estados.append("Sin cambios")
                
                nuevos_valores.append(nuevo_stock)

            # Asignar columna
            df_matrixify[col_inv_mat] = nuevos_valores
            
            status.update(label="✅ ¡Proceso completado!", state="complete", expanded=False)

        # -------------------------------------------------
        # 5. RESULTADOS Y DESCARGA
        # -------------------------------------------------
        st.success("Inventario procesado exitosamente")

        # Métricas visuales
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric(label="🔄 Cambios Encontrados", value=cambios_realizados)
        with m2:
            st.metric(label="✅ SKUs Cruzados (CEDI)", value=skus_encontrados)
        with m3:
            st.metric(label="⚠️ Anomalías (No en CEDI)", value=skus_no_encontrados, delta_color="inverse")

        if skus_no_encontrados > 0:
            with st.expander("Ver lista de anomalías (SKUs en Shopify que no están en CEDI)"):
                # Filtrar y mostrar los que no se encontraron (suponiendo que su nuevo stock es 0)
                anomalias = df_matrixify[~df_matrixify[col_sku_mat].isin(inventario_dict.keys())]
                st.dataframe(anomalias[[col_sku_mat, "Title"]].head(100))
                st.caption("*Estos productos se ajustaron a 0 unidades.*")

        # Preparar archivo de descarga
        fecha_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        nombre_archivo = f"Actualizacion_Inventario_Ecommerce_{fecha_str}.xlsx"
        
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_matrixify.to_excel(writer, index=False)
        
        st.markdown("### 📥 Descargar Resultado")
        st.download_button(
            label=f"Descargar Excel: {nombre_archivo}",
            data=buffer.getvalue(),
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary" 
        )

else:
    # Mensaje inicial cuando está vacío
    st.info("👋 Sube ambos archivos para activar el botón de procesamiento.")