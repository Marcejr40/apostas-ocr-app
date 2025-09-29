import re
import io
from datetime import datetime

import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
from rapidfuzz import fuzz

# ---------- Config ----------
st.set_page_config(page_title="Apostas OCR (Melhorado)", layout="wide")
st.title("📊 OCR de Apostas — versão melhorada")

# ---------- Inicializa sessão ----------
if "bets" not in st.session_state:
    st.session_state["bets"] = pd.DataFrame(
        columns=["Inserido em", "Grupo", "Casa", "Descrição", "Valor", "Retorno", "Lucro", "Status", "OCR_debug"]
    )

# ---------- Utilitários ----------
def parse_money_token(token: str):
    """Converte token como '1.234,56' ou '1234.56' ou '3,00' para float. Retorna None se falhar."""
    if token is None:
        return None
    s = str(token).strip()
    # remover espaços e símbolos extras
    s = s.replace("R$", "").replace("r$", "").replace("RS", "").replace("rs", "").strip()
    # manter apenas dígitos, pontos e vírgulas
    s = re.sub(r"[^0-9\.,\-]", "", s)
    if s == "":
        return None
    # se tiver '.' e ',' -> assume . milhar , decimal (pt-BR)
    if "." in s and "," in s:
        s2 = s.replace(".", "").replace(",", ".")
    # se tiver só ',' assume decimal pt-BR
    elif "," in s and "." not in s:
        s2 = s.replace(",", ".")
    # se tiver só '.' -> ambíguo, mas assume decimal se duas casas no final
    elif "." in s and "," not in s:
        parts = s.split(".")
        if len(parts[-1]) == 2:
            s2 = s  # assume decimal
        else:
            # caso "100" lido como "100", mantemos
            s2 = s
    else:
        s2 = s
    # remover múltiplos pontos residuais
    s2 = re.sub(r"[^0-9\.\-]", "", s2)
    try:
        return float(s2)
    except:
        return None

def find_money_by_label(text: str, label_patterns):
    """Procura padrões 'label ... R$ 3,00' e devolve primeira ocorrência convertida."""
    for pat in label_patterns:
        # procura algo como 'label ... R$ 3,00' ou 'label: 3,00'
        regex = re.compile(rf"{pat}\s*[:\-\–]?\s*(?:R\$)?\s*([0-9\.,]+)", flags=re.I)
        m = regex.search(text)
        if m:
            val = parse_money_token(m.group(1))
            if val is not None:
                return val
    return None

def extract_all_money_candidates(text: str):
    """Retorna lista de floats detectados no texto (priorizando tokens com R$)"""
    candidates = []
    # tokens com R$
    for m in re.findall(r"R\$\s*[0-9\.,]+", text, flags=re.I):
        num = parse_money_token(m)
        if num is not None:
            candidates.append(num)
    # tokens sem R$, mas padrão numérico com vírgula/ponto
    for m in re.findall(r"(?<!R\$)\b[0-9]{1,4}[.,][0-9]{1,3}\b", text):
        num = parse_money_token(m)
        if num is not None:
            candidates.append(num)
    # inteiros soltos (apenas se não temos outros candidatos)
    if not candidates:
        for m in re.findall(r"\b[0-9]{1,4}\b", text):
            num = parse_money_token(m)
            if num is not None:
                candidates.append(num)
    return candidates

def detectar_status(text: str):
    """Detecta status com fuzzy matching e listas de palavra-chave.
       Prioriza Green para evitar confusões."""
    t = (text or "").lower()

    # listas
    green_words = ["green", "ganho", "ganhou", "vencida", "vencedor", "winning", "won"]
    red_words = ["red", "perdida", "perdeu", "loss", "perdido", "lost"]
    void_words = ["void", "anulada", "cancelada", "anulado", "reembolso", "refund"]

    # prioridade: se qualquer substring clara de green aparece -> Green
    if any(w in t for w in green_words):
        return "Green"

    # fuzzy check stronger for green (catch ocr erros)
    if fuzz.partial_ratio(t, "green") > 65:
        return "Green"

    # fuzzy for red with higher threshold
    if fuzz.partial_ratio(t, "red") > 80 or any(w in t for w in red_words):
        return "Red"

    # void
    if fuzz.partial_ratio(t, "void") > 70 or any(w in t for w in void_words):
        return "Void"

    # fallback: if appears both green-like and red-like, prefer green
    green_score = max(fuzz.partial_ratio(t, g) for g in green_words)
    red_score = max(fuzz.partial_ratio(t, r) for r in red_words)
    if green_score >= red_score and green_score > 50:
        return "Green"
    if red_score > green_score and red_score > 70:
        return "Red"

    return "Pendente"

def infer_valor_retorno(text: str, auto_status: str):
    """Heurística para decidir Valor e Retorno a partir do texto extraído.
       Retorna (valor, retorno, debug_dict)."""
    debug = {"candidates": [], "from_label_valor": None, "from_label_retorno": None}

    # labels comuns em PT
    valor_labels = ["valor apostado", "valor", "aposta", "apostado", "stake", "apostou"]
    retorno_labels = ["retorno obtido", "retorno", "retorno:", "retorno obtido:", "retorno recebido"]

    # tenta encontrar por labels
    v = find_money_by_label(text, valor_labels)
    r = find_money_by_label(text, retorno_labels)
    debug["from_label_valor"] = v
    debug["from_label_retorno"] = r

    # pegar todos candidatos
    candidates = extract_all_money_candidates(text)
    debug["candidates"] = candidates.copy()

    # lógica para decidir
    valor = v
    retorno = r

    if valor is not None and retorno is not None:
        return valor, retorno, debug

    # se encontramos >=2 candidatos, presumimos menor=valor, maior=retorno
    if len(candidates) >= 2:
        sorted_c = sorted(candidates)
        # pequenas proteções: se o maior é muito maior e status Green, keep
        valor = valor or sorted_c[0]
        retorno = retorno or sorted_c[-1]
        return valor, retorno, debug

    # se há exatamente 1 candidato:
    if len(candidates) == 1:
        cand = candidates[0]
        # heurística: se status é Red -> retorno = 0 e valor = cand (aposta perdida)
        if auto_status == "Red":
            return cand, 0.0, debug
        # se Void -> retorno = cand (valor reembolsado)
        if auto_status == "Void":
            return cand, cand, debug
        # se Green -> é provável que seja retorno (ex: "Retorno obtido R$30,00")
        # mas preferimos assumir candidato = retorno, e valor ficará 0 para você ajustar
        if auto_status == "Green":
            return 0.0, cand, debug
        # se Pendente -> colocar cand como valor (mais seguro) e retorno 0
        return cand, 0.0, debug

    # se nenhum candidato detectado: return zeros
    return 0.0, 0.0, debug

# ---------- Interface ----------
st.markdown("Envie um print e o app tentará extrair **Status**, **Valor** e **Retorno**. Revise os campos antes de salvar.")

uploaded_file = st.file_uploader("Enviar print (PNG/JPG)", type=["png", "jpg", "jpeg"])
if uploaded_file:
    st.image(uploaded_file, caption="Print enviado", use_container_width=True)
    # Executa OCR
    try:
        img = Image.open(uploaded_file)
        try:
            extracted_text = pytesseract.image_to_string(img, lang="por")
        except Exception:
            extracted_text = pytesseract.image_to_string(img)
    except Exception as e:
        st.error(f"Erro ao abrir imagem: {e}")
        extracted_text = ""

    st.subheader("Texto extraído (revise):")
    st.text_area("", extracted_text, height=180)

    # detectar status e valores
    auto_status = detectar_status(extracted_text)
    valor_guess, retorno_guess, debug = infer_valor_retorno(extracted_text, auto_status)

    # Mostrar debug resumido (expansível)
    with st.expander("Mostrar dados detectados / debug"):
        st.write("Status detectado:", auto_status)
        st.write("Candidatos monetários detectados:", debug["candidates"])
        st.write("Valor detectado por label:", debug["from_label_valor"])
        st.write("Retorno detectado por label:", debug["from_label_retorno"])
        st.write("Decisão heurística: valor_guess, retorno_guess", valor_guess, retorno_guess)

    # Formulário pré-preenchido (edite antes de salvar)
    st.subheader("Preencha / confirme os dados antes de salvar")
    with st.form("salvar_aposta"):
        grupo = st.text_input("Grupo", value="Manual")
        casa = st.text_input("Casa", value="")
        descricao = st.text_area("Descrição", value=(extracted_text or "")[:300])
        valor = st.number_input("Valor apostado (R$)", min_value=0.0, value=float(valor_guess or 0.0), format="%.2f", step=0.5)
        retorno = st.number_input("Retorno (R$)", min_value=0.0, value=float(retorno_guess or 0.0), format="%.2f", step=0.5)
        status = st.selectbox("Status", ["Green", "Red", "Void", "Pendente"], index=["Green","Red","Void","Pendente"].index(auto_status))
        btn = st.form_submit_button("Salvar aposta")

        if btn:
            lucro = float(retorno) - float(valor)
            nova = {
                "Inserido em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Grupo": grupo,
                "Casa": casa,
                "Descrição": descricao,
                "Valor": float(valor),
                "Retorno": float(retorno),
                "Lucro": lucro,
                "Status": status,
                "OCR_debug": str(debug)
            }
            st.session_state["bets"] = pd.concat([st.session_state["bets"], pd.DataFrame([nova])], ignore_index=True)
            st.success(f"Aposta salva — Lucro = {lucro:.2f} R$")

# ---------- Mostrar histórico e resumo ----------
st.header("📑 Histórico de Apostas")
df = st.session_state["bets"]
st.dataframe(df, use_container_width=True)

if not df.empty:
    df["Lucro"] = df["Retorno"].astype(float) - df["Valor"].astype(float)
    total_reais = df["Lucro"].sum()
    avg_valor = df["Valor"].replace(0, pd.NA).dropna().mean() if not df["Valor"].replace(0, pd.NA).dropna().empty else 0
    total_unidades = total_reais / avg_valor if avg_valor and avg_valor != 0 else 0

    st.subheader("📊 Resumo rápido")
    c1, c2, c3 = st.columns(3)
    c1.metric("Lucro total (R$)", f"{total_reais:.2f}")
    c2.metric("Lucro total (unidades)", f"{total_unidades:.2f}")
    c3.metric("Apostas registradas", len(df))

    # gráficos finais (simples)
    st.subheader("📈 Gráficos")
    try:
        lucro_por_grupo = df.groupby("Grupo")["Lucro"].sum()
        st.bar_chart(lucro_por_grupo)

        st.line_chart(df["Lucro"].cumsum())
    except Exception as e:
        st.error("Erro ao gerar gráficos: " + str(e))

    # download Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="RAW")
    buffer.seek(0)
    st.download_button("📥 Baixar Excel (RAW)", data=buffer, file_name="apostas_raw.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
