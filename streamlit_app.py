import streamlit as st
import pandas as pd
import sqlite3
import pytesseract
from PIL import Image
import re
import matplotlib.pyplot as plt
from rapidfuzz import fuzz
import io
from datetime import datetime

# -------------------------
# Configuração da página
# -------------------------
st.set_page_config(page_title="Apostas OCR (Completo)", layout="wide")
st.title("📊 Apostas OCR — App funcional")

# -------------------------
# Banco SQLite
# -------------------------
DB_PATH = "apostas.db"

DB_PATH = "apostas.db"

def init_db():
    # Abre conexão (permite uso em múltiplas threads do Streamlit)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    # Cria tabela mínima se não existir (somente id) — depois vamos garantir colunas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS apostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
    """)
    conn.commit()

    # Colunas esperadas e seus tipos
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

    # Verifica colunas que já existem
    cursor.execute("PRAGMA table_info(apostas)")
    existing = [row[1] for row in cursor.fetchall()]  # row[1] é o nome da coluna

    # Adiciona colunas que faltam (ALTER TABLE ADD COLUMN)
    for col, typ in expected.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE apostas ADD COLUMN {col} {typ}")
    conn.commit()
    return conn

def add_bet_to_db(grupo, casa, descricao, valor, retorno, status):
    # calcula lucro
    try:
        lucro = float(retorno) - float(valor)
    except:
        lucro = 0.0
    cursor = conn.cursor()
    # Insere explicitamente nas colunas que garantimos existir
    cursor.execute("""
        INSERT INTO apostas (criado_em, grupo, casa, descricao, valor, retorno, lucro, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), grupo, casa, descricao, float(valor), float(retorno), float(lucro), status))
    conn.commit()

def load_bets_df():
    return pd.read_sql("SELECT * FROM apostas ORDER BY id ASC", conn)

# -------------------------
# Utilitários OCR / parsing
# -------------------------
def parse_money_token(token: str):
    """Tenta converter token textual em float (suporta 3,00 ; 3.00 ; 1.234,56)."""
    if token is None:
        return None
    s = str(token).strip()
    s = s.replace("R$", "").replace("r$", "").replace(" ", "")
    # keep digits , .
    s = re.sub(r"[^0-9\.,\-]", "", s)
    if s == "":
        return None
    # if both . and , assume . thousand and , decimal (pt-BR)
    if "." in s and "," in s:
        s2 = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s2 = s.replace(",", ".")
    else:
        s2 = s
    # final cleanup
    s2 = re.sub(r"[^0-9\.\-]", "", s2)
    try:
        return float(s2)
    except:
        return None

def extract_money_candidates(text: str):
    """Retorna lista de números detectados no texto (prioriza tokens com R$)."""
    candidates = []
    # tokens like R$ 3,00 or R$3.00
    for m in re.findall(r"R\$\s*[0-9\.,]+", text, flags=re.I):
        val = parse_money_token(m)
        if val is not None:
            candidates.append(val)
    # numbers with decimal separators (not prefixed by R$)
    for m in re.findall(r"\b[0-9]{1,4}[.,][0-9]{1,3}\b", text):
        val = parse_money_token(m)
        if val is not None:
            candidates.append(val)
    # fallback integers (small)
    if not candidates:
        for m in re.findall(r"\b[0-9]{1,4}\b", text):
            val = parse_money_token(m)
            if val is not None:
                candidates.append(val)
    return candidates

def find_label_value(text: str, label_patterns):
    """Procura por padrões como 'valor', 'apostado', 'aposta' seguido de número."""
    for pat in label_patterns:
        regex = re.compile(rf"{pat}\s*[:\-\–]?\s*(?:R\$)?\s*([0-9\.,]+)", flags=re.I)
        m = regex.search(text)
        if m:
            val = parse_money_token(m.group(1))
            if val is not None:
                return val
    return None

def detect_casa(text: str):
    """Detecta casa de aposta por palavras-chave simples."""
    t = text.lower()
    if "bet365" in t or "bet 365" in t:
        return "Bet365"
    if "betano" in t:
        return "Betano"
    if "pinnacle" in t:
        return "Pinnacle"
    if "blaze" in t:
        return "Blaze"
    # outras heurísticas: procurar 'Casa:' ou 'Casa de Aposta'
    m = re.search(r"casa[:\-\s]*([A-Za-z0-9]+)", text, flags=re.I)
    if m:
        return m.group(1).strip()
    return "Desconhecida"

def detectar_status(text: str):
    """Detecta Green/Red/Void/Pendente com fuzzy e palavras-chave.
       Prioriza Green para evitar falsos negativos."""
    t = (text or "").lower()
    green_words = ["green", "ganho", "ganhou", "vencida", "gana", "venceu", "retorno obtido"]
    red_words = ["red", "perdida", "perdeu", "loss", "perdido", "perda"]
    void_words = ["void", "anulada", "anulado", "cancelada", "reembolso", "reembolsada"]

    # direct substring checks first
    if any(w in t for w in green_words):
        return "Green"
    if any(w in t for w in red_words):
        # but if green also appears, prefer green
        if any(w in t for w in green_words):
            return "Green"
        return "Red"
    if any(w in t for w in void_words):
        return "Void"

    # fuzzy checks
    if fuzz.partial_ratio(t, "green") > 60:
        return "Green"
    if fuzz.partial_ratio(t, "void") > 70:
        return "Void"
    if fuzz.partial_ratio(t, "red") > 80:
        return "Red"

    # fallback
    return "Pendente"

def infer_valor_retorno_from_text(text: str, status: str):
    """Heurística que tenta inferir valor e retorno do texto OCR."""
    debug = {}
    # Try by labels first
    valor_labels = ["valor apostado", "valor", "apostado", "aposta", "stake", "apostou"]
    retorno_labels = ["retorno obtido", "retorno", "retorno:", "retorno obtido:", "retorno recebido", "retorno:"]
    v_label = find_label_value(text, valor_labels)
    r_label = find_label_value(text, retorno_labels)
    debug["v_label"] = v_label
    debug["r_label"] = r_label

    candidates = extract_money_candidates(text)
    debug["candidates"] = candidates.copy()

    valor = v_label
    retorno = r_label

    if valor is not None and retorno is not None:
        return valor, retorno, debug

    if len(candidates) >= 2:
        s = sorted(candidates)
        # smaller usually valor, larger retorno
        valor = valor or s[0]
        retorno = retorno or s[-1]
        return valor, retorno, debug

    if len(candidates) == 1:
        only = candidates[0]
        if status == "Red":
            return only, 0.0, debug
        if status == "Void":
            return only, only, debug
        if status == "Green":
            # assume single candidate is retorno (common in many prints)
            return 0.0, only, debug
        # pending: assume it's valor
        return only, 0.0, debug

    # nothing found
    return 0.0, 0.0, debug

# -------------------------
# Função principal de processamento
# -------------------------
def process_image_file(uploaded_file):
    """Roda OCR, extrai casa, status, valores e descrição."""
    try:
        img = Image.open(uploaded_file)
    except Exception as e:
        return {"error": f"Erro ao abrir imagem: {e}"}

    # OCR preferindo português
    try:
        text = pytesseract.image_to_string(img, lang="por")
    except Exception:
        text = pytesseract.image_to_string(img)

    # normalize whitespace
    text_clean = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

    status = detectar_status(text_clean)
    casa = detect_casa(text_clean)
    valor_guess, retorno_guess, debug = infer_valor_retorno_from_text(text_clean, status)

    # description: try to pick the most informative lines (event/title)
    lines = [line for line in text_clean.splitlines() if line.strip()]
    desc = ""
    if lines:
        # pick a middle line or a long line
        long_lines = sorted(lines, key=lambda x: len(x), reverse=True)
        desc = long_lines[0]
    else:
        desc = text_clean[:120]

    result = {
        "texto": text_clean,
        "status": status,
        "casa": casa,
        "descricao": desc,
        "valor_guess": float(valor_guess or 0.0),
        "retorno_guess": float(retorno_guess or 0.0),
        "debug": debug
    }
    return result

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
            status = st.selectbox("Status", ["Green", "Red", "Void", "Pendente", "Indefinido"], index=["Green","Red","Void","Pendente","Indefinido"].index(result["status"] if result["status"] in ["Green","Red","Void","Pendente","Indefinido"] else "Pendente"))
            submit = st.form_submit_button("Salvar aposta")
            if submit:
                add_bet_to_db(grupo, casa, descricao, valor, retorno, status)
                st.success("✅ Aposta salva!")

# -------------------------
# Mostrar e filtrar histórico
# -------------------------
st.header("📋 Histórico e Dashboard")

df = load_bets_df()
if df.empty:
    st.info("Nenhuma aposta registrada ainda. Faça upload de um print para começar.")
else:
    # filtros
    cols = st.columns([2, 2, 2, 4])
    with cols[0]:
        filtro_grupo = st.selectbox("Filtrar por Grupo", options=["Todos"] + sorted(df["grupo"].unique().tolist()))
    with cols[1]:
        filtro_casa = st.selectbox("Filtrar por Casa", options=["Todos"] + sorted(df["casa"].unique().tolist()))
    with cols[2]:
        filtro_status = st.selectbox("Filtrar por Status", options=["Todos"] + sorted(df["status"].unique().tolist()))
    # apply filters
    df_display = df.copy()
    if filtro_grupo != "Todos":
        df_display = df_display[df_display["grupo"] == filtro_grupo]
    if filtro_casa != "Todos":
        df_display = df_display[df_display["casa"] == filtro_casa]
    if filtro_status != "Todos":
        df_display = df_display[df_display["status"] == filtro_status]

    st.subheader("Tabela de apostas")
    st.dataframe(df_display, use_container_width=True)

    # ensure numeric types
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["retorno"] = pd.to_numeric(df["retorno"], errors="coerce").fillna(0.0)
    df["lucro"] = df["retorno"] - df["valor"]

    # aggregate metrics
    total_lucro = df["lucro"].sum()
    total_apostas = len(df)
    lucro_por_status = df.groupby("status")["lucro"].sum().reindex(["Green","Red","Void","Pendente","Indefinido"]).fillna(0)

    st.subheader("📊 Métricas rápidas")
    m1, m2, m3 = st.columns(3)
    m1.metric("Apostas registradas", total_apostas)
    m2.metric("Lucro total (R$)", f"{total_lucro:.2f}")
    # percentual de green (considerando ganhos positivos)
    greens = df[df["status"] == "Green"]
    perc_green = (len(greens) / total_apostas * 100) if total_apostas>0 else 0
    m3.metric("% Greens", f"{perc_green:.1f}%")

    # -------------------------
    # Gráficos visuais
    # -------------------------
    st.subheader("Gráficos")

    # 1) Pizza: distribuição por status (counts)
    fig1, ax1 = plt.subplots(figsize=(4,4))
    status_counts = df["status"].value_counts()
    ax1.pie(status_counts, labels=status_counts.index, autopct="%1.1f%%", textprops={'fontsize':9})
    ax1.set_title("Distribuição por Status")
    st.pyplot(fig1)

    # 2) Barra: lucro por grupo (money)
    if not df["grupo"].isnull().all():
        lucro_grupo = df.groupby("grupo")["lucro"].sum().sort_values(ascending=False)
        fig2, ax2 = plt.subplots(figsize=(6,4))
        lucro_grupo.plot(kind="bar", ax=ax2)
        ax2.set_ylabel("Lucro (R$)")
        ax2.set_title("Lucro por Grupo")
        st.pyplot(fig2)

    # 3) Linha: lucro acumulado (order by id/time)
    df_sorted = df.sort_values(by="id")
    fig3, ax3 = plt.subplots(figsize=(6,3))
    ax3.plot(df_sorted["id"].astype(int), df_sorted["lucro"].cumsum(), marker="o")
    ax3.set_xlabel("Registro (id)")
    ax3.set_ylabel("Lucro acumulado (R$)")
    ax3.set_title("Evolução do Lucro")
    st.pyplot(fig3)

    # 4) Barra horizontal: lucro por casa
    lucro_casa = df.groupby("casa")["lucro"].sum().sort_values()
    if len(lucro_casa) > 0:
        fig4, ax4 = plt.subplots(figsize=(6, max(2, len(lucro_casa)*0.6)))
        lucro_casa.plot(kind="barh", ax=ax4)
        ax4.set_xlabel("Lucro (R$)")
        ax4.set_title("Lucro por Casa de Aposta")
        st.pyplot(fig4)

    # -------------------------
    # Exportar dados
    # -------------------------
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="RAW")
    buffer.seek(0)
    st.download_button("📥 Baixar Excel (RAW)", data=buffer, file_name="apostas_raw.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
