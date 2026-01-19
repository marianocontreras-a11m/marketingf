# app_streamlit_estado_modelo.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ============================================
# CONFIGURACIÓN DE LA APP
# ============================================
st.set_page_config(
    page_title="Pricing por Estado · Factor X",
    page_icon="null",
    layout="wide"
)

st.markdown("""
<style>
div[data-testid="stMetric"] {
  background: #FFFFFF;
  border: 1px solid #EEE;
  border-radius: 14px;
  padding: 12px 16px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.05);
}
section[data-testid="stSidebar"] { background: #fafafa; }
.block-container { padding-top: 1.2rem; }
hr { margin: 0.8rem 0; }
</style>
""", unsafe_allow_html=True)

st.title("Dashboard de Pricing por Estado · Modelo Factor X")

# =====================================================
# CARGA DE DATOS (USUARIO SUBE CSV)
# =====================================================
st.sidebar.header("📂 Carga de datos")

uploaded_file = st.sidebar.file_uploader(
    "Sube el archivo estado_master.csv",
    type=["csv"]
)

@st.cache_data(show_spinner=False)
def load_data(file):
    df = pd.read_csv(file)

    # Normalizar nombre de columna
    df = df.rename(columns={"Conversion_%": "Conversion_Rate"})

    # Limpiar conversión si viene como texto
    df["Conversion_Rate"] = (
        df["Conversion_Rate"]
        .astype(str)
        .str.replace(",", "")
        .str.replace("%", "")
        .astype(float)
    )

    return df

if uploaded_file is None:
    st.info("⬅️ Sube un archivo CSV para comenzar.")
    st.stop()

df = load_data(uploaded_file)

# =====================================================
# AJUSTE AUTOMÁTICO DE CONVERSIÓN
# =====================================================
OBJETIVO = 0.028  # 2.8%

region_factor = {
    "Centro": 0.92,
    "Occidente": 1.05,
    "Bajío": 0.98,
    "Noreste": 1.02,
    "Sureste": 0.90,
    "Golfo": 0.97,
    "Noroeste": 1.01,
    "Sur": 0.93
}

df["Factor_regional"] = df["Region"].map(region_factor).fillna(1.00)

df["Conversion_Rate"] = np.where(
    df["Conversion_Rate"] > 5.0,
    OBJETIVO * df["Factor_regional"] * 100,
    df["Conversion_Rate"]
)

df["Leads_convertidos"] = (
    df["Leads_estimados"] * (df["Conversion_Rate"] / 100)
).round().astype(int)

# =====================================================
# PARÁMETROS DEL MODELO
# =====================================================
precio_ideal_global = st.sidebar.number_input(
    "Precio ideal global (MXN)",
    min_value=0.0, max_value=10000.0,
    value=1800.0, step=50.0
)

factor_x = st.sidebar.slider(
    "Factor X (ancho de banda)",
    0.02, 0.20, 0.05, 0.01
)

# Filtro por estado
estados = sorted(df["Estado"].unique())
sel_estados = st.sidebar.multiselect(
    "Filtrar por estados",
    estados,
    default=estados
)

df_f = df[df["Estado"].isin(sel_estados)].copy()

if df_f.empty:
    st.warning("⚠️ No hay datos para los estados seleccionados.")
    st.stop()

# =====================================================
# KPIs GENERALES
# =====================================================
total_leads = int(df_f["Leads_estimados"].sum())
total_conv = int(df_f["Leads_convertidos"].sum())
conv_rate = (total_conv / total_leads * 100) if total_leads else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Leads estimados", f"{total_leads:,}")
c2.metric("Leads convertidos", f"{total_conv:,}")
c3.metric("Tasa de conversión", f"{conv_rate:.2f}%")
c4.metric("Estados activos", f"{len(sel_estados)}")

# =====================================================
# GRÁFICAS Y TABLAS
# =====================================================
st.subheader("Leads y conversión por estado")

summary = df_f[[
    "Estado", "Region", "Leads_estimados",
    "Conversion_Rate", "Leads_convertidos"
]]

chart = alt.Chart(summary).mark_bar().encode(
    x=alt.X("Estado:N", sort="-y"),
    y=alt.Y("Leads_estimados:Q", title="Leads"),
    color="Region:N",
    tooltip=list(summary.columns)
).properties(height=400)

st.altair_chart(chart, use_container_width=True)
st.dataframe(
    summary.sort_values("Leads_estimados", ascending=False),
    use_container_width=True
)

# =====================================================
# PRECIOS RECOMENDADOS
# =====================================================
st.subheader("Recomendación de precio por estado")

df_f["Precio_Ideal"] = precio_ideal_global
df_f["Banda_Baja"] = df_f["Precio_Ideal"] * (1 - factor_x)
df_f["Banda_Alta"] = df_f["Precio_Ideal"] * (1 + factor_x)

st.dataframe(
    df_f[["Estado", "Region", "Precio_Ideal", "Banda_Baja", "Banda_Alta"]].round(2),
    use_container_width=True
)

# =====================================================
# SIMULADOR
# =====================================================
st.subheader("Simulador de precio por estado")

estado_sim = st.selectbox("Selecciona un estado", sel_estados)
row = df_f[df_f["Estado"] == estado_sim].iloc[0]

conv_base = row["Conversion_Rate"] / 100
leads_estado = row["Leads_estimados"]

precio_propuesto = st.number_input(
    "Precio propuesto (MXN)",
    value=float(precio_ideal_global),
    step=10.0
)

gap = (precio_propuesto - precio_ideal_global) / precio_ideal_global * 100

if precio_propuesto < df_f["Banda_Baja"].iloc[0]:
    mult = 1 + min(0.4, abs(gap) / 10 * 0.2)
    mensaje = "📉 Precio bajo → posible mejora en conversión"
elif precio_propuesto > df_f["Banda_Alta"].iloc[0]:
    mult = 1 - min(0.4, abs(gap) / 10 * 0.2)
    mensaje = "📈 Precio alto → posible caída en conversión"
else:
    mult = 1.0
    mensaje = "✔️ Precio dentro de banda → conversión estable"

conv_pred = conv_base * mult
inscritos_est = int(leads_estado * conv_pred)
ingresos_est = inscritos_est * precio_propuesto

st.write(mensaje)
st.metric("Conversión base", f"{conv_base*100:.2f}%")
st.metric("Conversión estimada", f"{conv_pred*100:.2f}%")
st.metric("Inscritos estimados", f"{inscritos_est:,}")
st.metric("Ingresos estimados", f"${ingresos_est:,.0f} MXN")

# =====================================================
# DESCARGA
# =====================================================
st.subheader("Descarga de resultados")

csv = df_f.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Descargar CSV completo",
    data=csv,
    file_name="estado_pricing_resultados.csv",
    mime="text/csv"
)

st.markdown("---")
st.caption("Modelo por Estado con Factor X — Streamlit Demo.")
