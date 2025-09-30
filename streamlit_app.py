import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import pytesseract
import re
import os

# =========================
# Banco de Dados
# =========================
def init_db():
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo TEXT,
            casa TEXT,
            descricao TEXT,
            valor REAL,
            retorno REAL,
            odd REAL,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def inserir_aposta(grupo, casa, descricao, valor, retorno, odd, status):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (grupo, casa, descricao, valor, retorno, odd, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (grupo, casa, descricao, valor, retorno, odd, status))
    conn.commit()
    conn.close()

def listar_apostas():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql_query("SELECT * FROM apostas", conn)
    conn.close()
    return df

def atualizar_aposta(id_, grupo, casa, descricao, valor, retorno, odd, status):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        UPDATE apostas
        SET grupo=?, casa=?, descricao=?, valor=?, retorno=?, odd=?, status=?
        WHERE id=?
    """, (grupo, casa, descricao, valor, retorno, odd, status, id_))
    conn.commit()
    conn.close()

def deletar_aposta(id_):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("DELETE FROM apostas WHERE id=?", (id_,))
    conn.commit()
    conn.close()

# =========================
# OCR
# =========================
def process_image(uploaded_file):
    if uploaded_file is None:
        return {}

    image = Image.open(uploaded_file)
    text = pytesseract.image_to_string(image, lang="por").lower()

    # Mostra o texto cru do OCR para debug
    st.write("🔍 Texto OCR detectado:")
    st.code(text)

    data = {
        "grupo": "",
        "casa": "",
        "descricao": text[:80],  # primeiros 80 caracteres
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

    # Extrai números (valor, retorno, odd)
    numeros = re.findall(r"\d+[.,]?\d*", text)
    numeros = [n.replace(",", ".") for n in numeros]

    if len(numeros) >= 1:
        data["valor"] = float(numeros[0])
    if len(numeros) >= 2:
        data["retorno"] = float(numeros[1])
    if data["valor"] > 0 and data["retorno"] > 0:
        data["odd"] = round(data["retorno"] / data["valor"], 2)

    return data

# =========================
# Dashboard
# =========================
def mostrar_dashboard(df):
    st.subheader("📊 Resumo Geral")

    if df.empty:
        st.info("Nenhuma aposta cadastrada ainda.")
        return

    total_valor = df["valor"].sum()
    total_retorno = df["retorno"].sum()
    lucro = total_retorno - total_valor

    col1, col2, col3 = st.columns(3)
    col1.metric("Investido", f"R$ {total_valor:.2f}")
    col2.metric("Retorno", f"R$ {total_retorno:.2f}")
    col3.metric("Lucro", f"R$ {lucro:.2f}")

    # Gráfico por status
    st.write("### Distribuição por Status")
    status_counts = df["status"].value_counts()
    fig, ax = plt.subplots()
    status_counts.plot(kind="bar", ax=ax, color=["green", "red", "gray"])
    st.pyplot(fig)

    # Gráfico por grupo
    if "grupo" in df.columns and not df["grupo"].isnull().all():
        st.write("### Lucro por Grupo")
        lucro_por_grupo = df.groupby("grupo")[["valor", "retorno"]].sum()
        lucro_por_grupo["lucro"] = lucro_por_grupo["retorno"] - lucro_por_grupo["valor"]

        fig, ax = plt.subplots()
        lucro_por_grupo["lucro"].plot(kind="bar", ax=ax)
        st.pyplot(fig)

# =========================
# App Principal
# =========================
def main():
    st.set_page_config(page_title="Gerenciador de Apostas", layout="wide")
    st.title("🏆 Gerenciador de Apostas com OCR")

    init_db()

    menu = ["Cadastrar", "Listar/Editar", "Dashboard"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Cadastrar":
        st.subheader("📥 Cadastrar Nova Aposta")

        uploaded_file = st.file_uploader("Upload da imagem (com dados da aposta)", type=["png", "jpg", "jpeg"])
        ocr_data = process_image(uploaded_file) if uploaded_file else {}

        with st.form("form_aposta"):
            grupo = st.text_input("Grupo", value=ocr_data.get("grupo", ""))
            casa = st.text_input("Casa", value=ocr_data.get("casa", ""))
            descricao = st.text_area("Descrição", value=ocr_data.get("descricao", ""))
            valor = st.number_input("Valor", min_value=0.0, value=float(ocr_data.get("valor", 0.0)))
            retorno = st.number_input("Retorno", min_value=0.0, value=float(ocr_data.get("retorno", 0.0)))
            odd = st.number_input("Odd", min_value=1.01, value=float(ocr_data.get("odd", 1.01)), step=0.01)
            status = st.selectbox("Status", ["Green", "Red", "Void"], index=["Green", "Red", "Void"].index(ocr_data.get("status", "Void")))
            submitted = st.form_submit_button("Salvar Aposta")

            if submitted:
                inserir_aposta(grupo, casa, descricao, valor, retorno, odd, status)
                st.success("Aposta cadastrada com sucesso!")

    elif choice == "Listar/Editar":
        st.subheader("📋 Lista de Apostas")
        df = listar_apostas()

        if df.empty:
            st.info("Nenhuma aposta cadastrada.")
        else:
            st.dataframe(df)

            aposta_id = st.number_input("ID da aposta para editar/deletar", min_value=1, step=1)
            aposta = df[df["id"] == aposta_id]

            if not aposta.empty:
                aposta = aposta.iloc[0]

                with st.form("form_editar"):
                    grupo = st.text_input("Grupo", value=aposta["grupo"])
                    casa = st.text_input("Casa", value=aposta["casa"])
                    descricao = st.text_area("Descrição", value=aposta["descricao"])
                    valor = st.number_input("Valor", min_value=0.0, value=float(aposta["valor"]))
                    retorno = st.number_input("Retorno", min_value=0.0, value=float(aposta["retorno"]))
                    odd = st.number_input("Odd", min_value=1.01, value=float(aposta["odd"]), step=0.01)
                    status = st.selectbox("Status", ["Green", "Red", "Void"], index=["Green", "Red", "Void"].index(aposta["status"]))
                    atualizar_btn = st.form_submit_button("Atualizar")
                    deletar_btn = st.form_submit_button("Deletar")

                    if atualizar_btn:
                        atualizar_aposta(aposta_id, grupo, casa, descricao, valor, retorno, odd, status)
                        st.success("Aposta atualizada com sucesso!")
                    if deletar_btn:
                        deletar_aposta(aposta_id)
                        st.warning("Aposta deletada.")

    elif choice == "Dashboard":
        df = listar_apostas()
        mostrar_dashboard(df)

if __name__ == "__main__":
    main()

