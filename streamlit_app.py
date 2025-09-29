import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytesseract
from PIL import Image
import io
import matplotlib.pyplot as plt

# =========================
# CONFIGURAÇÃO DO APP
# =========================
st.set_page_config(page_title="Apostas OCR", layout="wide")

# =========================
# BANCO DE DADOS
# =========================
def init_db():
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            criado_em TEXT,
            grupo TEXT,
            casa TEXT,
            descricao TEXT,
            valor REAL,
            retorno REAL,
            odd REAL,
            lucro REAL,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    lucro = retorno - valor if status == "Green" else -valor if status == "Red" else 0
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, odd, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, valor, retorno, odd, lucro, status))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
    conn.close()
    return df

# =========================
# OCR
# =========================
def process_image(uploaded_file):
    if uploaded_file is None:
        return {}

    image = Image.open(uploaded_file)
    text = pytesseract.image_to_string(image, lang="por").lower()

    # Inicializa dicionário com valores padrão
    data = {
        "grupo": "",
        "casa": "",
        "descricao": text[:50],
        "valor": 0.0,
        "retorno": 0.0,
        "odd": 1.01,
        "status": "Void"
    }

    # Detecta status
    if "green" in text:
        data["status"] = "Green"
    elif "red" in text:
        data["status"] = "Red"
    elif "void" in text:
        data["status"] = "Void"

    # Detecta valores
    import re
    numeros = re.findall(r"\d+[,.]?\d*", text)
    if numeros:
        try:
            data["valor"] = float(numeros[0].replace(",", "."))
            if len(numeros) > 1:
                data["retorno"] = float(numeros[1].replace(",", "."))
                data["odd"] = round(data["retorno"] / data["valor"], 2) if data["valor"] > 0 else 1.01
        except:
            pass

    return data

# =========================
# INTERFACE
# =========================
st.title("📊 Controle de Apostas com OCR")

init_db()

uploaded_file = st.file_uploader("Envie o print da aposta", type=["png", "jpg", "jpeg"])
ocr_data = process_image(uploaded_file) if uploaded_file else {}

with st.form("nova_aposta"):
    grupo = st.text_input("Grupo", value=ocr_data.get("grupo", ""))
    casa = st.text_input("Casa", value=ocr_data.get("casa", ""))
    descricao = st.text_area("Descrição", value=ocr_data.get("descricao", ""))
    valor = st.number_input("Valor", min_value=0.0, value=float(ocr_data.get("valor", 0.0)), step=1.0)
    retorno = st.number_input("Retorno", min_value=0.0, value=float(ocr_data.get("retorno", 0.0)), step=1.0)
    odd = st.number_input("Odd", min_value=1.01, value=float(ocr_data.get("odd", 1.01)), step=0.01)
    status = st.selectbox("Status", ["Green", "Red", "Void"], index=["Green", "Red", "Void"].index(ocr_data.get("status", "Void")))

    submit = st.form_submit_button("Salvar")

    if submit:
        add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status)
        st.success("✅ Aposta salva com sucesso!")
        st.experimental_rerun()

st.divider()

# =========================
# RESUMO E GRÁFICOS
# =========================
df = load_bets_df()

if df.empty:
    st.info("Nenhuma aposta registrada ainda.")
else:
    st.subheader("📋 Histórico de Apostas")
    st.dataframe(df)

    st.subheader("📈 Resumo")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Investido", f"R$ {df['valor'].sum():.2f}")
    with col2:
        st.metric("Retorno Total", f"R$ {df['retorno'].sum():.2f}")
    with col3:
        st.metric("Lucro/Prejuízo", f"R$ {df['lucro'].sum():.2f}")

    st.subheader("📊 Gráficos")
    col1, col2 = st.columns(2)

    with col1:
        fig, ax = plt.subplots()
        df["status"].value_counts().plot(kind="pie", autopct="%1.1f%%", ax=ax)
        ax.set_ylabel("")
        ax.set_title("Distribuição por Status")
        st.pyplot(fig)

    with col2:
        fig, ax = plt.subplots()
        df.groupby("casa")["lucro"].sum().plot(kind="bar", ax=ax)
        ax.set_title("Lucro por Casa")
        st.pyplot(fig)
