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
lucro = 0
if status == "Green":
lucro = retorno - valor
elif status == "Red":
lucro = -valor
elif status == "Void":
lucro = 0
c.execute("""
INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, odd, lucro, status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, valor, retorno, odd, lucro, status))
conn.commit()
conn.close()

def load_bets_df():
conn = sqlite3.connect("apostas.db")
df = pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)
conn.close()
return df

def update_bet(bet_id, grupo, casa, descricao, valor, retorno, odd, status):
conn = sqlite3.connect("apostas.db")
c = conn.cursor()
lucro = 0
if status == "Green":
lucro = retorno - valor
elif status == "Red":
lucro = -valor
elif status == "Void":
lucro = 0
c.execute("""
UPDATE apostas
SET grupo=?, casa=?, descricao=?, valor=?, retorno=?, odd=?, lucro=?, status=?
WHERE id=?
""", (grupo, casa, descricao, valor, retorno, odd, lucro, status, bet_id))
conn.commit()
conn.close()

# ==========================

# OCR

# ==========================

def extract_text_from_image(image, lang="por"):
try:
text = pytesseract.image_to_string(image, lang=lang)
return text
except Exception as e:
return f"Erro ao executar OCR: {e}"

def parse_bet_from_text(text):
grupo, casa, descricao, valor, retorno, odd, status = "", "", "", 0.0, 0.0, 1.0, "Void"
for line in text.splitlines():
line = line.strip().lower()
if "green" in line:
status = "Green"
elif "red" in line:
status = "Red"
elif "void" in line:
status = "Void"
if "grupo" in line:
grupo = line.replace("grupo", "").strip().title()
if "casa" in line:
casa = line.replace("casa", "").strip().title()
if "odd" in line:
try:
odd = float(line.replace("odd", "").strip().replace(",", "."))
except:
pass
if "valor" in line or "stake" in line:
try:
valor = float(line.replace("valor", "").replace("stake", "").replace("r$", "").strip().replace(",", "."))
except:
pass
if "retorno" in line or "ganho" in line:
try:
retorno = float(line.replace("retorno", "").replace("ganho", "").replace("r$", "").strip().replace(",", "."))
except:
pass
if "desc" in line or "jogo" in line:
descricao = line.replace("desc", "").replace("jogo", "").strip().title()
return grupo, casa, descricao, valor, retorno, odd, status

# ==========================

# APP STREAMLIT

# ==========================

st.set_page_config(page_title="App de Apostas", layout="wide")
st.title("📊 Controle de Apostas com OCR + Banco de Dados")

init_db()

# Upload de imagem e OCR

uploaded_file = st.file_uploader("📷 Envie uma imagem do bilhete", type=["png", "jpg", "jpeg"])
if uploaded_file:
image = Image.open(uploaded_file)
st.image(image, caption="Imagem enviada", use_container_width=True)
text = extract_text_from_image(image)
st.text_area("Texto OCR extraído:", text, height=150)
grupo, casa, descricao, valor, retorno, odd, status = parse_bet_from_text(text)
with st.expander("📌 Conferir/Editar dados extraídos"):
grupo = st.text_input("Grupo", grupo)
casa = st.text_input("Casa", casa)
descricao = st.text_input("Descrição", descricao)
valor = st.number_input("Valor apostado", min_value=0.0, value=valor, step=1.0)
retorno = st.number_input("Retorno", min_value=0.0, value=retorno, step=1.0)
odd = st.number_input("Odd", min_value=1.0, value=odd, step=0.01)
status = st.selectbox("Status", ["Green", "Red", "Void"], index=["Green", "Red", "Void"].index(status))
if st.button("💾 Salvar aposta extraída"):
add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status)
st.success("Aposta salva com sucesso!")

# Adicionar aposta manual

st.subheader("✍️ Adicionar aposta manualmente")
with st.form("nova_aposta"):
col1, col2 = st.columns(2)
with col1:
grupo = st.text_input("Grupo")
casa = st.text_input("Casa")
descricao = st.text_input("Descrição")
with col2:
valor = st.number_input("Valor apostado", min_value=0.0, step=1.0)
retorno = st.number_input("Retorno", min_value=0.0, step=1.0)
odd = st.number_input("Odd", min_value=1.0, step=0.01, value=1.0)
status = st.selectbox("Status", ["Green", "Red", "Void"])
submitted = st.form_submit_button("💾 Salvar aposta manual")
if submitted:
add_bet_to_db(grupo, casa, descricao, valor, retorno, odd, status)
st.success("Aposta adicionada com sucesso!")

# Listagem de apostas

st.subheader("📋 Minhas Apostas")
df = load_bets_df()
if not df.empty:
st.dataframe(df)

```
# Editar aposta
st.subheader("✏️ Editar aposta existente")
bet_id = st.selectbox("Selecione o ID da aposta para editar", df["id"].tolist())
aposta = df[df["id"] == bet_id].iloc[0]
with st.form("editar_aposta"):
    grupo = st.text_input("Grupo", aposta["grupo"])
    casa = st.text_input("Casa", aposta["casa"])
    descricao = st.text_input("Descrição", aposta["descricao"])
    valor = st.number_input("Valor apostado", min_value=0.0, value=float(aposta["valor"]), step=1.0)
    retorno = st.number_input("Retorno", min_value=0.0, value=float(aposta["retorno"]), step=1.0)
    odd = st.number_input("Odd", min_value=1.0, value=float(aposta["odd"]), step=0.01)
    status = st.selectbox("Status", ["Green", "Red", "Void"], index=["Green", "Red", "Void"].index(aposta["status"]))
    submitted_edit = st.form_submit_button("💾 Atualizar aposta")
    if submitted_edit:
        update_bet(bet_id, grupo, casa, descricao, valor, retorno, odd, status)
        st.success("Aposta atualizada com sucesso!")
        st.experimental_rerun()

# Resumo geral
st.subheader("📊 Resumo Geral")
total_apostas = len(df)
total_green = len(df[df["status"] == "Green"])
total_red = len(df[df["status"] == "Red"])
total_void = len(df[df["status"] == "Void"])
lucro_total = df["lucro"].sum()
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total apostas", total_apostas)
col2.metric("✅ Greens", total_green)
col3.metric("❌ Reds", total_red)
col4.metric("➖ Voids", total_void)
col5.metric("💰 Lucro total (R$)", round(lucro_total, 2))

# Gráficos
st.subheader("📈 Gráficos")
fig, ax = plt.subplots()
df["status"].value_counts().plot(kind="bar", ax=ax, color=["green", "red", "gray"])
ax.set_title("Distribuição por Status")
st.pyplot(fig)

fig2, ax2 = plt.subplots()
df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax2, color="blue")
ax2.set_title("Lucro por Grupo")
st.pyplot(fig2)
```

else:
st.info("Nenhuma aposta registrada ainda.")
