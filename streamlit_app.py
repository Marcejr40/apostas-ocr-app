import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import pytesseract
import sqlite3
import re
from datetime import datetime

# ==============================
# Configuração inicial
# ==============================
st.set_page_config(page_title="Controle de Apostas", layout="wide")

# ==============================
# Funções de Banco de Dados
# ==============================
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

def add_bet(grupo, casa, descricao, odd, valor, retorno, status):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    lucro = retorno - valor if status == "Green" else (-valor if status == "Red" else 0)
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, odd, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, odd, valor, retorno, lucro, status))
    conn.commit()
    conn.close()

def load_bets():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
    conn.close()
    return df

# ==============================
# OCR e Extração
# ==============================
def ocr_extract(image):
    try:
        return pytesseract.image_to_string(image, lang="por")
    except Exception as e:
        return f"Erro ao executar OCR: {e}"

def classify_status(text):
    text_lower = text.lower()
    if "green" in text_lower or "ganho" in text_lower:
        return "Green"
    elif "red" in text_lower or "perdeu" in text_lower:
        return "Red"
    elif "void" in text_lower or "anulado" in text_lower:
        return "Void"
    return "Indefinido"

def extract_values_from_text(text):
    valor, retorno = 0.0, 0.0
    status = classify_status(text)
    valores = re.findall(r"(\d+[.,]?\d*)", text)
    if valores:
        try:
            valor = float(valores[0].replace(",", "."))
            if len(valores) > 1:
                retorno = float(valores[1].replace(",", "."))
        except:
            pass
    return valor, retorno, status

# ==============================
# Interface
# ==============================
st.title("📊 Controle de Apostas com OCR")

init_db()

uploaded_file = st.file_uploader("Envie um print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagem enviada", use_container_width=True)

    extracted_text = ocr_extract(image)
    st.write("📑 Texto reconhecido:", extracted_text)

    # 🔹 Pré-preenchimento
    valor_detectado, retorno_detectado, status_detected = extract_values_from_text(extracted_text)

    with st.form("form_aposta"):
        grupo = st.text_input("Grupo", "Grupo 1")
        casa = st.text_input("Casa", "Betano")
        descricao = st.text_area("Descrição", extracted_text)
        odd = st.number_input("Odd", min_value=1.01, value=1.50, step=0.01)
        valor = st.number_input("Valor apostado (R$)", min_value=0.0, value=valor_detectado, step=1.0)
        retorno = st.number_input("Retorno (R$)", min_value=0.0, value=retorno_detectado, step=1.0)
        status = st.selectbox("Status", ["Green", "Red", "Void", "Indefinido"],
                              index=["Green", "Red", "Void", "Indefinido"].index(status_detected))

        submitted = st.form_submit_button("Salvar aposta")

        if submitted:
            add_bet(grupo, casa, descricao, odd, valor, retorno, status)
            st.success("✅ Aposta salva com sucesso!")

# ==============================
# Dashboard
# ==============================
st.header("📈 Dashboard")

df = load_bets()
if not df.empty:
    st.dataframe(df)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Lucro por Grupo")
        fig, ax = plt.subplots()
        df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax, color="skyblue")
        st.pyplot(fig)

    with col2:
        st.subheader("Distribuição por Status")
        fig, ax = plt.subplots()
        df["status"].value_counts().plot(kind="pie", autopct="%1.1f%%", ax=ax)
        st.pyplot(fig)

    st.subheader("Evolução do Lucro")
    df["criado_em"] = pd.to_datetime(df["criado_em"])
    df = df.sort_values("criado_em")
    fig, ax = plt.subplots()
    df.set_index("criado_em")["lucro"].cumsum().plot(ax=ax, color="green")
    st.pyplot(fig)
else:
    st.info("Nenhuma aposta registrada ainda.")
