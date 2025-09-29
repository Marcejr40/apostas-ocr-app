```python
import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt

# -----------------------------
# Configuração do app
# -----------------------------
st.set_page_config(page_title="Apostas OCR", layout="wide")

# -----------------------------
# Banco de Dados SQLite
# -----------------------------
def init_db():
    conn = sqlite3.connect("apostas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo TEXT,
            casa TEXT,
            descricao TEXT,
            valor REAL,
            retorno REAL,
            status TEXT
        )
    """)
    conn.commit()
    return conn

conn = init_db()

def salvar_aposta(grupo, casa, descricao, valor, retorno, status):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO apostas (grupo, casa, descricao, valor, retorno, status) VALUES (?, ?, ?, ?, ?, ?)",
        (grupo, casa, descricao, valor, retorno, status),
    )
    conn.commit()

def carregar_apostas():
    return pd.read_sql("SELECT * FROM apostas", conn)

# -----------------------------
# Função para processar imagens
# -----------------------------
def processar_imagem(uploaded_file):
    image = Image.open(uploaded_file)
    texto = pytesseract.image_to_string(image, lang="por")

    status = "Indefinido"
    if "green" in texto.lower():
        status = "Green"
    elif "red" in texto.lower():
        status = "Red"
    elif "void" in texto.lower():
        status = "Void"

    valor = 0
    retorno = 0
    for linha in texto.splitlines():
        if "R$" in linha:
            numeros = [n.replace("R$", "").replace(",", ".").strip() for n in linha.split() if "R$" in n]
            try:
                if len(numeros) >= 1:
                    valor = float(numeros[0])
                if len(numeros) >= 2:
                    retorno = float(numeros[1])
            except:
                pass

    return {
        "grupo": "Grupo 1",  # preenchimento manual depois
        "casa": "Betano",    # detectar por OCR depois
        "descricao": texto[:50],
        "valor": valor,
        "retorno": retorno,
        "status": status,
    }

# -----------------------------
# Interface Streamlit
# -----------------------------
st.title("📊 Sistema de Apostas com OCR + Dashboard")

# Upload
uploaded_file = st.file_uploader("Envie um print da aposta", type=["png", "jpg", "jpeg"])
if uploaded_file:
    aposta = processar_imagem(uploaded_file)
    st.write("🔍 Resultado do OCR:", aposta)

    if st.button("Salvar aposta"):
        salvar_aposta(
            aposta["grupo"], aposta["casa"], aposta["descricao"], aposta["valor"], aposta["retorno"], aposta["status"]
        )
        st.success("✅ Aposta salva no banco de dados!")

# Carregar apostas salvas
df = carregar_apostas()
if not df.empty:
    st.subheader("📑 Histórico de Apostas")
    st.dataframe(df)

    # Calcular lucro/prejuízo
    df["lucro"] = df["retorno"] - df["valor"]

    st.subheader("📈 Gráficos de Desempenho")

    # Gráfico 1 - Evolução do lucro acumulado
    st.write("Evolução do Lucro (R$)")
    df["lucro_acumulado"] = df["lucro"].cumsum()
    fig, ax = plt.subplots()
    ax.plot(df.index, df["lucro_acumulado"], marker="o")
    ax.set_ylabel("Lucro acumulado (R$)")
    st.pyplot(fig)

    # Gráfico 2 - Lucro por grupo
    st.write("Lucro por Grupo")
    fig, ax = plt.subplots()
    df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax)
    ax.set_ylabel("Lucro (R$)")
    st.pyplot(fig)

    # Gráfico 3 - Distribuição por status
    st.write("Distribuição por Status")
    fig, ax = plt.subplots()
    df["status"].value_counts().plot(kind="pie", autopct="%1.1f%%", ax=ax)
    ax.set_ylabel("")
    st.pyplot(fig)

    # Gráfico 4 - Lucro por casa de aposta
    st.write("Lucro por Casa de Aposta")
    fig, ax = plt.subplots()
    df.groupby("casa")["lucro"].sum().plot(kind="barh", ax=ax)
    ax.set_xlabel("Lucro (R$)")
    st.pyplot(fig)
else:
    st.info("Nenhuma aposta registrada ainda. Faça upload de um print para começar.")
```
