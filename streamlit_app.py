import streamlit as st
import sqlite3
import pandas as pd
import pytesseract
from PIL import Image
import io
import matplotlib.pyplot as plt

# -----------------------------
# Banco de Dados
# -----------------------------
def init_db():
    conn = sqlite3.connect("apostas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            esporte TEXT,
            campeonato TEXT,
            partida TEXT,
            mercado TEXT,
            odd REAL,
            valor REAL,
            retorno REAL,
            data TEXT,
            status TEXT,
            imagem BLOB
        )
    """)
    conn.commit()
    conn.close()

def insert_aposta(esporte, campeonato, partida, mercado, odd, valor, retorno, data, status, imagem):
    conn = sqlite3.connect("apostas.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO apostas (esporte, campeonato, partida, mercado, odd, valor, retorno, data, status, imagem)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (esporte, campeonato, partida, mercado, odd, valor, retorno, data, status, imagem))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)
    conn.close()
    return df

def update_aposta(aposta_id, esporte, campeonato, partida, mercado, odd, valor, retorno, data, status):
    conn = sqlite3.connect("apostas.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE apostas
        SET esporte=?, campeonato=?, partida=?, mercado=?, odd=?, valor=?, retorno=?, data=?, status=?
        WHERE id=?
    """, (esporte, campeonato, partida, mercado, odd, valor, retorno, data, status, aposta_id))
    conn.commit()
    conn.close()

# -----------------------------
# Funções auxiliares
# -----------------------------
def ocr_from_image(uploaded_file):
    image = Image.open(uploaded_file)
    text = pytesseract.image_to_string(image, lang="por")
    return text, image

# -----------------------------
# Interface Streamlit
# -----------------------------
st.set_page_config(page_title="Gestão de Apostas", layout="wide")
st.title("📊 Gestão de Apostas com OCR")

init_db()

menu = st.sidebar.radio("Menu", ["Nova Aposta", "Histórico", "Resumo Geral"])

# -----------------------------
# Nova Aposta
# -----------------------------
if menu == "Nova Aposta":
    st.subheader("Adicionar nova aposta")

    with st.form("nova_aposta_form"):
        esporte = st.text_input("Esporte")
        campeonato = st.text_input("Campeonato")
        partida = st.text_input("Partida")
        mercado = st.text_input("Mercado")
        odd = st.number_input("Odd", min_value=1.01, step=0.01)
        valor = st.number_input("Valor Apostado (R$)", min_value=0.0, step=1.0)
        retorno = st.number_input("Retorno Esperado (R$)", min_value=0.0, step=1.0)
        data = st.date_input("Data")
        status = st.selectbox("Status", ["Aberta", "Green", "Red"])
        uploaded_file = st.file_uploader("Comprovante (imagem)", type=["png", "jpg", "jpeg"])

        submitted = st.form_submit_button("Salvar")

        if submitted:
            img_bytes = uploaded_file.read() if uploaded_file else None
            insert_aposta(esporte, campeonato, partida, mercado, odd, valor, retorno, str(data), status, img_bytes)
            st.success("✅ Aposta salva com sucesso!")

    st.markdown("---")
    st.subheader("OCR do Comprovante")
    img_file = st.file_uploader("Carregar imagem para OCR", type=["png", "jpg", "jpeg"], key="ocr_upload")
    if img_file:
        text, img = ocr_from_image(img_file)
        st.image(img, caption="Imagem carregada", use_container_width=True)
        st.text_area("Texto extraído", text, height=200)

# -----------------------------
# Histórico de Apostas
# -----------------------------
elif menu == "Histórico":
    st.subheader("Histórico de apostas")

    df = load_bets_df()
    if not df.empty:
        st.dataframe(df, use_container_width=True)

        aposta_id = st.number_input("ID da aposta para editar", min_value=1, step=1)
        aposta = df[df["id"] == aposta_id]

        if not aposta.empty:
            aposta = aposta.iloc[0]

            with st.form("editar_aposta"):
                esporte = st.text_input("Esporte", aposta["esporte"])
                campeonato = st.text_input("Campeonato", aposta["campeonato"])
                partida = st.text_input("Partida", aposta["partida"])
                mercado = st.text_input("Mercado", aposta["mercado"])
                odd = st.number_input("Odd", min_value=1.01, value=float(aposta["odd"]), step=0.01)
                valor = st.number_input("Valor Apostado", min_value=0.0, value=float(aposta["valor"]), step=1.0)
                retorno = st.number_input("Retorno Esperado", min_value=0.0, value=float(aposta["retorno"]), step=1.0)
                data = st.text_input("Data", aposta["data"])
                status = st.selectbox("Status", ["Aberta", "Green", "Red"], index=["Aberta","Green","Red"].index(aposta["status"]))
                salvar = st.form_submit_button("Salvar Alterações")

                if salvar:
                    update_aposta(aposta["id"], esporte, campeonato, partida, mercado, odd, valor, retorno, data, status)
                    st.success("✅ Aposta atualizada!")

    else:
        st.info("Nenhuma aposta cadastrada ainda.")

# -----------------------------
# Resumo Geral
# -----------------------------
elif menu == "Resumo Geral":
    st.subheader("📈 Resumo das apostas")

    df = load_bets_df()
    if not df.empty:
        total_apostas = len(df)
        total_investido = df["valor"].sum()
        total_retorno = df["retorno"].sum()
        lucro = total_retorno - total_investido

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Apostas", total_apostas)
        col2.metric("Investido (R$)", f"{total_investido:,.2f}")
        col3.metric("Retorno (R$)", f"{total_retorno:,.2f}")
        col4.metric("Lucro (R$)", f"{lucro:,.2f}")

        st.markdown("---")
        st.subheader("Gráfico por Status")

        status_counts = df["status"].value_counts()
        fig, ax = plt.subplots()
        ax.pie(status_counts, labels=status_counts.index, autopct="%1.1f%%")
        ax.set_title("Distribuição por Status")
        st.pyplot(fig)

        st.markdown("---")
        st.subheader("Gráfico por Esporte")

        esporte_group = df.groupby("esporte")["valor"].sum()
        fig2, ax2 = plt.subplots()
        esporte_group.plot(kind="bar", ax=ax2)
        ax2.set_ylabel("Valor Apostado (R$)")
        st.pyplot(fig2)

    else:
        st.info("Nenhum dado disponível ainda.")
