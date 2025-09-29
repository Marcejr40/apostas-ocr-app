import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import sqlite3
import re
import matplotlib.pyplot as plt
from datetime import datetime
import io

# -------------------------
# Configuração da página
# -------------------------
st.set_page_config(page_title="Apostas OCR (Completo)", layout="wide")
st.title("📊 Apostas OCR — App funcional")

# -------------------------
# Banco SQLite
# -------------------------
DB_PATH = "apostas.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    # cria tabela se não existir (coluna id fixa)
    c.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    conn.commit()

    # colunas esperadas e tipos
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
    c.execute("PRAGMA table_info(apostas)")
    existing = [row[1] for row in c.fetchall()]

    # adiciona colunas que faltam sem perder dados
    for col, typ in expected.items():
        if col not in existing:
            c.execute(f"ALTER TABLE apostas ADD COLUMN {col} {typ}")
    conn.commit()
    return conn

conn = init_db()

def add_bet_to_db(grupo, casa, descricao, valor, retorno, status):
    try:
        lucro = float(retorno) - float(valor)
    except:
        lucro = 0.0
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        grupo, casa, descricao, float(valor), float(retorno), float(lucro), status
    ))
    conn.commit()

def load_bets_df():
    return pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)

# -------------------------
# OCR + extração simples
# -------------------------
def parse_money_token(token: str):
    if token is None:
        return None
    s = str(token).strip()
    s = s.replace("R$", "").replace("r$", "").replace(" ", "")
    s = re.sub(r"[^0-9\.,\-]", "", s)
    if s == "":
        return None
    if "." in s and "," in s:
        s2 = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s2 = s.replace(",", ".")
    else:
        s2 = s
    s2 = re.sub(r"[^0-9\.\-]", "", s2)
    try:
        return float(s2)
    except:
        return None

def extract_money_candidates(text: str):
    candidates = []
    for m in re.findall(r"R\$\s*[0-9\.,]+", text, flags=re.I):
        val = parse_money_token(m)
        if val is not None:
            candidates.append(val)
    for m in re.findall(r"\b[0-9]{1,4}[.,][0-9]{1,3}\b", text):
        val = parse_money_token(m)
        if val is not None:
            candidates.append(val)
    if not candidates:
        for m in re.findall(r"\b[0-9]{1,4}\b", text):
            val = parse_money_token(m)
            if val is not None:
                candidates.append(val)
    return candidates

def detectar_status_simples(text: str):
    t = (text or "").lower()
    if any(k in t for k in ["green", "ganho", "ganhou", "venc"]):
        return "Green"
    if any(k in t for k in ["red", "perdida", "perdeu", "loss"]):
        return "Red"
    if any(k in t for k in ["void", "anulada", "cancelada", "reembolso"]):
        return "Void"
    return "Pendente"

def detect_casa(text: str):
    t = text.lower()
    if "bet365" in t or "bet 365" in t:
        return "Bet365"
    if "betano" in t:
        return "Betano"
    if "pinnacle" in t:
        return "Pinnacle"
    if "blaze" in t:
        return "Blaze"
    m = re.search(r"casa[:\-\s]*([A-Za-z0-9]+)", text, flags=re.I)
    if m:
        return m.group(1).strip()
    return "Desconhecida"

def infer_valor_retorno(text: str, status: str):
    v = None
    r = None
    # tentar por labels comuns
    m_v = re.search(r"(valor|apostado|aposta)[:\s]*R?\$?\s*([0-9\.,]+)", text, flags=re.I)
    m_r = re.search(r"(retorno|retorno obtido|retorno recebido)[:\s]*R?\$?\s*([0-9\.,]+)", text, flags=re.I)
    if m_v:
        v = parse_money_token(m_v.group(2))
    if m_r:
        r = parse_money_token(m_r.group(2))

    candidates = extract_money_candidates(text)
    if v is not None and r is not None:
        return float(v), float(r)
    if len(candidates) >= 2:
        s = sorted(candidates)
        return float(s[0]), float(s[-1])
    if len(candidates) == 1:
        only = candidates[0]
        if status == "Red":
            return float(only), 0.0
        if status == "Void":
            return float(only), float(only)
        if status == "Green":
            return 0.0, float(only)
        return float(only), 0.0
    return 0.0, 0.0

def process_image_file(uploaded_file):
    try:
        img = Image.open(uploaded_file)
    except Exception as e:
        return {"error": f"Erro ao abrir imagem: {e}"}
    try:
        text = pytesseract.image_to_string(img, lang="por")
    except Exception:
        text = pytesseract.image_to_string(img)
    text_clean = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

    status = detectar_status_simples(text_clean)
    casa = detect_casa(text_clean)
    valor_guess, retorno_guess = infer_valor_retorno(text_clean, status)

    lines = [l for l in text_clean.splitlines() if l.strip()]
    desc = lines[0] if lines else text_clean[:120]

    return {
        "texto": text_clean,
        "status": status,
        "casa": casa,
        "descricao": desc,
        "valor_guess": float(valor_guess or 0.0),
        "retorno_guess": float(retorno_guess or 0.0)
    }

# -------------------------
# UI - Upload e preview
# -------------------------
st.header("📷 Enviar print da aposta")
uploaded = st.file_uploader("Envie PNG/JPG do print", type=["png", "jpg", "jpeg"])

if uploaded:
    with st.spinner("Executando OCR..."):
        result = process_image_file(uploaded)
    if "error" in result:
        st.error(result["error"])
    else:
        st.subheader("🔎 Resultado do OCR:")
        st.json({
            "casa": result["casa"],
            "descricao": result["descricao"][:200],
            "valor_guess": result["valor_guess"],
            "retorno_guess": result["retorno_guess"],
            "status": result["status"]
        })

        with st.form("confirm_form"):
            st.write("Edite os campos se necessário antes de salvar:")
            grupo = st.text_input("Grupo", value="Grupo 1")
            casa = st.text_input("Casa", value=result["casa"])
            descricao = st.text_area("Descrição", value=result["descricao"])
            valor = st.number_input("Valor apostado (R$)", min_value=0.0, value=float(result["valor_guess"]), format="%.2f", step=0.5)
            retorno = st.number_input("Retorno (R$)", min_value=0.0, value=float(result["retorno_guess"]), format="%.2f", step=0.5)
            status = st.selectbox("Status", ["Green", "Red", "Void", "Pendente"], index=["Green","Red","Void","Pendente"].index(result["status"] if result["status"] in ["Green","Red","Void","Pendente"] else "Pendente"))
            submit = st.form_submit_button("Salvar aposta")
            if submit:
                add_bet_to_db(grupo, casa, descricao, valor, retorno, status)
                st.success("✅ Aposta salva!")

# -------------------------
# Histórico e dashboard
# -------------------------
st.header("📋 Histórico e Dashboard")

df = load_bets_df()
if df.empty:
    st.info("Nenhuma aposta registrada ainda. Faça upload de um print para começar.")
else:
    # filtros
    cols = st.columns([2, 2, 2, 4])
    with cols[0]:
        filtro_grupo = st.selectbox("Filtrar por Grupo", options=["Todos"] + sorted(df["grupo"].dropna().unique().tolist()))
    with cols[1]:
        filtro_casa = st.selectbox("Filtrar por Casa", options=["Todos"] + sorted(df["casa"].dropna().unique().tolist()))
    with cols[2]:
        filtro_status = st.selectbox("Filtrar por Status", options=["Todos"] + sorted(df["status"].dropna().unique().tolist()))

    df_display = df.copy()
    if filtro_grupo != "Todos":
        df_display = df_display[df_display["grupo"] == filtro_grupo]
    if filtro_casa != "Todos":
        df_display = df_display[df_display["casa"] == filtro_casa]
    if filtro_status != "Todos":
        df_display = df_display[df_display["status"] == filtro_status]

    st.subheader("Tabela de apostas")
    st.dataframe(df_display, use_container_width=True)

    # garantir tipos numéricos
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["retorno"] = pd.to_numeric(df["retorno"], errors="coerce").fillna(0.0)
    df["lucro"] = df["retorno"] - df["valor"]

    # métricas rápidas
    total_lucro = df["lucro"].sum()
    total_apostas = len(df)
    lucro_por_status = df.groupby("status")["lucro"].sum().reindex(["Green","Red","Void","Pendente"]).fillna(0)

    st.subheader("📊 Métricas rápidas")
    m1, m2, m3 = st.columns(3)
    m1.metric("Apostas registradas", total_apostas)
    m2.metric("Lucro total (R$)", f"{total_lucro:.2f}")
    greens = df[df["status"] == "Green"]
    perc_green = (len(greens) / total_apostas * 100) if total_apostas>0 else 0
    m3.metric("% Greens", f"{perc_green:.1f}%")

    # Gráficos visuais
    st.subheader("Gráficos")

    # pizza status (counts)
    fig1, ax1 = plt.subplots(figsize=(4,4))
    status_counts = df["status"].value_counts()
    ax1.pie(status_counts, labels=status_counts.index, autopct="%1.1f%%", textprops={'fontsize':9})
    ax1.set_title("Distribuição por Status")
    st.pyplot(fig1)

    # barra: lucro por grupo
    lucro_grupo = df.groupby("grupo")["lucro"].sum().sort_values(ascending=False)
    if not lucro_grupo.empty:
        fig2, ax2 = plt.subplots(figsize=(6,4))
        lucro_grupo.plot(kind="bar", ax=ax2)
        ax2.set_ylabel("Lucro (R$)")
        ax2.set_title("Lucro por Grupo")
        st.pyplot(fig2)

    # linha: lucro acumulado
    df_sorted = df.sort_values(by="id")
    fig3, ax3 = plt.subplots(figsize=(6,3))
    ax3.plot(df_sorted["id"].astype(int), df_sorted["lucro"].cumsum(), marker="o")
    ax3.set_xlabel("Registro (id)")
    ax3.set_ylabel("Lucro acumulado (R$)")
    ax3.set_title("Evolução do Lucro")
    st.pyplot(fig3)

    # barra horizontal: lucro por casa
    lucro_casa = df.groupby("casa")["lucro"].sum().sort_values()
    if len(lucro_casa) > 0:
        fig4, ax4 = plt.subplots(figsize=(6, max(2, len(lucro_casa)*0.6)))
        lucro_casa.plot(kind="barh", ax=ax4)
        ax4.set_xlabel("Lucro (R$)")
        ax4.set_title("Lucro por Casa de Aposta")
        st.pyplot(fig4)

    # exportar excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="RAW")
    buffer.seek(0)
    st.download_button("📥 Baixar Excel (RAW)", data=buffer, file_name="apostas_raw.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
