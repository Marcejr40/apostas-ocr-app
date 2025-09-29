import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
from datetime import datetime
import matplotlib.pyplot as plt

# ==========================
# BANCO DE DADOS
# ==========================
DB_FILE = "apostas.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
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

def add_bet(criado_em, grupo, casa, descricao, odd, valor, retorno, lucro, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, odd, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (criado_em, grupo, casa, descricao, odd, valor, retorno, lucro, status))
    conn.commit()
    conn.close()

def update_bet(aposta_id, grupo, casa, descricao, odd, valor, retorno, lucro, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        UPDATE apostas
        SET grupo=?, casa=?, descricao=?, odd=?, valor=?, retorno=?, lucro=?, status=?
        WHERE id=?
    """, (grupo, casa, descricao, odd, valor, retorno, lucro, status, aposta_id))
    conn.commit()
    conn.close()

def delete_bet(aposta_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM apostas WHERE id=?", (aposta_id,))
    conn.commit()
    conn.close()

def load_bets():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)
    conn.close()
    return df

# ==========================
# INICIALIZAÇÃO
# ==========================
init_db()
st.set_page_config(page_title="Gestão de Apostas", layout="wide")
st.title("📊 Gestão de Apostas com OCR + Banco de Dados")

# ==========================
# OCR
# ==========================
uploaded_file = st.file_uploader("Carregar imagem da aposta (opcional)", type=["png", "jpg", "jpeg"])
ocr_text = ""
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagem carregada", use_container_width=True)
    try:
        ocr_text = pytesseract.image_to_string(image, lang="por")
        st.text_area("📜 Texto OCR detectado:", ocr_text, height=150)
    except Exception as e:
        st.error(f"Erro ao executar OCR: {e}")

# ==========================
# FORMULÁRIO DE APOSTA
# ==========================
with st.form("nova_aposta"):
    st.subheader("➕ Lançar nova aposta")
    grupo = st.text_input("Grupo", value="")
    casa = st.text_input("Casa de Apostas", value="")
    descricao = st.text_area("Descrição", value=ocr_text if ocr_text else "")
    odd = st.number_input("Odd", min_value=1.01, value=1.50, step=0.01)
    valor = st.number_input("Valor Apostado (R$)", min_value=0.0, value=0.0, step=1.0)
    retorno = st.number_input("Retorno Esperado (R$)", min_value=0.0, value=0.0, step=1.0)
    status = st.selectbox("Status", ["Pendente", "Green", "Red", "Void"])

    submitted = st.form_submit_button("Salvar aposta")
    if submitted:
        lucro = 0
        if status == "Green":
            lucro = retorno - valor
        elif status == "Red":
            lucro = -valor
        elif status == "Void":
            lucro = 0

        add_bet(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, odd, valor, retorno, lucro, status)
        st.success("✅ Aposta salva com sucesso!")
        st.rerun()

# ==========================
# LISTAGEM
# ==========================
df = load_bets()

st.subheader("📋 Histórico de Apostas")
if df.empty:
    st.info("Nenhuma aposta registrada ainda.")
else:
    st.dataframe(df, use_container_width=True)

    # Editar ou remover apostas
    st.subheader("✏️ Editar aposta existente")
    aposta_id = st.selectbox("Selecione a aposta pelo ID:", df["id"].tolist())
    aposta = df[df["id"] == aposta_id].iloc[0]

    with st.form("editar_aposta"):
        grupo_edit = st.text_input("Grupo", value=aposta["grupo"])
        casa_edit = st.text_input("Casa", value=aposta["casa"])
        descricao_edit = st.text_area("Descrição", value=aposta["descricao"])
        odd_edit = st.number_input("Odd", min_value=1.01, value=float(aposta["odd"]), step=0.01)
        valor_edit = st.number_input("Valor", min_value=0.0, value=float(aposta["valor"]), step=1.0)
        retorno_edit = st.number_input("Retorno", min_value=0.0, value=float(aposta["retorno"]), step=1.0)
        status_edit = st.selectbox("Status", ["Pendente", "Green", "Red", "Void"], index=["Pendente", "Green", "Red", "Void"].index(aposta["status"]))

        salvar_edit = st.form_submit_button("💾 Salvar alterações")
        deletar = st.form_submit_button("🗑️ Deletar aposta")

        if salvar_edit:
            lucro_edit = 0
            if status_edit == "Green":
                lucro_edit = retorno_edit - valor_edit
            elif status_edit == "Red":
                lucro_edit = -valor_edit
            elif status_edit == "Void":
                lucro_edit = 0
            update_bet(aposta_id, grupo_edit, casa_edit, descricao_edit, odd_edit, valor_edit, retorno_edit, lucro_edit, status_edit)
            st.success("✅ Aposta atualizada!")
            st.rerun()

        if deletar:
            delete_bet(aposta_id)
            st.success("🗑️ Aposta removida!")
            st.rerun()

# ==========================
# RESUMO
# ==========================
st.subheader("📈 Resumo Financeiro")
if not df.empty:
    total_investido = df["valor"].sum()
    total_retorno = df["retorno"].sum()
    total_lucro = df["lucro"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("💸 Investido", f"R$ {total_investido:,.2f}")
    col2.metric("📥 Retorno", f"R$ {total_retorno:,.2f}")
    col3.metric("📊 Lucro/Prejuízo", f"R$ {total_lucro:,.2f}")

    # ==========================
    # GRÁFICOS
    # ==========================
    st.subheader("📊 Gráficos")

    col1, col2 = st.columns(2)

    # Gráfico de lucro por status
    with col1:
        lucro_status = df.groupby("status")["lucro"].sum()
        fig, ax = plt.subplots()
        lucro_status.plot(kind="bar", ax=ax, color=["gray", "green", "red", "orange"])
        ax.set_title("Lucro por Status")
        ax.set_ylabel("Lucro (R$)")
        st.pyplot(fig)

    # Gráfico de lucro por grupo
    with col2:
        lucro_grupo = df.groupby("grupo")["lucro"].sum()
        fig, ax = plt.subplots()
        lucro_grupo.plot(kind="bar", ax=ax, color="blue")
        ax.set_title("Lucro por Grupo")
        ax.set_ylabel("Lucro (R$)")
        st.pyplot(fig)
