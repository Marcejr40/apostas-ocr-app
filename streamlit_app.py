import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
import re
import matplotlib.pyplot as plt
from datetime import datetime
import io

# -------------------------
# Config da página
# -------------------------
st.set_page_config(page_title="Gestor de Apostas OCR", layout="wide")
st.title("📊 Gestor de Apostas com OCR + SQLite")

# -------------------------
# Banco SQLite (inicializa)
# -------------------------
DB_PATH = "apostas.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
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
    return conn

conn = init_db()

def add_bet_to_db(grupo, casa, descricao, valor, retorno, status):
    try:
        lucro = float(retorno) - float(valor)
    except:
        lucro = 0.0
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        grupo, casa, descricao, float(valor), float(retorno), float(lucro), status
    ))
    conn.commit()

def update_bet_in_db(bet_id, grupo, casa, descricao, valor, retorno, status):
    try:
        lucro = float(retorno) - float(valor)
    except:
        lucro = 0.0
    cur = conn.cursor()
    cur.execute("""
        UPDATE apostas
        SET grupo=?, casa=?, descricao=?, valor=?, retorno=?, lucro=?, status=?
        WHERE id=?
    """, (grupo, casa, descricao, float(valor), float(retorno), float(lucro), status, bet_id))
    conn.commit()

def delete_bet_from_db(bet_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM apostas WHERE id=?", (bet_id,))
    conn.commit()

def load_bets_df():
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id DESC", conn)
    return df

# -------------------------
# Funções de OCR / parsing
# -------------------------
def parse_money_token(token: str):
    if token is None:
        return None
    s = str(token).strip()
    s = s.replace("R$", "").replace("r$", "").replace(" ", "")
    s = re.sub(r"[^0-9\.,\-]", "", s)
    if s == "":
        return None
    # pt-BR style: '.' thousands, ',' decimal
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
    # tokens with R$
    for m in re.findall(r"R\$\s*[0-9\.,]+", text, flags=re.I):
        val = parse_money_token(m)
        if val is not None:
            candidates.append(val)
    # numbers with separators
    for m in re.findall(r"\b[0-9]{1,4}[.,][0-9]{1,3}\b", text):
        val = parse_money_token(m)
        if val is not None:
            candidates.append(val)
    # fallback small integers
    if not candidates:
        for m in re.findall(r"\b[0-9]{1,4}\b", text):
            val = parse_money_token(m)
            if val is not None:
                candidates.append(val)
    return candidates

def detect_casa(text: str):
    t = (text or "").lower()
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

def detectar_status(text: str):
    t = (text or "").lower()
    green_words = ["green", "ganho", "ganhou", "venc", "won"]
    red_words = ["red", "perd", "perdeu", "loss", "lost"]
    void_words = ["void", "anulad", "cancel", "refund", "reembolso"]

    if any(w in t for w in green_words):
        return "Green"
    if any(w in t for w in red_words):
        # prefer green if both appear
        if any(w in t for w in green_words):
            return "Green"
        return "Red"
    if any(w in t for w in void_words):
        return "Void"

    # fallback simple heuristics
    if "retorno" in t and "%" not in t:
        # if has "retorno" and a number likely green
        return "Green"
    return "Pendente"

def infer_valor_retorno(text: str, status: str):
    # try labeled extraction
    v = None
    r = None
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
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

    casa = detect_casa(text)
    status = detectar_status(text)
    valor_guess, retorno_guess = infer_valor_retorno(text, status)

    # descricao: pick longest line or first
    lines = [l for l in text.splitlines() if l.strip()]
    descricao = lines[0] if lines else text[:120]

    return {
        "texto": text,
        "casa": casa,
        "status": status,
        "valor_guess": float(valor_guess),
        "retorno_guess": float(retorno_guess),
        "descricao": descricao
    }

# -------------------------
# UI
# -------------------------
menu = st.sidebar.radio("Navegação", ["➕ Nova Aposta", "📑 Histórico"])

if menu == "➕ Nova Aposta":
    st.header("➕ Lançar Nova Aposta")
    uploaded = st.file_uploader("Enviar print (opcional)", type=["png", "jpg", "jpeg"])
    pre_desc = ""
    pre_val, pre_ret, pre_status, pre_casa = 0.0, 0.0, "Pendente", ""

    if uploaded:
        st.image(uploaded, caption="Print enviado", use_container_width=True)
        with st.spinner("Executando OCR..."):
            result = process_image_file(uploaded)
        if "error" in result:
            st.error(result["error"])
        else:
            st.subheader("Texto extraído (revise):")
            st.text_area("", result["texto"], height=180)
            pre_desc = result["descricao"]
            pre_val = result["valor_guess"]
            pre_ret = result["retorno_guess"]
            pre_status = result["status"]
            pre_casa = result["casa"]

    with st.form("form_nova"):
        grupo = st.text_input("Grupo", value="Grupo 1")
        casa = st.text_input("Casa de Apostas", value=pre_casa)
        descricao = st.text_area("Descrição", value=pre_desc)
        valor = st.number_input("Valor apostado (R$)", min_value=0.0, value=float(pre_val), format="%.2f")
        retorno = st.number_input("Retorno (R$)", min_value=0.0, value=float(pre_ret), format="%.2f")
        status = st.selectbox("Status", ["Green", "Red", "Void", "Pendente"], index=["Green","Red","Void","Pendente"].index(pre_status if pre_status in ["Green","Red","Void","Pendente"] else "Pendente"))
        submit = st.form_submit_button("💾 Salvar aposta")
        if submit:
            add_bet_to_db(grupo, casa, descricao, valor, retorno, status)
            st.success("Aposta salva com sucesso!")
            st.experimental_rerun()

elif menu == "📑 Histórico":
    st.header("📑 Histórico de Apostas")
    df = load_bets_df()
    if df.empty:
        st.info("Nenhuma aposta registrada ainda.")
    else:
        # convert dates & numeric
        df["criado_em"] = pd.to_datetime(df["criado_em"])
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
        df["retorno"] = pd.to_numeric(df["retorno"], errors="coerce").fillna(0.0)
        df["lucro"] = pd.to_numeric(df["lucro"], errors="coerce").fillna(df["retorno"] - df["valor"])

        # filtros: data, grupo, casa, status
        st.subheader("🔎 Filtros")
        col1, col2, col3, col4 = st.columns(4)
        min_date = df["criado_em"].min().date()
        max_date = df["criado_em"].max().date()
        start = col1.date_input("Data início", min_date)
        end = col2.date_input("Data fim", max_date)
        grupo_opt = ["Todos"] + sorted(df["grupo"].dropna().unique().tolist())
        casa_opt = ["Todos"] + sorted(df["casa"].dropna().unique().tolist())
        grupo_sel = col3.selectbox("Grupo", grupo_opt)
        casa_sel = col4.selectbox("Casa", casa_opt)
        status_sel = st.selectbox("Status", options=["Todos"] + sorted(df["status"].dropna().unique().tolist()))

        # aplicar
        mask = (df["criado_em"].dt.date >= start) & (df["criado_em"].dt.date <= end)
        df_f = df[mask].copy()
        if grupo_sel != "Todos":
            df_f = df_f[df_f["grupo"] == grupo_sel]
        if casa_sel != "Todos":
            df_f = df_f[df_f["casa"] == casa_sel]
        if status_sel != "Todos":
            df_f = df_f[df_f["status"] == status_sel]

        # resumo
        total_val = df_f["valor"].sum()
        total_ret = df_f["retorno"].sum()
        total_luc = df_f["lucro"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Apostado (R$)", f"{total_val:,.2f}")
        c2.metric("Total Retorno (R$)", f"{total_ret:,.2f}")
        c3.metric("Lucro Líquido (R$)", f"{total_luc:,.2f}")

        st.divider()

        # edição por aposta (form completo)
        st.subheader("Editar / Excluir apostas (abra o item e edite tudo antes de salvar)")
        for _, row in df_f.iterrows():
            with st.expander(f"ID {int(row['id'])} | {row['casa']} | {row['status']} | R$ {row['valor']:.2f}"):
                with st.form(f"edit_{int(row['id'])}"):
                    g = st.text_input("Grupo", value=row["grupo"])
                    c = st.text_input("Casa", value=row["casa"])
                    d = st.text_area("Descrição", value=row["descricao"])
                    v = st.number_input("Valor (R$)", min_value=0.0, value=float(row["valor"]), format="%.2f", key=f"v_{int(row['id'])}")
                    r = st.number_input("Retorno (R$)", min_value=0.0, value=float(row["retorno"]), format="%.2f", key=f"r_{int(row['id'])}")
                    st_status = st.selectbox("Status", ["Green","Red","Void","Pendente"], index=["Green","Red","Void","Pendente"].index(row["status"] if row["status"] in ["Green","Red","Void","Pendente"] else "Pendente"), key=f"s_{int(row['id'])}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        ok = st.form_submit_button("💾 Salvar alterações")
                    with col_b:
                        rm = st.form_submit_button("🗑️ Excluir aposta")
                    if ok:
                        update_bet_in_db(int(row["id"]), g, c, d, v, r, st_status)
                        st.success("Aposta atualizada!")
                        st.experimental_rerun()
                    if rm:
                        delete_bet_from_db(int(row["id"]))
                        st.warning("Aposta excluída!")
                        st.experimental_rerun()

        # tabela resumida
        st.subheader("Tabela (visualização atual)")
        st.dataframe(df_f, use_container_width=True)

        # gráficos
        st.subheader("Relatórios / Gráficos")
        # pie status counts
        st.write("Distribuição por Status (quantidade)")
        fig1, ax1 = plt.subplots()
        df_f["status"].value_counts().plot(kind="pie", autopct="%1.1f%%", ax=ax1)
        st.pyplot(fig1)

        # lucro por grupo (R$)
        st.write("Lucro por Grupo (R$)")
        fig2, ax2 = plt.subplots()
        df_f.groupby("grupo")["lucro"].sum().sort_values(ascending=False).plot(kind="bar", ax=ax2)
        ax2.set_ylabel("Lucro (R$)")
        st.pyplot(fig2)

        # lucro por casa (R$)
        st.write("Lucro por Casa (R$)")
        fig3, ax3 = plt.subplots()
        df_f.groupby("casa")["lucro"].sum().sort_values(ascending=False).plot(kind="bar", ax=ax3)
        ax3.set_ylabel("Lucro (R$)")
        st.pyplot(fig3)

        # lucro acumulado ao longo do tempo
        st.write("Evolução do Lucro (acumulado)")
        df_time = df_f.sort_values(by="criado_em")
        fig4, ax4 = plt.subplots()
        ax4.plot(df_time["criado_em"], df_time["lucro"].cumsum(), marker="o")
        ax4.set_ylabel("Lucro acumulado (R$)")
        ax4.set_xlabel("Data")
        st.pyplot(fig4)

        # exportar excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_f.to_excel(writer, index=False, sheet_name="RAW")
        buffer.seek(0)
        st.download_button("📥 Baixar Excel (filtrado)", data=buffer, file_name="apostas_filtradas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
