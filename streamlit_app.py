import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytesseract
from PIL import Image
import matplotlib.pyplot as plt

# ========================

# BANCO DE DADOS

# ========================

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
lucro REAL,
status TEXT
)
""")
conn.commit()
conn.close()

def add_bet_to_db(grupo, casa, descricao, valor, retorno, status):
conn = sqlite3.connect("apostas.db")
c = conn.cursor()
lucro = float(retorno) - float(valor)
c.execute("""
INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, lucro, status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, float(valor), float(retorno), lucro, status))
conn.commit()
conn.close()

def load_bets_df():
conn = sqlite3.connect("apostas.db")
df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
conn.close()
return df

def update_bet_in_db(bet_id, grupo, casa, descricao, valor, retorno, status):
conn = sqlite3.connect("apostas.db")
c = conn.cursor()
lucro = float(retorno) - float(valor)
c.execute("""
UPDATE apostas
SET grupo=?, casa=?, descricao=?, valor=?, retorno=?, lucro=?, status=?
WHERE id=?
""", (grupo, casa, descricao, float(valor), float(retorno), lucro, status, bet_id))
conn.commit()
conn.close()

def delete_bet_from_db(bet_id):
conn = sqlite3.connect("apostas.db")
c = conn.cursor()
c.execute("DELETE FROM apostas WHERE id=?", (bet_id,))
conn.commit()
conn.close()

# ========================

# APP STREAMLIT

# ========================

st.set_page_config(page_title="Gestor de Apostas OCR", layout="wide")
st.title("📊 Gestor de Apostas com OCR + Banco de Dados")

init_db()

menu = st.sidebar.radio("Navegação", ["➕ Nova Aposta", "📑 Histórico"])

# ========================

# NOVA APOSTA

# ========================

if menu == "➕ Nova Aposta":
st.header("➕ Lançar Nova Aposta")

```
uploaded_file = st.file_uploader("Envie um print (opcional)", type=["png", "jpg", "jpeg"])
descricao = ""
valor, retorno, status = 0.0, 0.0, "Void"

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Imagem enviada", use_container_width=True)

    try:
        text = pytesseract.image_to_string(image, lang="por")
        st.text_area("Texto detectado", text, height=120)
        descricao = text[:200]  # resumo automático
    except Exception as e:
        st.error(f"Erro no OCR: {e}")

with st.form("nova_aposta_form"):
    grupo = st.text_input("Grupo", "")
    casa = st.text_input("Casa de Apostas", "")
    descricao = st.text_area("Descrição", descricao)
    valor = st.number_input("Valor apostado (R$)", min_value=0.0, step=1.0, value=valor)
    retorno = st.number_input("Retorno (R$)", min_value=0.0, step=1.0, value=retorno)
    status = st.selectbox("Status", ["Green", "Red", "Void"])

    submitted = st.form_submit_button("💾 Salvar Aposta")

    if submitted:
        add_bet_to_db(grupo, casa, descricao, valor, retorno, status)
        st.success("✅ Aposta salva com sucesso!")
```

# ========================

# HISTÓRICO + EDIÇÃO + FILTROS

# ========================

elif menu == "📑 Histórico":
st.header("📑 Histórico de Apostas")
df = load_bets_df()

```
if df.empty:
    st.info("Nenhuma aposta lançada ainda.")
else:
    df["criado_em"] = pd.to_datetime(df["criado_em"])

    # FILTROS
    st.subheader("🔎 Filtros")
    col1, col2, col3 = st.columns(3)

    data_inicio = col1.date_input("Data início", df["criado_em"].min().date())
    data_fim = col2.date_input("Data fim", df["criado_em"].max().date())
    grupo_filtro = col3.selectbox("Grupo", ["Todos"] + sorted(df["grupo"].dropna().unique().tolist()))

    df_filtrado = df[(df["criado_em"].dt.date >= data_inicio) & (df["criado_em"].dt.date <= data_fim)]
    if grupo_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["grupo"] == grupo_filtro]

    # RESUMO
    total_valor = df_filtrado["valor"].sum()
    total_retorno = df_filtrado["retorno"].sum()
    total_lucro = df_filtrado["lucro"].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("💸 Total Apostado", f"R$ {total_valor:,.2f}")
    col2.metric("📥 Total Retorno", f"R$ {total_retorno:,.2f}")
    col3.metric("📊 Lucro Líquido", f"R$ {total_lucro:,.2f}")

    st.divider()

    # LISTAGEM EDITÁVEL
    for idx, row in df_filtrado.iterrows():
        with st.expander(f"ID {row['id']} | {row['casa']} | {row['status']} | R$ {row['valor']}"):
            with st.form(f"edit_form_{row['id']}"):
                grupo = st.text_input("Grupo", row["grupo"])
                casa = st.text_input("Casa de Apostas", row["casa"])
                descricao = st.text_area("Descrição", row["descricao"])
                valor = st.number_input("Valor apostado (R$)", min_value=0.0, step=1.0, value=row["valor"])
                retorno = st.number_input("Retorno (R$)", min_value=0.0, step=1.0, value=row["retorno"])
                status = st.selectbox("Status", ["Green", "Red", "Void"], index=["Green", "Red", "Void"].index(row["status"]))

                col1, col2 = st.columns(2)
                with col1:
                    salvar = st.form_submit_button("💾 Salvar Alterações")
                with col2:
                    excluir = st.form_submit_button("🗑️ Excluir Aposta")

                if salvar:
                    update_bet_in_db(row["id"], grupo, casa, descricao, valor, retorno, status)
                    st.success(f"Aposta {row['id']} atualizada com sucesso!")
                    st.experimental_rerun()

                if excluir:
                    delete_bet_from_db(row["id"])
                    st.warning(f"Aposta {row['id']} excluída com sucesso!")
                    st.experimental_rerun()

    # GRÁFICOS
    if not df_filtrado.empty:
        st.subheader("📈 Relatórios")

        col1, col2 = st.columns(2)
        with col1:
            st.write("Lucro total por Grupo (R$)")
            fig, ax = plt.subplots()
            df_filtrado.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax, color="green")
            ax.set_ylabel("Lucro (R$)")
            st.pyplot(fig)

        with col2:
            st.write("Lucro total por Casa (R$)")
            fig, ax = plt.subplots()
            df_filtrado.groupby("casa")["lucro"].sum().plot(kind="bar", ax=ax, color="blue")
            ax.set_ylabel("Lucro (R$)")
            st.pyplot(fig)

        st.write("Distribuição por Status (quantidade)")
        fig, ax = plt.subplots()
        df_filtrado["status"].value_counts().plot(kind="pie", autopct="%1.1f%%", ax=ax)
        st.pyplot(fig)

        st.write("Lucro por Status (R$)")
        fig, ax = plt.subplots()
        df_filtrado.groupby("status")["lucro"].sum().plot(kind="bar", ax=ax, color=["green", "red", "gray"])
        ax.set_ylabel("Lucro (R$)")
        st.pyplot(fig)

