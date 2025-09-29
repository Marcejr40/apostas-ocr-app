import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
from datetime import datetime
import matplotlib.pyplot as plt
import re
import io

DB = "apostas.db"

# -------------------------
# Inicializar DB (garante colunas)
# -------------------------
def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
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

def add_bet(grupo, casa, descricao, odd, valor, retorno, status):
    lucro = 0.0
    try:
        if status.lower() == "green":
            lucro = float(retorno) - float(valor)
        elif status.lower() == "red":
            lucro = -float(valor)
        elif status.lower() == "void":
            lucro = 0.0
    except:
        lucro = 0.0
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, odd, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          grupo, casa, descricao, odd if odd is not None else None, valor, retorno, lucro, status))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect(DB, check_same_thread=False)
    df = pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)
    conn.close()
    return df

def update_bet(bet_id, grupo, casa, descricao, odd, valor, retorno, status):
    lucro = 0.0
    try:
        if status.lower() == "green":
            lucro = float(retorno) - float(valor)
        elif status.lower() == "red":
            lucro = -float(valor)
        elif status.lower() == "void":
            lucro = 0.0
    except:
        lucro = 0.0
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        UPDATE apostas SET grupo=?, casa=?, descricao=?, odd=?, valor=?, retorno=?, lucro=?, status=?
        WHERE id=?
    """, (grupo, casa, descricao, odd if odd is not None else None, valor, retorno, lucro, status, bet_id))
    conn.commit()
    conn.close()

def delete_bet(bet_id):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM apostas WHERE id=?", (bet_id,))
    conn.commit()
    conn.close()

# -------------------------
# Funções OCR e heurísticas
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

def detectar_status(text: str):
    t = (text or "").lower()
    green_words = ["green", "ganho", "ganhou", "venc", "won", "win"]
    red_words = ["red", "perd", "perdeu", "loss", "lost"]
    void_words = ["void", "anulad", "cancel", "refund", "reembolso"]
    if any(w in t for w in green_words):
        return "Green"
    if any(w in t for w in red_words):
        if any(w in t for w in green_words):
            return "Green"
        return "Red"
    if any(w in t for w in void_words):
        return "Void"
    if "retorno" in t and re.search(r"[0-9]", t):
        return "Green"
    return "Pendente"

def infer_valor_retorno(text: str, status: str):
    v = None
    r = None
    m_v = re.search(r"(valor|apostado|aposta)[:\s]*R?\$?\s*([0-9\.,]+)", text, flags=re.I)
    m_r = re.search(r"(retorno|retorno obtido|retorno recebido|retorno obtido)[:\s]*R?\$?\s*([0-9\.,]+)", text, flags=re.I)
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

def infer_odd(text: str):
    m = re.search(r"(odd|odds|cotação|cotacao)[:\s]*([0-9]+[.,][0-9]+)", text, flags=re.I)
    if m:
        return parse_money_token(m.group(2))
    nums = re.findall(r"\b[0-9]{1,2}[.,][0-9]{1,4}\b", text)
    for n in nums:
        val = parse_money_token(n)
        if val and val >= 1.01 and val <= 100.0:
            return val
    return None

def pick_description(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""
    lines_sorted = sorted(lines, key=lambda s: len(s), reverse=True)
    return lines_sorted[0][:300]

def process_uploaded_image(uploaded_file):
    try:
        img = Image.open(uploaded_file)
    except Exception as e:
        return {"error": f"Erro ao abrir imagem: {e}"}
    try:
        text = pytesseract.image_to_string(img, lang="por")
    except Exception:
        text = pytesseract.image_to_string(img)
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
    casa = "Desconhecida"
    status = detectar_status(text)
    valor_guess, retorno_guess = infer_valor_retorno(text, status)
    odd_guess = infer_odd(text)
    descricao = pick_description(text)
    return {
        "texto": text,
        "casa": casa,
        "status": status,
        "valor_guess": float(valor_guess or 0.0),
        "retorno_guess": float(retorno_guess or 0.0),
        "odd_guess": float(odd_guess) if odd_guess is not None else None,
        "descricao": descricao
    }

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="Gestor de Apostas OCR", layout="wide")
st.title("📊 Gestor de Apostas com OCR + SQLite (versão completa)")

init_db()

menu = st.sidebar.radio("Navegação", ["➕ Nova Aposta", "📑 Histórico"])

if menu == "➕ Nova Aposta":
    st.header("➕ Lançar Nova Aposta")
    uploaded = st.file_uploader("Enviar print (opcional) - PNG/JPG", type=["png", "jpg", "jpeg"])
    pre_desc = ""
    pre_val = 0.0
    pre_ret = 0.0
    pre_status = "Pendente"
    pre_odd = 0.0
    pre_casa = ""
    if uploaded:
        st.image(uploaded, caption="Print enviado", use_container_width=True)
        with st.spinner("Executando OCR..."):
            result = process_uploaded_image(uploaded)
        if "error" in result:
            st.error(result["error"])
        else:
            st.subheader("Texto extraído (revise):")
            st.text_area("", result["texto"], height=180)
            pre_desc = result["descricao"]
            pre_val = result["valor_guess"]
            pre_ret = result["retorno_guess"]
            pre_status = result["status"]
            pre_odd = result["odd_guess"] if result["odd_guess"] is not None else 0.0
            pre_casa = result["casa"]
    with st.form("form_new"):
        grupo = st.text_input("Grupo", value="Grupo 1")
        casa = st.text_input("Casa de Aposta", value=pre_casa)
        descricao = st.text_area("Descrição", value=pre_desc)
        odd = st.number_input("Odd (cotação) — só para conferência", min_value=0.0, value=float(pre_odd or 0.0), format="%.2f")
        valor = st.number_input("Valor apostado (R$)", min_value=0.0, value=float(pre_val or 0.0), format="%.2f")
        retorno = st.number_input("Retorno (R$)", min_value=0.0, value=float(pre_ret or 0.0), format="%.2f")
        status = st.selectbox("Status", options=["Green", "Red", "Void", "Pendente"], index=["Green","Red","Void","Pendente"].index(pre_status if pre_status in ["Green","Red","Void","Pendente"] else "Pendente"))
        submit = st.form_submit_button("💾 Salvar aposta")
        if submit:
            add_bet(grupo, casa, descricao, odd if odd>0 else None, valor, retorno, status)
            st.success("Aposta salva com sucesso!")
            st.rerun()

elif menu == "📑 Histórico":
    st.header("📑 Histórico de Apostas")
    df = load_bets_df()
    if df.empty:
        st.info("Nenhuma aposta registrada ainda.")
    else:
        df["criado_em"] = pd.to_datetime(df["criado_em"], errors="coerce")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
        df["retorno"] = pd.to_numeric(df["retorno"], errors="coerce").fillna(0.0)
        if "lucro" not in df.columns or df["lucro"].isnull().any():
            df["lucro"] = df["retorno"] - df["valor"]
        st.subheader("🔎 Filtros")
        col1, col2, col3, col4 = st.columns(4)
        min_date = df["criado_em"].min().date() if not df["criado_em"].isna().all() else datetime.now().date()
        max_date = df["criado_em"].max().date() if not df["criado_em"].isna().all() else datetime.now().date()
        start = col1.date_input("Data início", min_date)
        end = col2.date_input("Data fim", max_date)
        grupo_opt = ["Todos"] + sorted(df["grupo"].dropna().unique().tolist())
        casa_opt = ["Todos"] + sorted(df["casa"].dropna().unique().tolist())
        grupo_sel = col3.selectbox("Grupo", grupo_opt)
        casa_sel = col4.selectbox("Casa", casa_opt)
        status_sel = st.selectbox("Status", options=["Todos"] + sorted(df["status"].dropna().unique().tolist()))
        mask = (df["criado_em"].dt.date >= start) & (df["criado_em"].dt.date <= end)
        df_f = df[mask].copy()
        if grupo_sel != "Todos":
            df_f = df_f[df_f["grupo"] == grupo_sel]
        if casa_sel != "Todos":
            df_f = df_f[df_f["casa"] == casa_sel]
        if status_sel != "Todos":
            df_f = df_f[df_f["status"] == status_sel]
        total_val = df_f["valor"].sum()
        total_ret = df_f["retorno"].sum()
        total_luc = df_f["lucro"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Apostado (R$)", f"{total_val:,.2f}")
        c2.metric("Total Retorno (R$)", f"{total_ret:,.2f}")
        c3.metric("Lucro Líquido (R$)", f"{total_luc:,.2f}")
        st.divider()
        st.subheader("✏️ Editar / Excluir apostas")
        for _, row in df_f.iterrows():
            id_int = int(row["id"])
            header = f"ID {id_int} | {row.get('casa','')} | {row.get('status','')} | R$ {row.get('valor',0):.2f}"
            with st.expander(header):
                with st.form(f"edit_form_{id_int}"):
                    new_grp = st.text_input("Grupo", value=row.get("grupo",""), key=f"g_{id_int}")
                    new_casa = st.text_input("Casa", value=row.get("casa",""), key=f"c_{id_int}")
                    new_desc = st.text_area("Descrição", value=row.get("descricao",""), key=f"d_{id_int}")
                    new_odd = st.number_input("Odd (cotação)", min_value=0.0, value=float(row.get("odd") if row.get("odd") is not None else 0.0), format="%.2f", key=f"od_{id_int}")
                    new_val = st.number_input("Valor (R$)", min_value=0.0, value=float(row.get("valor",0.0)), format="%.2f", key=f"v_{id_int}")
                    new_ret = st.number_input("Retorno (R$)", min_value=0.0, value=float(row.get("retorno",0.0)), format="%.2f", key=f"r_{id_int}")
                    new_status = st.selectbox("Status", ["Green","Red","Void","Pendente"], index=["Green","Red","Void","Pendente"].index(row.get("status") if row.get("status") in ["Green","Red","Void","Pendente"] else "Pendente"), key=f"s_{id_int}")
                    colA, colB = st.columns(2)
                    with colA:
                        btn_save = st.form_submit_button("💾 Salvar alterações")
                    with colB:
                        btn_delete = st.form_submit_button("🗑️ Excluir aposta")
                    if btn_save:
                        update_bet(id_int, new_grp, new_casa, new_desc, float(new_odd) if new_odd>0 else None, new_val, new_ret, new_status)
                        st.success("Aposta atualizada!")
                        st.rerun()
                    if btn_delete:
                        delete_bet(id_int)
                        st.warning("Aposta excluída!")
                        st.rerun()
        st.subheader("Tabela (visualização atual)")
        st.dataframe(df_f, use_container_width=True)
        st.subheader("📈 Gráficos e relatórios")
        fig1, ax1 = plt.subplots()
        df_f["status"].value_counts().plot(kind="pie", autopct="%1.1f%%", ax=ax1)
        st.pyplot(fig1)
        fig2, ax2 = plt.subplots()
        df_f.groupby("grupo")["lucro"].sum().sort_values(ascending=False).plot(kind="bar", ax=ax2)
        ax2.set_ylabel("Lucro (R$)")
        st.pyplot(fig2)
        fig3, ax3 = plt.subplots()
        df_f.groupby("casa")["lucro"].sum().sort_values(ascending=False).plot(kind="bar", ax=ax3)
        ax3.set_ylabel("Lucro (R$)")
        st.pyplot(fig3)
        fig4, ax4 = plt.subplots()
        df_time = df_f.sort_values(by="criado_em")
        ax4.plot(df_time["criado_em"], df_time["lucro"].cumsum(), marker="o")
        ax4.set_ylabel("Lucro acumulado (R$)")
        ax4.set_xlabel("Data")
        st.pyplot(fig4)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_f.to_excel(writer, index=False, sheet_name="RAW")
        buffer.seek(0)
        st.download_button("📥 Baixar Excel (filtrado)", data=buffer, file_name="apostas_filtradas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
