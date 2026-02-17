import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import time

# -------------------------------------------------
# 1. CONFIGURACIÓN DE LA PÁGINA
# -------------------------------------------------
st.set_page_config(
    page_title="Clemont Stock Manager Pro",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS
st.markdown("""
    <style>
    .main { background-color: #f4f6f9; }
    .stButton>button {
        width: 100%; border-radius: 8px; height: 55px; font-weight: bold;
        background-color: #0f172a; color: white; border: none;
    }
    .stButton>button:hover { background-color: #334155; color: white; }
    .metric-container {
        background-color: white; padding: 15px; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;
    }
    div[data-testid="stMetricValue"] { font-size: 24px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 Clemont Stock Manager Pro")
st.caption("Auditoría y Sincronización: CEDI ➡️ Matrixify")

# -------------------------------------------------
# 2. FUNCIONES DE CARGA INTELIGENTE
# -------------------------------------------------
def cargar_cedi_inteligente(file, columna_clave="Código Producto"):
    try:
        # Lee primeras 20 filas para buscar encabezado
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
    except Exception:
        return None

# -------------------------------------------------
# 3. INTERFAZ DE CARGA
# -------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.info("📂 Paso 1: Archivo Matrixify (Shopify)")
    matrixify_file = st.file_uploader("Sube el export de Matrixify", type=["xlsx"], key="mat")

with col2:
    st.warning("🏭 Paso 2: Archivo CEDI")
    cedi_file = st.file_uploader("Sube el inventario del CEDI", type=["xlsx"], key="cedi")

# -------------------------------------------------
# 4. PROCESAMIENTO
# -------------------------------------------------
if matrixify_file and cedi_file:
    
    if st.button("🚀 AUDITAR Y PROCESAR INVENTARIO"):
        
        with st.status("⚙️ Procesando datos...", expanded=True) as status:
            
            # --- CARGA Y LIMPIEZA ---
            st.write("📖 Leyendo archivos...")
            df_mat = pd.read_excel(matrixify_file, engine="openpyxl")
            df_cedi = cargar_cedi_inteligente(cedi_file, "Código Producto")

            # Normalizar nombres de columnas
            df_mat.columns = df_mat.columns.astype(str).str.strip()
            df_cedi.columns = df_cedi.columns.astype(str).str.strip()

            # Definir columnas clave
            col_sku_mat = "Variant SKU"
            col_inv_mat = "Inventory Available: Ecommerce" # Columna destino
            col_sku_cedi = "Código Producto"
            
            # Buscar columna de cantidad en CEDI
            posibles_cant = ["Cant. Disponible", "Suma de Cant. Disponible", "Disponible", "Saldo", "Total"]
            col_cant_cedi = next((c for c in posibles_cant if c in df_cedi.columns), None)

            if not col_cant_cedi:
                status.update(label="❌ Error: No se encontró columna de cantidad en CEDI", state="error")
                st.stop()

            # Normalizar SKUs (texto y sin espacios)
            df_mat[col_sku_mat] = df_mat[col_sku_mat].astype(str).str.strip()
            df_cedi[col_sku_cedi] = df_cedi[col_sku_cedi].astype(str).str.strip()
            
            # Normalizar Cantidades
            df_cedi[col_cant_cedi] = pd.to_numeric(df_cedi[col_cant_cedi], errors='coerce').fillna(0)
            
            # Asegurar que la columna de inventario existe en Matrixify (si es archivo nuevo)
            if col_inv_mat not in df_mat.columns:
                df_mat[col_inv_mat] = 0
            else:
                df_mat[col_inv_mat] = pd.to_numeric(df_mat[col_inv_mat], errors='coerce').fillna(0)

            # --- LÓGICA DE CRUCE Y AUDITORÍA ---
            st.write("🔄 Cruzando referencias...")
            
            # Agrupar CEDI (Diccionario maestro)
            inventario_cedi = df_cedi.groupby(col_sku_cedi)[col_cant_cedi].sum().to_dict()
            
            # Listas para el reporte detallado
            reporte_audit = []
            skus_procesados_shopify = set()

            # Iterar sobre Shopify (Matrixify)
            for idx, row in df_mat.iterrows():
                sku = row[col_sku_mat]
                stock_old = float(row[col_inv_mat])
                skus_procesados_shopify.add(sku)
                
                # Buscar en CEDI
                if sku in inventario_cedi:
                    stock_new = float(inventario_cedi[sku])
                    en_cedi = True
                else:
                    stock_new = 0.0
                    en_cedi = False
                
                # Clasificación de Anomalía
                tipo_cambio = "Sin Cambios"
                
                if not en_cedi:
                    if stock_old > 0:
                        tipo_cambio = "⚠️ Fantasma (En Shopify, No en CEDI)"
                        # Acción: Se pone a 0
                    else:
                        tipo_cambio = "Sin Stock (Ambos 0)"
                else:
                    if stock_new == 0 and stock_old > 0:
                        tipo_cambio = "🔴 Agotado (Stockout)"
                    elif stock_new > stock_old:
                        tipo_cambio = "📈 Subió Stock"
                    elif stock_new < stock_old:
                        tipo_cambio = "📉 Bajó Stock"
                
                # Guardar dato para reporte
                reporte_audit.append({
                    "SKU": sku,
                    "Nombre": row.get("Title", "N/A"), # Intentar obtener nombre
                    "Stock Anterior (Shopify)": stock_old,
                    "Stock Nuevo (CEDI)": stock_new,
                    "Diferencia": stock_new - stock_old,
                    "Estado": tipo_cambio
                })

                # Actualizar el DataFrame original para la descarga de Matrixify
                df_mat.at[idx, col_inv_mat] = stock_new

            # --- BUSCAR SKUS QUE ESTÁN EN CEDI PERO NO EN SHOPIFY ---
            todos_skus_cedi = set(inventario_cedi.keys())
            skus_nuevos_en_cedi = todos_skus_cedi - skus_procesados_shopify
            
            for sku_nuevo in skus_nuevos_en_cedi:
                 reporte_audit.append({
                    "SKU": sku_nuevo,
                    "Nombre": "Desconocido (Solo en CEDI)",
                    "Stock Anterior (Shopify)": 0,
                    "Stock Nuevo (CEDI)": inventario_cedi[sku_nuevo],
                    "Diferencia": inventario_cedi[sku_nuevo],
                    "Estado": "🆕 Nuevo en CEDI (No en Shopify)"
                })

            # Crear DataFrame de Auditoría
            df_audit = pd.DataFrame(reporte_audit)
            
            status.update(label="✅ Análisis completado", state="complete", expanded=False)

        # -------------------------------------------------
        # 5. DASHBOARD DE RESULTADOS
        # -------------------------------------------------
        
        # Filtrar DataFrames por estado
        df_subieron = df_audit[df_audit["Estado"] == "📈 Subió Stock"]
        df_bajaron = df_audit[df_audit["Estado"] == "📉 Bajó Stock"]
        df_agotados = df_audit[df_audit["Estado"] == "🔴 Agotado (Stockout)"]
        df_fantasmas = df_audit[df_audit["Estado"] == "⚠️ Fantasma (En Shopify, No en CEDI)"]
        df_nuevos_cedi = df_audit[df_audit["Estado"] == "🆕 Nuevo en CEDI (No en Shopify)"]

        # Métricas Generales
        st.subheader("📊 Resumen de Impacto")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Stock Subió", f"{len(df_subieron)} SKUs", delta="Ingreso mercancía")
        m2.metric("Stock Bajó", f"{len(df_bajaron)} SKUs", delta="-Ventas/Ajustes", delta_color="inverse")
        m3.metric("Se Agotaron", f"{len(df_agotados)} SKUs", delta="Stockout crítico", delta_color="inverse")
        m4.metric("No encontrados", f"{len(df_fantasmas)} SKUs", help="Están en Shopify con stock, pero no aparecen en el archivo CEDI")

        # Pestañas de Detalle
        st.markdown("### 🔎 Detalle por Categoría")
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Subieron", 
            "📉 Bajaron", 
            "🔴 Agotados", 
            "⚠️ Fantasmas (Shopify)", 
            "🆕 Nuevos (CEDI)"
        ])

        with tab1:
            st.dataframe(df_subieron, use_container_width=True)
        
        with tab2:
            st.dataframe(df_bajaron, use_container_width=True)
            
        with tab3:
            st.caption("Estos productos tenían inventario y ahora quedaron en 0.")
            st.dataframe(df_agotados, use_container_width=True)
            
        with tab4:
            st.error(f"⚠️ Hay {len(df_fantasmas)} productos que tienen stock en Shopify, pero NO aparecen en el CEDI. El sistema los ajustará a 0 para prevenir sobreventas.")
            st.dataframe(df_fantasmas, use_container_width=True)
            
        with tab5:
            st.info(f"🆕 Hay {len(df_nuevos_cedi)} productos en el CEDI que NO existen en tu archivo de Shopify. No se pueden cargar a Shopify hasta que crees el producto.")
            st.dataframe(df_nuevos_cedi, use_container_width=True)

        # -------------------------------------------------
        # 6. DESCARGAS
        # -------------------------------------------------
        st.markdown("---")
        st.subheader("📥 Descargar Archivos")

        col_d1, col_d2 = st.columns(2)
        
        # Archivo 1: Matrixify (El funcional)
        buffer_mat = BytesIO()
        with pd.ExcelWriter(buffer_mat, engine="openpyxl") as writer:
            df_mat.to_excel(writer, index=False)
        
        fecha_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        
        col_d1.download_button(
            label="⬇️ Archivo para Matrixify (Importar)",
            data=buffer_mat.getvalue(),
            file_name=f"Update_Inventario_Matrixify_{fecha_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            help="Este es el archivo que debes subir a Matrixify app"
        )

        # Archivo 2: Auditoría (El reporte)
        buffer_audit = BytesIO()
        with pd.ExcelWriter(buffer_audit, engine="openpyxl") as writer:
            df_audit.to_excel(writer, index=False)
            
        col_d2.download_button(
            label="📊 Descargar Reporte de Auditoría (Excel)",
            data=buffer_audit.getvalue(),
            file_name=f"Reporte_Auditoria_Stocks_{fecha_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Excel con el detalle de qué subió, qué bajó y errores encontrados"
        )

else:
    # Mensaje de bienvenida
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 50px;">
        <h3>👋 Bienvenido al Gestor de Stock Clemont</h3>
        <p>Por favor carga tus archivos arriba para comenzar el análisis.</p>
    </div>
    """, unsafe_allow_html=True)