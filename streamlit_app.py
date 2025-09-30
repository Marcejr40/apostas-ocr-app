import streamlit as st
import sqlite3
import pandas as pd
import pytesseract
from PIL import Image
import io

# Configuração inicial
st.set_page_config(page_title="Gestor de Apostas", layout="wide")

# Banco de dados
def init_db():
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS apostas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT,
                    esporte TEXT,
                    campeonato TEXT,
                    confronto TEXT,
                    mercado TEXT,
                    odd REAL,
                    valor REAL,
                    retorno TEXT,
                    imagem BLOB
                )''')
    conn.commit()
    conn.close()

init_db()

def insert_aposta(data, esporte, campeonato, confronto, mercado, odd, valor, retorno, imagem):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("INSERT INTO apostas (data, esporte, campeonato, confronto, mercado, odd, valor, retorno, imagem) VALUES (?,?,?,?,?,?,?,?,?)",
              (data, esporte, campeonato, confronto, mercado, odd, valor, retorno, imagem))
    conn.commit()
    conn.close()

def update_aposta(aposta_id, data, esporte, campeonato, confronto, mercado, odd, valor, retorno):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute('''UPDATE apostas 
                 SET data=?, esporte=?, campeonato=?, confronto=?, mercado=?, odd=?, valor=?, retorno=? 
                 WHERE id=?''',
              (data, esporte, campeonato, confronto, mercado, odd, valor, retorno, aposta_id))
    conn.commit()
    conn.close()

def delete_aposta(aposta_id):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("DELETE FROM apostas WHERE id=?", (aposta_id,))
    conn.commit()
    conn.close()

def get_apostas():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql_query("SELECT * FROM apostas", conn)
    conn.close()
    return df

# Função OCR
def extrair_texto(img_bytes):
    image = Image.open(io.BytesIO(img_bytes))
    texto = pytesseract.image_to_string(image, lang="por")
    return texto

# Layout principal
st.title("📊 Gestor de Apostas com OCR")

aba = st.sidebar.radio("Navegação", ["Adicionar Aposta", "Gerenciar Apostas", "Resumo Geral"])

# ---------------- Adicionar ----------------
if aba == "Adicionar Aposta":
    st.header("➕ Adicionar Nova Aposta")

    with st.form("form_aposta", clear_on_submit=True):
        data = st.date_input("Data da aposta")
        esporte = st.text_input("Esporte")
        campeonato = st.text_input("Campeonato")
        confronto = st.text_input("Confronto")
        mercado = st.text_input("Mercado")
        odd = st.number_input("Odd", min_value=1.01, step=0.01)
        valor = st.number_input("Valor Apostado", min_value=0.0, step=1.0)
        retorno = st.selectbox("Resultado", ["Green", "Red", "Void"])
        imagem = st.file_uploader("Comprovante (opcional)", type=["png", "jpg", "jpeg"])

        submitted = st.form_submit_button("Salvar")

        if submitted:
            imagem_bytes = imagem.read() if imagem else None
            insert_aposta(str(data), esporte, campeonato, confronto, mercado, odd, valor, retorno, imagem_bytes)
            st.success("✅ Aposta adicionada com sucesso!")
            st.rerun()

# ---------------- Gerenciar ----------------
elif aba == "Gerenciar Apostas":
    st.header("🛠️ Editar ou Excluir Apostas")

    df = get_apostas()
    if df.empty:
        st.info("Nenhuma aposta cadastrada ainda.")
    else:
        aposta_id = st.selectbox("Selecione a aposta para editar/excluir:", df["id"])

        aposta = df[df["id"] == aposta_id].iloc[0]

        with st.form("form_editar"):
            data_edit = st.date_input("Data", value=pd.to_datetime(aposta["data"]))
            esporte_edit = st.text_input("Esporte", aposta["esporte"])
            campeonato_edit = st.text_input("Campeonato", aposta["campeonato"])
            confronto_edit = st.text_input("Confronto", aposta["confronto"])
            mercado_edit = st.text_input("Mercado", aposta["mercado"])
            odd_edit = st.number_input("Odd", min_value=1.01, value=float(aposta["odd"]), step=0.01)
            valor_edit = st.number_input("Valor", min_value=0.0, value=float(aposta["valor"]), step=1.0)
            retorno_edit = st.selectbox("Resultado", ["Green", "Red", "Void"], index=["Green","Red","Void"].index(aposta["retorno"]))

            col1, col2 = st.columns(2)
            with col1:
                salvar = st.form_submit_button("💾 Salvar Alterações")
            with col2:
                excluir = st.form_submit_button("🗑️ Excluir Aposta")

        if salvar:
            update_aposta(aposta_id, str(data_edit), esporte_edit, campeonato_edit, confronto_edit, mercado_edit, odd_edit, valor_edit, retorno_edit)
            st.success("✅ Alterações salvas!")
            st.rerun()

        if excluir:
            delete_aposta(aposta_id)
            st.success("🗑️ Aposta excluída!")
            st.rerun()

# ---------------- Resumo ----------------
elif aba == "Resumo Geral":
    st.header("📈 Resumo Geral")

    df = get_apostas()
    if df.empty:
        st.info("Nenhuma aposta cadastrada.")
    else:
        st.dataframe(df)

        ganhos = df[df["retorno"] == "Green"]["valor"].sum()
        perdas = df[df["retorno"] == "Red"]["valor"].sum()
        voids = df[df["retorno"] == "Void"]["valor"].sum()
        total = ganhos - perdas

        st.metric("Lucro Total", f"R$ {total:.2f}")
        st.metric("Green (Vitórias)", f"R$ {ganhos:.2f}")
        st.metric("Red (Perdas)", f"R$ {perdas:.2f}")
        st.metric("Void", f"R$ {voids:.2f}")
