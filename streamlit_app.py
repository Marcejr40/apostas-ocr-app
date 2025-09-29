import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from rapidfuzz import fuzz
import pytesseract
from PIL import Image

# ---- BANCO DE DADOS (SQLite) ----
def init_db():
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            grupo TEXT,
            casa TEXT,
            descricao TEXT,
            valor REAL,
            retorno REAL,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_bet(data, grupo, casa, descricao, valor, retorno, status):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("INSERT INTO bets (data, grupo, casa, descricao, valor, retorno, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (data, grupo, casa, descricao, valor, retorno, status))
    conn.commit()
    conn.close()

def get_bets():
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("SELECT * FROM bets")
    rows = c.fetchall()
    conn.close()
    return rows

# ---- DETECÇÃO DE STATUS (Green, Red, Void) ----
def detectar_status(text):
    text_lower = text.lower()

    if fuzz.partial_ratio(text_lower, "green") > 65 or any(x in text_lower for x in ["gren", "grenn", "ganho", "vencida", "gree", "grern", "grcn"]):
        return "Green"
    elif fuzz.partial_ratio(text_lower, "red") > 80 or any(x in text_lower for x in ["perdida", "loss"]):
        return "Red"
    elif fuzz.partial_ratio(text_lower, "void") > 70 or any(x in text_lower for x in ["anulada", "cancelada"]):
        return "Void"
    else:
        return "Pendente"

# ---- INICIALIZA BANCO ----
init_db()

# ---- INTERFACE STREAMLIT ----
st.set_page_config(page_title="OCR Apostas", page_icon="📊", layout="wide")
st.title("📊 OCR Apostas com Banco de Dados (SQLite)")

uploaded_file = st.file_uploader("📤 Envie um print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="🖼️ Imagem enviada", use_container_width=True)

    try:
        text = pytesseract.image_to_string(image, lang="por")
        st.text_area("📝 Texto reconhecido:", text, height=150)

        status = detectar_status(text)

        grupo = st.text_input("👥 Grupo")
        casa = st.text_input("🏠 Casa de Aposta")
        descricao = st.text_input("📌 Descrição da aposta")
        valor = st.number_input("💰 Valor apostado (R$)", min_value=0.0, step=1.0)
        retorno = st.number_input("🎯 Retorno esperado (R$)", min_value=0.0, step=1.0)

        if st.button("💾 Salvar aposta"):
            add_bet(datetime.now().strftime("%d/%m/%Y %H:%M"), grupo, casa, descricao, valor, retorno, status)
            st.success("✅ Aposta salva no banco de dados!")

    except Exception as e:
        st.error(f"⚠️ Erro ao executar OCR: {e}")

# ---- DASHBOARD ----
st.subheader("📈 Histórico de apostas")

dados = get_bets()
if dados:
    df = pd.DataFrame(dados, columns=["ID", "Data", "Grupo", "Casa", "Descrição", "Valor", "Retorno", "Status"])
    st.dataframe(df, use_container_width=True)

    # Gráfico por status
    st.subheader("📊 Lucro/Prejuízo por Status")
    st.bar_chart(df.groupby("Status")["Valor"].sum())

    # Gráfico por grupo
    if "Grupo" in df.columns:
        st.subheader("👥 Distribuição por Grupo")
        st.bar_chart(df.groupby("Grupo")["Valor"].sum())

else:
    st.info("ℹ️ Nenhuma aposta registrada ainda.")
