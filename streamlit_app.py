```python
import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import sqlite3
import re
import matplotlib.pyplot as plt
from datetime import datetime

# ===============================
# BANCO DE DADOS
# ===============================
DB_PATH = "apostas.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    # cria tabela se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    conn.commit()

    # colunas esperadas
    expected = {
        "criado_em": "TEXT",
        "grupo": "TEXT",
        "casa": "TEXT",
        "descricao": "TEXT",
        "valor": "REAL",
        "retorno": "REAL",
        "lucro": "REAL",
        "status": "TEXT"
    }

    # checa colunas já existentes
    cursor.execute("PRAGMA table_info(apostas)")
    existing = [row[1] for row in cursor.fetchall()]

    # adiciona colunas que faltam
    for col, typ in expected.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE apostas ADD COLUMN {col} {typ}")
    conn.commit()
    return conn

conn = init_db()

def add_bet_to_db(grupo, casa, descricao, valor, retorno, status):
    try:
        lucro = float(retorno) - float(valor)
    except:
        lucro = 0.0
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        grupo, casa, descricao, float(valor), float(retorno), float(lucro), status
    ))
    conn.commit()

def load_bets_df():
    return pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)

# ===============================
# OCR + EXTRAÇÃO
# ===============================
def extrair_dados_texto(texto):
    grupo = "Grupo 1"
    casa = "Betano"

    # valor apostado
    valor_match = re.search(r"R?\$?\s?(\d+[,.]?\d*)", texto)
    valor = float(valor_match.group(1).replace(",", ".")) if valor_match else 0

    # retorno
    retorno_match = re.search(r"retorno\s*R?\$?\s?(\d+[,.]?\d*)", texto, re.IGNORECASE)
    retorno = float(retorno_match.group(1).replace(",", ".")) if retorno_match else 0

    # status
    if "green" in texto.lower():
        status = "Green"
    elif "red" in texto.lower():
        status = "Red"
    elif "void" in texto.lower():
        status = "Void"
    else:
        status = "Indefinido"

    return {
        "grupo": grupo,
        "casa": casa,
        "descricao": texto[:100],
        "valor": valor,
        "retorno": retorno,
        "status": status,
    }

def processar_imagem(imagem):
    texto = pytesseract.image_to_string(imagem, lang="por")
    return extrair_dados_texto(texto)

# ===============================
# INTERFACE STREAMLIT
# ===============================
st.set_page_config(page_title="App de Apostas OCR", layout="wide")
st.title("📊 Controle de Apostas com OCR + Banco de Dados")

# upload da imagem
uploaded_file = st.file_uploader("Envie um print da aposta", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    imagem = Image.open(uploaded_file)
    dados = processar_imagem(imagem)
    st.subheader("Resultado do OCR:")
    st.json(dados)

    if st.button("Salvar aposta"):
        add_bet_to_db(
            dados["grupo"],
            dados["casa"],
            dados["descricao"],
            dados["valor"],
            dados["retorno"],
            dados["status"],
        )
        st.success("✅ Aposta salva no banco com sucesso!")

# ===============================
# HISTÓRICO E GRÁFICOS
# ===============================
df = load_bets_df()

if not df.empty:
    st.subheader("📋 Histórico de Apostas")

    # filtro por grupo
    grupos = ["Todos"] + sorted(df["grupo"].dropna().unique().tolist())
    grupo_filtro = st.selectbox("Filtrar por grupo:", grupos)

    if grupo_filtro != "Todos":
        df = df[df["grupo"] == grupo_filtro]

    st.dataframe(df, use_container_width=True)

    # calcula lucro (se não existir)
    if "lucro" not in df.columns:
        df["lucro"] = df.apply(
            lambda row: row["retorno"] - row["valor"] if row["status"] == "Green"
            else (-row["valor"] if row["status"] == "Red" else 0),
            axis=1,
        )

    # escolha do gráfico
    opcao = st.radio("Visualizar gráfico de:", [
        "Lucro Total por Status",
        "Lucro Acumulado",
        "Lucro por Grupo"
    ])

    if opcao == "Lucro Total por Status":
        resumo = df.groupby("status")["lucro"].sum()
        st.write("### Lucro Total por Status")
        st.bar_chart(resumo)

    elif opcao == "Lucro Acumulado":
        df["lucro_acumulado"] = df["lucro"].cumsum()
        st.write("### Lucro Acumulado")
        fig, ax = plt.subplots()
        ax.plot(df.index, df["lucro_acumulado"], marker="o")
        ax.set_title("Lucro Acumulado")
        ax.set_xlabel("Apostas")
        ax.set_ylabel("Lucro (R$)")
        st.pyplot(fig)

    elif opcao == "Lucro por Grupo":
        resumo_grupo = df.groupby("grupo")["lucro"].sum()
        st.write("### Lucro Total por Grupo")
        st.bar_chart(resumo_grupo)

else:
    st.info("Nenhuma aposta registrada ainda. Faça upload de um print para começar.")
```
