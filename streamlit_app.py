import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# Função para conectar no banco
def get_connection():
    return sqlite3.connect("apostas.db")

# Adicionar aposta
def add_bet(grupo, casa, descricao, valor, retorno, status, odd):
    conn = get_connection()
    c = conn.cursor()
    lucro = retorno - valor
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, lucro, status, odd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, valor, retorno, lucro, status, odd))
    conn.commit()
    conn.close()

# Carregar apostas
def load_bets():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
    conn.close()
    return df

# Interface Streamlit
st.title("📊 App de Apostas - Versão Base")

with st.form("nova_aposta"):
    grupo = st.text_input("Grupo")
    casa = st.text_input("Casa de apostas")
    descricao = st.text_area("Descrição")
    valor = st.number_input("Valor", min_value=0.0, step=1.0)
    retorno = st.number_input("Retorno", min_value=0.0, step=1.0)
    odd = st.number_input("Odd", min_value=1.01, step=0.01, value=2.0)
    status = st.selectbox("Status", ["Green", "Red", "Void", "Indefinido"])
    submit = st.form_submit_button("Salvar")

    if submit:
        add_bet(grupo, casa, descricao, valor, retorno, status, odd)
        st.success("Aposta salva com sucesso!")

st.subheader("📋 Histórico de Apostas")
df = load_bets()
st.dataframe(df)
