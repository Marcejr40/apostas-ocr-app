import streamlit as st
import sqlite3
import pandas as pd
import pytesseract
from PIL import Image
import io
import re
from datetime import datetime
import matplotlib.pyplot as plt

# =========================
# CONFIGURAÇÕES INICIAIS
# =========================
st.set_page_config(page_title="Controle de Apostas com OCR", layout="wide")

# =========================
# BANCO DE DADOS
# =========================
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
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    lucro = retorno - valor
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, odd, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        grupo, casa, descricao, float(valor), float(retorno), float(odd), lucro, status
    ))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)
    conn.close()
    return df

# =========================
# OCR E EXTRAÇÃO DE INFORMAÇÕES
# =========================
def extrair_info_ocr(texto):
    # Padrões regex
    padrao_valor = re.search(r"Aposta\s*R\$\s*([\d.,]+)", texto)
    padrao_retorno = re.search(r"Retorno (?:Total )?R\$\s*([\d.,]+)", texto)
    padrao_odd = re.search(r"\s(\d+\.\d{2})", texto)

    # Extrair valores
    valor = float(padrao_valor.group(1).replace(".", "").replace(",", ".")) if padrao_valor else 0.0
    retorno = float(padrao_retorno.group(1).replace(".", "").replace(",", ".")) if padrao_retorno else 0.0
    odd = float(padrao_odd.group(1)) if padrao_odd else 1.0

    # Determinar status
    if "Retorno Obtido" in texto:
        status = "Green"
    elif "Anulado" in texto or "Anulada" in texto:
        status = "Void"
    elif "Perdida" in texto or "Cash Out" in texto:
        status = "Red"
    else:
        status = "Indefinido"

    return valor, retorno, odd, status

# =========================
# INTERFACE STREAMLIT
# =========================
st.title("📊 Controle de Apostas com OCR")

# Upload da imagem
st.subheader("📸 Importar aposta (imagem)")
uploaded_file = st.file_uploader("Envie a imagem do bilhete", type=["png", "jpg", "jpeg"])

texto_ocr = ""
valor_detectado, retorno_detectado, odd_detectada, status_detectado = 0.0, 0.0, 1.0, "Indefinido"

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagem carregada", use_column_width=True)

    # OCR
    texto_ocr = pytesseract.image_to_string(image, lang="por")
    st.subheader("Resultado do OCR")
    st.code(texto_ocr)

    # Extração de info automática
    valor_detectado, retorno_detectado, odd_detectada, status_detectado = extrair_info_ocr(texto_ocr)

# =========================
# FORMULÁRIO DE EDIÇÃO
# =========================
st.subheader("✍️ Cadastro/edição da aposta")

with st.form("aposta_form"):
    grupo = st.text_input("Grupo", "Grupo 1")
    casa = st.text_input("Casa de aposta", "Bet365")
    descricao = st.text_area("Descrição", texto_ocr)
    valor = st.number_input("Valor", min_value=0.0, value=valor_detectado, step=1.0)
    retorno = st.number_input("Retorno", min_value=0.0, value=retorno_detectado, step=1.0)
    odd = st.number_input("Odd", min_value=1.0, value=odd_detectada, step=0.01)
    status = st.selectbox("Status", ["Green", "Red", "Void", "Indefinido"],
                          index=["Green", "Red", "Void", "Indefinido"].index(status_detectado))
    submit = st.form_submit_button("Salvar aposta")

if submit:
    add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status)
    st.success("✅ Aposta salva com sucesso!")

# =========================
# HISTÓRICO DE APOSTAS
# =========================
st.subheader("📑 Histórico de apostas")
df = load_bets_df()
st.dataframe(df)

# =========================
# GRÁFICOS
# =========================
st.subheader("📊 Análise de Lucro/Prejuízo")

if not df.empty:
    fig, ax = plt.subplots(figsize=(6,4))
    df.groupby("status")["lucro"].sum().plot(kind="bar", ax=ax, color="royalblue")
    ax.set_ylabel("Lucro total (R$)")
    ax.set_xlabel("Status")
    ax.set_title("Lucro por Status")
    st.pyplot(fig)

    fig2, ax2 = plt.subplots(figsize=(6,4))
    df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax2, color="green")
    ax2.set_ylabel("Lucro total (R$)")
    ax2.set_xlabel("Grupo")
    ax2.set_title("Lucro por Grupo")
    st.pyplot(fig2)
else:
    st.info("Nenhuma aposta registrada ainda.")
    
# =========================
# INICIAR BANCO DE DADOS
# =========================
init_db()

