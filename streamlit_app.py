import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt
import io
from datetime import datetime

# ------------------------------
# Configuração inicial
# ------------------------------
st.set_page_config(page_title="Gestor de Apostas", layout="wide")

# ------------------------------
# Banco de dados
# ------------------------------
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

def add_bet(grupo, casa, descricao, valor, retorno, odd, lucro, status):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, odd, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao,
          valor, retorno, odd, lucro, status))
    conn.commit()
    conn.close()

def load_bets():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
    conn.close()
    return df

# ------------------------------
# OCR (Tesseract)
# ------------------------------
def process_image(img) -> dict:
    try:
        text = pytesseract.image_to_string(img, lang="por").lower()
        resultado = {"valor": 0.0, "retorno": 0.0, "status": "Void", "odd": 1.0}

        # Detecta status
        if "green" in text:
            resultado["status"] = "Green"
        elif "red" in text:
            resultado["status"] = "Red"
        elif "void" in text:
            resultado["status"] = "Void"

        # Detecta valores
        for line in text.splitlines():
            if "valor" in line:
                try:
                    resultado["valor"] = float(line.replace("valor", "").replace("r$", "").replace(",", ".").strip())
                except:
                    pass
            if "retorno" in line:
                try:
                    resultado["retorno"] = float(line.replace("retorno", "").replace("r$", "").replace(",", ".").strip())
                except:
                    pass
            if "odd" in line:
                try:
                    resultado["odd"] = float(line.replace("odd", "").replace(",", ".").strip())
                except:
                    pass

        return resultado
    except Exception as e:
        st.error(f"Erro no OCR: {e}")
        return {}

# ------------------------------
# APP
# ------------------------------
init_db()
st.title("📊 Gestor de Apostas com OCR")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📸 Importar aposta (imagem)")
    uploaded = st.file_uploader("Envie a imagem do bilhete", type=["png", "jpg", "jpeg"])
    if uploaded:
        img = Image.open(uploaded)
        st.image(img, caption="Imagem enviada", use_container_width=True)
        dados = process_image(img)

        if dados:
            st.success("OCR concluído!")
            st.write("Pré-preenchido com os valores detectados:")

            with st.form("add_bet_form"):
                grupo = st.text_input("Grupo", "")
                casa = st.text_input("Casa de aposta", "")
                descricao = st.text_area("Descrição", "")
                valor = st.number_input("Valor", value=float(dados.get("valor", 0.0)), step=0.01)
                retorno = st.number_input("Retorno", value=float(dados.get("retorno", 0.0)), step=0.01)
                odd = st.number_input("Odd", value=float(dados.get("odd", 1.0)), step=0.01)
                status = st.selectbox("Status", ["Green", "Red", "Void"], index=["Green", "Red", "Void"].index(dados.get("status", "Void")))
                lucro = retorno - valor if status == "Green" else (-valor if status == "Red" else 0.0)

                salvar = st.form_submit_button("Salvar aposta")

                if salvar:
                    add_bet(grupo, casa, descricao, valor, retorno, odd, lucro, status)
                    st.success("✅ Aposta salva com sucesso!")

with col2:
    st.subheader("📑 Histórico de apostas")
    df = load_bets()
    if not df.empty:
        st.dataframe(df, use_container_width=True)

        st.subheader("📈 Análise de Lucro/Prejuízo")
        resumo = df.groupby("status")["lucro"].sum()
        st.bar_chart(resumo)

        st.subheader("📊 Lucro por Grupo")
        grupo_resumo = df.groupby("grupo")["lucro"].sum()
        st.bar_chart(grupo_resumo)
    else:
        st.info("Nenhuma aposta cadastrada ainda.")

