# streamlit_app.py (corrigido: edição + exclusão sem conflito)
import streamlit as st
import sqlite3
import pandas as pd
import pytesseract
from PIL import Image
import re
from datetime import datetime
import matplotlib.pyplot as plt

# ---------------------
# Config
# ---------------------
st.set_page_config(page_title="Gestor de Apostas (OCR + Edição)", layout="wide")
st.title("📊 Gestor de Apostas — OCR, Histórico e Edição (mesma tela)")

DB_FILE = "apostas.db"

# ---------------------
# Banco de dados
# ---------------------
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
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

def add_bet(grupo, casa, descricao, valor, retorno, odd, status):
    lucro = retorno - valor if status == "Green" else (-valor if status == "Red" else 0.0)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, odd, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, float(valor), float(retorno), float(odd), float(lucro), status))
    conn.commit()
    conn.close()

def load_bets_df():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM apostas ORDER BY id DESC", conn)
    conn.close()
    return df

def update_bet(bet_id, grupo, casa, descricao, valor, retorno, odd, status):
    lucro = retorno - valor if status == "Green" else (-valor if status == "Red" else 0.0)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        UPDATE apostas
        SET grupo=?, casa=?, descricao=?, valor=?, retorno=?, odd=?, lucro=?, status=?
        WHERE id=?
    """, (grupo, casa, descricao, float(valor), float(retorno), float(odd), float(lucro), status, bet_id))
    conn.commit()
    conn.close()

def delete_bet(bet_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM apostas WHERE id=?", (bet_id,))
    conn.commit()
    conn.close()

# ---------------------
# Utilitários OCR + parsing
# ---------------------
def parse_brazil_currency(s: str):
    if s is None:
        return None
    s = str(s).strip().replace("R$", "").replace("r$", "").strip()
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

def classify_status_from_text(text: str):
    t = (text or "").lower()
    if any(k in t for k in ["retorno obtido", "retorno recebido", "ganhou", "ganho", "venc"]):
        return "Green"
    if any(k in t for k in ["anulado", "anulada", "cancelado", "cancelada", "void"]):
        return "Void"
    if any(k in t for k in ["perdeu", "perdida", "perdido", "lost", "red"]):
        return "Red"
    return "Indefinido"

def extract_info_from_ocr(text: str):
    t = (text or "")
    # debug: texto cru
    st.write("🔍 Texto OCR bruto (debug):")
    st.code(t)

    status = classify_status_from_text(t)

    valor = None
    retorno = None
    odd = None

    m_val = re.search(r"(?:aposta|valor)\s*[:\-]?\s*R?\$?\s*([\d\.,]+)", t, flags=re.I)
    m_ret = re.search(r"(?:retorno(?:\s+total|\s+obtido)?)\s*[:\-]?\s*R?\$?\s*([\d\.,]+)", t, flags=re.I)
    m_ret_after = re.search(r"R\$\s*([\d\.,]+)\s*(?:retorno|retorno\s+total|retorno\s+obtido)", t, flags=re.I)

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
        st.write("🔎 Tokens monetários detectados (raw, valor):", tokens)

    if retorno is None:
        vals = [v for (_, v) in tokens]
        vals_sorted = sorted(vals)
        if len(vals_sorted) >= 2:
            valor = valor or vals_sorted[0]
            retorno = retorno or vals_sorted[-1]
        elif len(vals_sorted) == 1:
            only = vals_sorted[0]
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

    valor = float(valor or 0.0)
    retorno = float(retorno or 0.0)
    odd = float(odd or 1.0)

    st.write(f"✅ Extraído (heurística): valor=R${valor:.2f}, retorno=R${retorno:.2f}, odd={odd:.2f}, status={status}")
    return valor, retorno, odd, status

# ---------------------
# Inicializa DB
# ---------------------
init_db()

# ---------------------
# Layout
# ---------------------
col_left, col_right = st.columns([1, 1.35])

with col_left:
    st.header("➕ Nova aposta (OCR ou manual)")
    uploaded = st.file_uploader("Envie o print da aposta (opcional)", type=["png", "jpg", "jpeg"])
    pre_val, pre_ret, pre_odd, pre_status = 0.0, 0.0, 1.0, "Indefinido"
    ocr_text = ""

    if uploaded:
        img = Image.open(uploaded)
        st.image(img, caption="Imagem carregada", use_container_width=True)
        try:
            ocr_text = pytesseract.image_to_string(img, lang="por")
        except Exception:
            ocr_text = pytesseract.image_to_string(img)
        pre_val, pre_ret, pre_odd, pre_status = extract_info_from_ocr(ocr_text)

    with st.form("form_new"):
        st.subheader("Conferir / Editar antes de salvar")
        grupo = st.text_input("Grupo", value="Grupo 1")
        casa = st.text_input("Casa", value="")
        descricao = st.text_area("Descrição (OCR)", value=ocr_text if ocr_text else "")
        valor = st.number_input("Valor apostado (R$)", min_value=0.0, value=float(pre_val), step=0.01, format="%.2f")
        retorno = st.number_input("Retorno (R$)", min_value=0.0, value=float(pre_ret), step=0.01, format="%.2f")
        odd = st.number_input("Odd", min_value=1.0, value=float(pre_odd), step=0.01, format="%.2f")
        status = st.selectbox("Status", ["Green", "Red", "Void", "Indefinido"], index=["Green","Red","Void","Indefinido"].index(pre_status if pre_status in ["Green","Red","Void"] else "Indefinido"))
        saved = st.form_submit_button("💾 Salvar aposta")

        if saved:
            try:
                add_bet(grupo, casa, descricao, valor, retorno, odd, status)
                st.success("Aposta salva com sucesso!")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

with col_right:
    st.header("📋 Histórico & Gráficos")
    df = load_bets_df()
    if df.empty:
        st.info("Nenhuma aposta registrada ainda.")
    else:
        st.subheader("Tabela (últimas lançadas)")
        st.dataframe(df, use_container_width=True)

        total_investido = df["valor"].sum()
        total_retorno = df["retorno"].sum()
        total_lucro = df["lucro"].sum()
        colA, colB, colC = st.columns(3)
        colA.metric("Total investido (R$)", f"{total_investido:,.2f}")
        colB.metric("Total retorno (R$)", f"{total_retorno:,.2f}")
        colC.metric("Lucro total (R$)", f"{total_lucro:,.2f}")

        st.markdown("---")
        st.subheader("Gráficos")
        g1, g2 = st.columns(2)
        with g1:
            st.write("Lucro por Status")
            fig1, ax1 = plt.subplots()
            df.groupby("status")["lucro"].sum().plot(kind="bar", ax=ax1, color=["green","red","gray"])
            ax1.set_ylabel("Lucro (R$)")
            st.pyplot(fig1)
        with g2:
            st.write("Lucro por Grupo")
            fig2, ax2 = plt.subplots()
            if df["grupo"].notna().any():
                df.groupby("grupo")["lucro"].sum().plot(kind="bar", ax=ax2)
            st.pyplot(fig2)

# ---------------------
# EDIÇÃO (mesma tela, abaixo do histórico)
# ---------------------
st.markdown("---")
st.header("✏️ Editar aposta existente")

df_all = load_bets_df()
if df_all.empty:
    st.info("Sem apostas para editar.")
else:
    df_all["label"] = df_all.apply(lambda r: f"ID {int(r['id'])} | {r['grupo']} | {r['casa']} | R$ {r['valor']:.2f} | {r['status']}", axis=1)
    options = df_all["label"].tolist()
    choice = st.selectbox("Selecione a aposta para editar", options)

    selected_id_match = re.search(r"ID\s+(\d+)", choice)
    if selected_id_match:
        selected_id = int(selected_id_match.group(1))
        selected_row = df_all[df_all["id"] == selected_id].iloc[0]

        st.write("Dados atuais da aposta selecionada:")
        st.write(selected_row)

        # Form de edição — só o botão "Atualizar" está dentro do form
        with st.form(f"form_edit_{selected_id}"):
            e_grupo = st.text_input("Grupo", value=selected_row["grupo"])
            e_casa = st.text_input("Casa", value=selected_row["casa"])
            e_descricao = st.text_area("Descrição", value=selected_row["descricao"])
            e_valor = st.number_input("Valor (R$)", min_value=0.0, value=float(selected_row["valor"]), step=0.01, format="%.2f")
            e_retorno = st.number_input("Retorno (R$)", min_value=0.0, value=float(selected_row["retorno"]), step=0.01, format="%.2f")
            e_odd = st.number_input("Odd", min_value=1.0, value=float(selected_row["odd"] if selected_row["odd"] is not None else 1.0), step=0.01, format="%.2f")
            e_status = st.selectbox("Status", ["Green","Red","Void","Indefinido"], index=["Green","Red","Void","Indefinido"].index(selected_row["status"] if selected_row["status"] in ["Green","Red","Void"] else "Indefinido"))
            btn_update = st.form_submit_button("💾 Salvar alterações")

        # Botão de deletar separado (fora do form) — evita conflito com form submit
        if st.button("🗑️ Excluir aposta", key=f"del_{selected_id}"):
            try:
                delete_bet(selected_id)
                st.success("Aposta excluída.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Erro ao excluir: {e}")

        # Processa a atualização (somente quando o form é submetido)
        if btn_update:
            try:
                update_bet(selected_id, e_grupo, e_casa, e_descricao, e_valor, e_retorno, e_odd, e_status)
                st.success("Aposta atualizada!")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar: {e}")
    else:
        st.error("Não foi possível identificar o ID selecionado. Recarregue a página.")

