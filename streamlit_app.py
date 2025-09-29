import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt
from datetime import datetime

# ======================
# BANCO DE DADOS
# ======================
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

def add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status):
    lucro = retorno - valor
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, odd, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao,
          float(valor), float(retorno), float(odd), lucro, status))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)
    conn.close()
    return df

def update_bet(bet_id, grupo, casa, descricao, valor, retorno, odd, status):
    lucro = retorno - valor
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        UPDATE apostas
        SET grupo=?, casa=?, descricao=?, valor=?, retorno=?, odd=?, lucro=?, status=?
        WHERE id=?
    """, (grupo, casa, descricao, valor, retorno, odd, lucro, status, bet_id))
    conn.commit()
    conn.close()

def delete_bet(bet_id):
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("DELETE FROM apostas WHERE id=?", (bet_id,))
    conn.commit()
    conn.close()

# ======================
# INICIALIZAÇÃO
# ======================
init_db()
st.set_page_config(page_title="Controle de Apostas", layout="wide")

st.title("📊 Controle de Apostas com OCR + Banco de Dados")

# ======================
# UPLOAD DE IMAGEM (OCR)
# ======================
st.header("📷 Upload de bilhete (OCR)")
uploaded_file = st.file_uploader("Envie o print da aposta", type=["png", "jpg", "jpeg"])

grupo = st.text_input("Grupo")
casa = st.text_input("Casa de aposta")
descricao = st.text_area("Descrição")
valor = st.number_input("Valor apostado", min_value=0.0, step=1.0)
retorno = st.number_input("Retorno", min_value=0.0, step=1.0)
odd = st.number_input("Odd", min_value=1.01, value=1.01, step=0.01)
status = st.selectbox("Status", ["green", "red", "void"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Print enviado", use_container_width=True)

    try:
        texto = pytesseract.image_to_string(image, lang="por")
        st.text_area("Texto reconhecido (OCR):", texto, height=150)
    except Exception as e:
        st.error(f"Erro ao executar OCR: {e}")

if st.button("Salvar aposta"):
    add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status)
    st.success("✅ Aposta salva com sucesso!")
    st.rerun()

# ======================
# HISTÓRICO DE APOSTAS
# ======================
st.header("📑 Histórico de Apostas")

df = load_bets_df()

if not df.empty:
    for _, aposta in df.iterrows():
        with st.expander(f"📝 Aposta #{aposta['id']} - {aposta['status'].upper()}"):
            st.write(f"**Criado em:** {aposta['criado_em']}")
            with st.form(key=f"edit_form_{aposta['id']}"):
                grupo_edit = st.text_input("Grupo", aposta["grupo"])
                casa_edit = st.text_input("Casa", aposta["casa"])
                descricao_edit = st.text_area("Descrição", aposta["descricao"])
                valor_edit = st.number_input("Valor", min_value=0.0, value=float(aposta["valor"]), step=1.0)
                retorno_edit = st.number_input("Retorno", min_value=0.0, value=float(aposta["retorno"]), step=1.0)
                odd_edit = st.number_input("Odd", min_value=1.01, value=float(aposta.get("odd", 1.01)), step=0.01)
                status_edit = st.selectbox("Status", ["green", "red", "void"],
                                           index=["green", "red", "void"].index(aposta["status"]))
                salvar = st.form_submit_button("Salvar alterações")
                if salvar:
                    update_bet(aposta["id"], grupo_edit, casa_edit, descricao_edit,
                               valor_edit, retorno_edit, odd_edit, status_edit)
                    st.success("Aposta atualizada com sucesso!")
                    st.rerun()

            if st.button("🗑️ Excluir aposta", key=f"del_{aposta['id']}"):
                delete_bet(aposta["id"])
                st.warning("Aposta excluída.")
                st.rerun()
else:
    st.info("Nenhuma aposta cadastrada ainda.")

# ======================
# RESUMO GERAL
# ======================
st.header("📈 Resumo Geral")

if not df.empty:
    total_apostas = len(df)
    total_green = len(df[df["status"] == "green"])
    total_red = len(df[df["status"] == "red"])
    total_void = len(df[df["status"] == "void"])
    lucro_total = df["lucro"].sum()

    st.metric("Total de apostas", total_apostas)
    st.metric("Greens", total_green)
    st.metric("Reds", total_red)
    st.metric("Voids", total_void)
    st.metric("Lucro total (R$)", round(lucro_total, 2))

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Distribuição por Status")
        fig, ax = plt.subplots()
        df["status"].value_counts().plot.pie(autopct="%1.1f%%", ax=ax)
        ax.set_ylabel("")
        st.pyplot(fig)

    with col2:
        st.subheader("Lucro acumulado")
        fig, ax = plt.subplots()
        df.groupby("criado_em")["lucro"].sum().cumsum().plot(ax=ax)
        plt.xticks(rotation=45)
        st.pyplot(fig)

    with col3:
        st.subheader("Lucro por Grupo")
        fig, ax = plt.subplots()
        df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax)
        plt.xticks(rotation=45)
        st.pyplot(fig)
