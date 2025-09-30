import streamlit as st
import sqlite3
import pandas as pd
import pytesseract
from PIL import Image
import re
from datetime import datetime
import matplotlib.pyplot as plt

st.set_page_config(page_title="Controle de Apostas com OCR", layout="wide")

# ------------------------
# Banco de dados (SQLite)
# ------------------------
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
    lucro = retorno - valor if status == "Green" else (-valor if status == "Red" else 0.0)
    conn = sqlite3.connect("apostas.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, odd, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        grupo, casa, descricao, float(valor), float(retorno), float(odd), float(lucro), status
    ))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect("apostas.db")
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
    conn.close()
    return df

# ------------------------
# Funções auxiliares
# ------------------------
def parse_brazil_currency(s: str):
    if s is None:
        return None
    s = s.strip().replace("R$", "").replace("r$", "").strip()
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    s = re.sub(r"[^\d\.\-]", "", s)
    try:
        return float(s)
    except:
        return None

def find_currency_tokens(text: str):
    tokens = []
    for m in re.findall(r"(R\$\s*[\d\.,]+)", text, flags=re.I):
        val = parse_brazil_currency(m)
        if val is not None:
            tokens.append((m, val))
    for m in re.findall(r"(?<!R\$)(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+[.,]\d+)", text):
        val = parse_brazil_currency(m)
        if val is not None:
            tokens.append((m, val))
    return tokens

def extrair_info_ocr(texto: str):
    t = (texto or "").strip()
    t_lower = t.lower()

    # Debug do OCR
    st.write("🔍 Texto OCR bruto:")
    st.code(t)

    status = "Indefinido"
    if any(x in t_lower for x in ["retorno obtido", "ganhou", "ganho"]):
        status = "Green"
    if "anulado" in t_lower or "anulada" in t_lower:
        status = "Void"
    if any(x in t_lower for x in ["perdeu", "perdida", "perdido", "red"]):
        status = "Red"

    valor = None
    retorno = None
    odd = None

    m_val = re.search(r"(?:aposta|valor)\s*[:\-]?\s*R?\$?\s*([\d\.,]+)", t, flags=re.I)
    m_ret = re.search(r"(?:retorno(?: total| obtido)?)\s*[:\-]?\s*R?\$?\s*([\d\.,]+)", t, flags=re.I)
    m_ret_after = re.search(r"R\$\s*([\d\.,]+)\s*(?:retorno|retorno total|retorno obtido)", t, flags=re.I)

    if m_val:
        valor = parse_brazil_currency(m_val.group(1))
    if m_ret:
        retorno = parse_brazil_currency(m_ret.group(1))
    if m_ret_after and retorno is None:
        retorno = parse_brazil_currency(m_ret_after.group(1))

    odd_candidates = re.findall(r"\b(\d+\.\d{2})\b", t)
    for oc in odd_candidates:
        try:
            v = float(oc)
            if 1.01 <= v <= 200:
                odd = v
                break
        except:
            pass

    tokens = find_currency_tokens(t)
    if tokens:
        st.write("🔎 Valores detectados:", tokens)

    if retorno is None:
        vals = [v for (_, v) in tokens]
        if len(vals) >= 2:
            valor = valor or min(vals)
            retorno = retorno or max(vals)
        elif len(vals) == 1:
            only = vals[0]
            if status == "Void":
                valor = valor or only
                retorno = only
            elif status == "Red":
                valor = valor or only
                retorno = 0.0
            else:
                valor = valor or only
                retorno = 0.0

    if valor is None:
        valor = tokens[0][1] if tokens else 0.0
    if retorno is None:
        retorno = 0.0
    if odd is None:
        try:
            if valor > 0 and retorno > 0:
                odd = round(retorno / valor, 2)
            else:
                odd = 1.0
        except:
            odd = 1.0

    st.write(f"✅ Extraído: Valor=R${valor:.2f}, Retorno=R${retorno:.2f}, Odd={odd:.2f}, Status={status}")
    return valor, retorno, odd, status

# ------------------------
# Interface Streamlit
# ------------------------
init_db()
st.title("📊 Controle de Apostas com OCR")

uploaded_file = st.file_uploader("Importar aposta (imagem)", type=["png", "jpg", "jpeg"])
texto_ocr = ""
valor_detectado, retorno_detectado, odd_detectado, status_detectado = 0.0, 0.0, 1.0, "Indefinido"

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Imagem carregada", use_container_width=True)
    try:
        texto_ocr = pytesseract.image_to_string(img, lang="por")
    except:
        texto_ocr = pytesseract.image_to_string(img)
    st.subheader("Texto detectado (OCR)")
    st.code(texto_ocr)
    valor_detectado, retorno_detectado, odd_detectado, status_detectado = extrair_info_ocr(texto_ocr)

st.subheader("Cadastrar / Conferir aposta")
with st.form("form_aposta"):
    grupo = st.text_input("Grupo", value="Grupo 1")
    casa = st.text_input("Casa de aposta", value="Bet365")
    descricao = st.text_area("Descrição", value=texto_ocr)
    valor = st.number_input("Valor", min_value=0.0, value=float(valor_detectado), step=0.01, format="%.2f")
    retorno = st.number_input("Retorno", min_value=0.0, value=float(retorno_detectado), step=0.01, format="%.2f")
    odd = st.number_input("Odd", min_value=1.0, value=float(odd_detectado), step=0.01, format="%.2f")
    status = st.selectbox("Status", ["Green", "Red", "Void", "Indefinido"], 
                          index=["Green", "Red", "Void", "Indefinido"].index(status_detectado if status_detectado in ["Green","Red","Void"] else "Indefinido"))
    submit = st.form_submit_button("Salvar aposta")

if submit:
    add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status)
    st.success("Aposta salva!")

st.subheader("Histórico de apostas")
df = load_bets_df()
if not df.empty:
    st.dataframe(df, use_container_width=True)
    st.subheader("Análises")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Lucro por Status")
        fig, ax = plt.subplots()
        df.groupby("status")["lucro"].sum().plot(kind="bar", ax=ax, color=["green","red","gray","blue"])
        st.pyplot(fig)
    with col2:
        st.write("Lucro por Grupo")
        fig2, ax2 = plt.subplots()
        df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax2)
        st.pyplot(fig2)
else:
    st.info("Nenhuma aposta registrada ainda.")

