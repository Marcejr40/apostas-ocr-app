import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt

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
            valor REAL,
            retorno REAL,
            lucro REAL,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_bet_to_db(grupo, casa, descricao, valor, retorno, lucro, status):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, valor, retorno, lucro, status))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)
    conn.close()
    return df

# ==============================
# Funções de OCR
# ==============================
def process_image(img, lang="por"):
    try:
        text = pytesseract.image_to_string(img, lang=lang)
        return text
    except Exception as e:
        return f"Erro ao executar OCR: {e}"

# ==============================
# Função principal
# ==============================
def main():
    st.set_page_config(page_title="Gerenciador de Apostas", layout="wide")
    st.title("📊 Gerenciador de Apostas com OCR")

    init_db()

    menu = ["Cadastrar Aposta", "Visualizar Apostas"]
    choice = st.sidebar.radio("Menu", menu)

    if choice == "Cadastrar Aposta":
        st.subheader("➕ Nova Aposta")

        uploaded_file = st.file_uploader("Carregar print da aposta", type=["png", "jpg", "jpeg"])
        descricao = ""
        if uploaded_file is not None:
            img = Image.open(uploaded_file)
            st.image(img, caption="Imagem carregada", use_container_width=True)

            ocr_result = process_image(img)
            st.text_area("Texto reconhecido pelo OCR", ocr_result, height=150)
            descricao = ocr_result

        with st.form("nova_aposta"):
            grupo = st.text_input("Grupo")
            casa = st.text_input("Casa")
            valor = st.number_input("Valor apostado (R$)", min_value=0.0, step=0.01)
            retorno = st.number_input("Retorno esperado (R$)", min_value=0.0, step=0.01)
            status = st.selectbox("Status", ["Green", "Red", "Void"])
            submitted = st.form_submit_button("Salvar")

            if submitted:
                lucro = 0
                if status == "Green":
                    lucro = retorno - valor
                elif status == "Red":
                    lucro = -valor
                else:
                    lucro = 0

                add_bet_to_db(grupo, casa, descricao, valor, retorno, lucro, status)
                st.success("Aposta salva com sucesso!")

    elif choice == "Visualizar Apostas":
        st.subheader("📋 Histórico de Apostas")

        df = load_bets_df()
        if df.empty:
            st.warning("Nenhuma aposta cadastrada ainda.")
        else:
            st.dataframe(df, use_container_width=True)

            st.subheader("📈 Resumo Financeiro")
            total_investido = df["valor"].sum()
            total_retorno = df["retorno"].sum()
            total_lucro = df["lucro"].sum()

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Investido", f"R$ {total_investido:,.2f}")
            col2.metric("Total Retorno", f"R$ {total_retorno:,.2f}")
            col3.metric("Lucro/Prejuízo", f"R$ {total_lucro:,.2f}")

            st.subheader("📊 Gráficos")
            col4, col5 = st.columns(2)

            with col4:
                fig1, ax1 = plt.subplots()
                df["status"].value_counts().plot(kind="bar", ax=ax1, color=["green", "red", "gray"])
                ax1.set_title("Quantidade por Status")
                st.pyplot(fig1)

            with col5:
                fig2, ax2 = plt.subplots()
                df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax2, color="blue")
                ax2.set_title("Lucro por Grupo")
                st.pyplot(fig2)

if __name__ == "__main__":
    main()
