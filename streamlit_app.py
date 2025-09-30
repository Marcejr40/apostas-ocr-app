import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt
from datetime import datetime

# ==============================
# Configuração inicial
# ==============================
st.set_page_config(page_title="Gestor de Apostas OCR", layout="wide")

# Banco de dados SQLite
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
            odd REAL,
            valor REAL,
            retorno REAL,
            lucro REAL,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==============================
# Funções auxiliares
# ==============================
def add_bet(grupo, casa, descricao, odd, valor, retorno, status):
    lucro = float(retorno) - float(valor)
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, odd, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          grupo, casa, descricao, odd, valor, retorno, lucro, status))
    conn.commit()
    conn.close()

def load_bets():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
    conn.close()
    return df

def ocr_extract(image):
    try:
        text = pytesseract.image_to_string(image, lang="por").lower()
        return text
    except Exception as e:
        return f"Erro OCR: {e}"

def classify_status(text):
    if "green" in text:
        return "Green"
    elif "red" in text:
        return "Red"
    elif "void" in text:
        return "Void"
    else:
        return "Indefinido"

# ==============================
# Interface principal
# ==============================
st.title("📊 Gestor de Apostas com OCR")

# Upload de imagem
uploaded_file = st.file_uploader("Envie um print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagem enviada", use_container_width=True)

    extracted_text = ocr_extract(image)
    st.write("📑 Texto reconhecido:", extracted_text)

    status_detected = classify_status(extracted_text)

    with st.form("form_aposta"):
        grupo = st.text_input("Grupo", "Grupo 1")
        casa = st.text_input("Casa", "Betano")
        descricao = st.text_area("Descrição", extracted_text)
        odd = st.number_input("Odd", min_value=1.01, value=1.50, step=0.01)
        valor = st.number_input("Valor apostado (R$)", min_value=0.0, value=10.0, step=1.0)
        retorno = st.number_input("Retorno (R$)", min_value=0.0, value=0.0, step=1.0)
        status = st.selectbox("Status", ["Green", "Red", "Void", "Indefinido"], index=["Green", "Red", "Void", "Indefinido"].index(status_detected))

        submitted = st.form_submit_button("Salvar aposta")

        if submitted:
            add_bet(grupo, casa, descricao, odd, valor, retorno, status)
            st.success("✅ Aposta salva com sucesso!")

# ==============================
# Resumo e relatórios
# ==============================
st.subheader("📌 Histórico de Apostas")
df = load_bets()

if not df.empty:
    st.dataframe(df, use_container_width=True)

    # Resumo geral
    total_apostas = len(df)
    total_lucro = df["lucro"].sum()
    total_green = len(df[df["status"] == "Green"])
    total_red = len(df[df["status"] == "Red"])
    total_void = len(df[df["status"] == "Void"])

    st.metric("Total de apostas", total_apostas)
    st.metric("Lucro/Prejuízo total (R$)", round(total_lucro, 2))
    st.metric("Greens", total_green)
    st.metric("Reds", total_red)
    st.metric("Voids", total_void)

    # Gráficos
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("📊 Lucro por Grupo")
        fig, ax = plt.subplots()
        df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax, color="skyblue")
        st.pyplot(fig)

    with col2:
        st.write("📊 Lucro por Casa")
        fig, ax = plt.subplots()
        df.groupby("casa")["lucro"].sum().plot(kind="bar", ax=ax, color="orange")
        st.pyplot(fig)

    with col3:
        st.write("📊 Status das Apostas")
        fig, ax = plt.subplots()
        df["status"].value_counts().plot(kind="pie", autopct="%1.0f%%", ax=ax)
        st.pyplot(fig)
else:
    st.info("Nenhuma aposta registrada ainda.")
