import streamlit as st
import pandas as pd
import logging
import re
from pathlib import Path
from io import BytesIO

from .meses import MESES_PT, MES_PARA_NUM

# Configuração de log detalhado
LOG_PATH = Path(__file__).resolve().parent / "reports" / "relatorio_fiscal_debug.log"
LOG_PATH.parent.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s',
    filemode='a'
)

def parse_col(serie, colname=""):
    serie = serie.replace({r"R\$": "", ".": "", ",": "."}, regex=True)
    numeric = pd.to_numeric(serie, errors="coerce").fillna(0)
    logging.debug(f"[parse_col] [{colname}] Amostra: {numeric.head(5).tolist()}")
    return numeric

def moeda_format(valor):
    """Formata valor para padrão brasileiro: R$ 12.345,67"""
    try:
        if isinstance(valor, str):
            # Remove tudo exceto dígitos e vírgula
            valor = re.sub(r'[^\d,]', '', valor)
            # Converte vírgula para ponto para processamento
            valor = valor.replace(',', '.')
        valor = float(valor)
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

def moeda_to_float(valor_texto):
    """Converte texto no formato brasileiro para float"""
    try:
        if not valor_texto:
            return 0.0
        # Remove tudo exceto dígitos e vírgula
        valor = re.sub(r'[^\d,]', '', valor_texto)
        # Converte vírgula para ponto
        valor = valor.replace(',', '.')
        return float(valor)
    except:
        return 0.0


def _saldo_inicial_acumulado(df, ano, mes_inicial):
    """Calcula créditos acumulados de ICMS e PIS/COFINS antes de ``mes_inicial``."""
    df = df.copy()
    df["Data Emissão"] = pd.to_datetime(df["Data Emissão"], format="%d/%m/%Y", errors="coerce")
    df = df[(df["Data Emissão"].dt.year == ano) & (df["Data Emissão"].dt.month < mes_inicial)]
    if df.empty:
        return 0.0, 0.0

    meses = sorted(df["Data Emissão"].dt.month.dropna().unique())
    credito_icms = 0.0
    credito_pc = 0.0
    for mes in meses:
        df_mes = df[df["Data Emissão"].dt.month == mes]

        filtro_entradas = (
            df_mes["Tipo"].eq("Entrada") &
            df_mes["Classificação"].str.contains(r"(Mercadoria para Revenda|Frete)", case=False, na=False)
        )
        df_entradas = df_mes[filtro_entradas].copy()
        filtro_saidas = df_mes["Tipo"].eq("Saída")
        df_saidas = df_mes[filtro_saidas].copy()

        total_liq_entradas = parse_col(df_entradas.get("Valor Líquido", pd.Series(dtype=str))).sum()
        total_liq_saidas = parse_col(df_saidas.get("Valor Líquido", pd.Series(dtype=str))).sum()

        total_icms_entradas = parse_col(df_entradas.get("Valor ICMS", pd.Series(dtype=str))).sum()
        total_icms_saidas = parse_col(df_saidas.get("Valor ICMS", pd.Series(dtype=str))).sum()

        credito_total_icms = credito_icms + total_icms_entradas
        saldo_icms = credito_total_icms - total_icms_saidas
        credito_icms = saldo_icms if saldo_icms > 0 else 0.0

        pis_cof_entradas = total_liq_entradas * 0.0925
        pis_cof_saidas = total_liq_saidas * 0.0925
        credito_total_pc = credito_pc + pis_cof_entradas
        saldo_pc = credito_total_pc - pis_cof_saidas
        credito_pc = saldo_pc if saldo_pc > 0 else 0.0

    return credito_icms, credito_pc

def calcular_resumo_fiscal_mes_a_mes(df, ano_sel, meses_sel, considerar_acumulo_previos=True):
    try:
        df = df.copy()
        df["Data Emissão"] = pd.to_datetime(df["Data Emissão"], format="%d/%m/%Y", errors="coerce")
        df = df[df["Data Emissão"].dt.year == ano_sel]

        if meses_sel:
            if all(isinstance(m, int) for m in meses_sel):
                meses_num = meses_sel
            else:
                meses_num = [MES_PARA_NUM.get(m, None) for m in meses_sel if m in MES_PARA_NUM]
            meses_num = [m for m in meses_num if m]
        else:
            meses_num = list(range(1, 13))

        credito_icms_acumulado = 0.0
        credito_pis_cofins_acumulado = 0.0
        if considerar_acumulo_previos and meses_num:
            mes_base = min(meses_num)
            credito_icms_acumulado, credito_pis_cofins_acumulado = _saldo_inicial_acumulado(
                df, ano_sel, mes_base
            )

        relatorio_mensal = []

        for mes in sorted(meses_num):
            df_mes = df[df["Data Emissão"].dt.month == mes]

            # Entradas: Mercadoria para Revenda OU Frete
            filtro_entradas = (
                df_mes["Tipo"].eq("Entrada") &
                df_mes["Classificação"].str.contains(r"(Mercadoria para Revenda|Frete)", case=False, na=False)
            )
            df_entradas = df_mes[filtro_entradas].copy()
            filtro_saidas = df_mes["Tipo"].eq("Saída")
            df_saidas = df_mes[filtro_saidas].copy()

            total_liq_entradas = parse_col(df_entradas.get("Valor Líquido", pd.Series(dtype=str)), "Valor Líquido Entradas").sum()
            total_liq_saidas = parse_col(df_saidas.get("Valor Líquido", pd.Series(dtype=str)), "Valor Líquido Saídas").sum()
            resultado_liq = total_liq_saidas - total_liq_entradas

            total_icms_entradas = parse_col(df_entradas.get("Valor ICMS", pd.Series(dtype=str)), "Valor ICMS Entradas").sum()
            total_icms_saidas = parse_col(df_saidas.get("Valor ICMS", pd.Series(dtype=str)), "Valor ICMS Saídas").sum()

            # Guardar o saldo acumulado do início do mês
            credito_icms_inicio = credito_icms_acumulado
            credito_total_icms = credito_icms_inicio + total_icms_entradas
            saldo_apuracao_icms = credito_total_icms - total_icms_saidas

            if saldo_apuracao_icms < 0:
                icms_a_pagar = abs(saldo_apuracao_icms)
                icms_credito_transportado = 0.0
            else:
                icms_a_pagar = 0.0
                icms_credito_transportado = saldo_apuracao_icms

            # Atualizar acumulado apenas para o próximo mês
            credito_icms_acumulado = icms_credito_transportado

            # PIS/COFINS (9,25%)
            pis_cof_entradas = total_liq_entradas * 0.0925
            pis_cof_saidas = total_liq_saidas * 0.0925

            credito_pis_cofins_inicio = credito_pis_cofins_acumulado
            credito_total_pc = credito_pis_cofins_inicio + pis_cof_entradas
            saldo_apuracao_pc = credito_total_pc - pis_cof_saidas

            if saldo_apuracao_pc < 0:
                pis_cofins_a_pagar = abs(saldo_apuracao_pc)
                pis_cofins_credito_transportado = 0.0
            else:
                pis_cofins_a_pagar = 0.0
                pis_cofins_credito_transportado = saldo_apuracao_pc

            credito_pis_cofins_acumulado = pis_cofins_credito_transportado

            relatorio_mensal.append({
                "Ano": ano_sel,
                "Mês": MESES_PT[mes],
                "Entradas (Revenda + Frete)": total_liq_entradas,
                "Saídas": total_liq_saidas,
                "Resultado Líquido": resultado_liq,
                "ICMS Entradas": total_icms_entradas,
                "ICMS Saídas": total_icms_saidas,
                "Crédito ICMS Acum. (início)": credito_icms_inicio,
                "ICMS a Pagar": icms_a_pagar,
                "Crédito ICMS Transportado": icms_credito_transportado,
                "PIS/COFINS Entradas": pis_cof_entradas,
                "PIS/COFINS Saídas": pis_cof_saidas,
                "Crédito PIS/COFINS Acum. (início)": credito_pis_cofins_inicio,
                "PIS/COFINS a Pagar": pis_cofins_a_pagar,
                "Crédito PIS/COFINS Transportado": pis_cofins_credito_transportado,
            })

        return relatorio_mensal

    except Exception as e:
        logging.error(f"Erro no cálculo fiscal: {e}")
        return []

def gerar_excel_resumo(relatorio_mensal):
    buffer = BytesIO()
    df_mensal = pd.DataFrame(relatorio_mensal)
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_mensal.to_excel(writer, index=False, sheet_name="Resumo Fiscal Mês a Mês")
    buffer.seek(0)
    return buffer

def format_brl(valor):
    """Formata número para padrão brasileiro: R$ 12.345,67"""
    if pd.isna(valor):
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def mostrar_resumo_fiscal(df, ano_sel=None, meses_sel=None):
    if df.empty or "Data Emissão" not in df.columns:
        st.warning("Nenhum dado disponível.")
        return

    st.header("Apuração Fiscal")

    # Cards de ICMS
    todos_meses = calcular_resumo_fiscal_mes_a_mes(
        df, ano_sel, list(range(1, 13))
    )
    if todos_meses:
        ultimo = todos_meses[-1]
        icms_final = ultimo['Crédito ICMS Transportado']
        cor_icms = "#1b4023" if icms_final > 0 else "#632626"
        desc_icms = "ICMS Crédito Acumulado no Último Período" if icms_final > 0 else "ICMS Saldo Devedor no Último Período"
        st.markdown(
            f"""
            <div style="border-radius:12px;background:{cor_icms};padding:18px 0 8px 0; text-align:center;font-size:1.45em;color:#fff;max-width:440px;margin-bottom:14px">
                <b>{desc_icms}:</b><br>
                <span style="font-size:1.8em;font-weight:800;">{format_brl(icms_final)}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.subheader("Relatórios disponíveis")

    # Relatório mês a mês (com filtro)
    relatorio_mensal = calcular_resumo_fiscal_mes_a_mes(df, ano_sel, meses_sel)
    if not relatorio_mensal:
        st.warning("Nenhum dado fiscal apurado para o período.")
        return

    df_mensal = pd.DataFrame(relatorio_mensal)
    st.dataframe(df_mensal.style.format({
        "Entradas (Revenda + Frete)": lambda x: format_brl(x),
        "Saídas": lambda x: format_brl(x),
        "Resultado Líquido": lambda x: format_brl(x),
        "ICMS Entradas": lambda x: format_brl(x),
        "ICMS Saídas": lambda x: format_brl(x),
        "Crédito ICMS Acum. (início)": lambda x: format_brl(x),
        "ICMS a Pagar": lambda x: format_brl(x),
        "Crédito ICMS Transportado": lambda x: format_brl(x),
        "PIS/COFINS Entradas": lambda x: format_brl(x),
        "PIS/COFINS Saídas": lambda x: format_brl(x),
        "Crédito PIS/COFINS Acum. (início)": lambda x: format_brl(x),
        "PIS/COFINS a Pagar": lambda x: format_brl(x),
        "Crédito PIS/COFINS Transportado": lambda x: format_brl(x),
    }), use_container_width=True)

    excel_buffer = gerar_excel_resumo(relatorio_mensal)
    st.download_button(
        label="📥 Baixar planilha com os cálculos mês a mês",
        data=excel_buffer,
        file_name="resumo_fiscal_mes_a_mes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _ultimo_mes_vigente(df):
    datas = pd.to_datetime(df.get("Data Emissão", pd.Series([])), format="%d/%m/%Y", errors="coerce") if df is not None else pd.Series([], dtype="datetime64[ns]")
    max_data = datas.max()
    if pd.isna(max_data):
        hoje = pd.Timestamp.today()
        return hoje.year, hoje.month
    return int(max_data.year), int(max_data.month)


def _meses_restantes_do_ano(ano, mes_inicio):
    return [(ano, m) for m in range(mes_inicio, 13)]


def _credito_acumulado_atual(df, ano, mes_vig, imposto):
    if df is None or df.empty or mes_vig <= 1:
        return 0.0
    meses_prev = list(range(1, mes_vig))
    resumo = calcular_resumo_fiscal_mes_a_mes(df, ano, meses_prev)
    if not resumo:
        return 0.0
    ultimo = resumo[-1]
    if imposto == "icms":
        return ultimo.get("Crédito ICMS Transportado", 0.0) or 0.0
    return ultimo.get("Crédito PIS/COFINS Transportado", 0.0) or 0.0


def _rollforward(credito_inicial, creditos, debitos, periodos):
    resultados = []
    credito_atual = credito_inicial
    for (ano, mes), cred, deb in zip(periodos, creditos, debitos):
        consumo = min(deb, cred + credito_atual)
        a_pagar = deb - consumo
        credito_final = max(cred + credito_atual - consumo, 0.0)
        resultados.append(
            {
                "Período": f"{ano}-{mes:02d}",
                "Ano": ano,
                "Mês": MESES_PT[mes],
                "Crédito Inicial": credito_atual,
                "Crédito do Mês": cred,
                "Débito do Mês": deb,
                "A Pagar": a_pagar,
                "Crédito Final": credito_final,
            }
        )
        credito_atual = credito_final
    return resultados


def chip(texto: str, color: str) -> str:
    classes = {
        "green": "badge badge-green",
        "red": "badge badge-red",
    }
    return f"<span class='{classes.get(color, 'badge')}'>{texto}</span>"


def derive_kpis(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "total_a_pagar": 0.0,
            "meses_com_pagamento": 0,
            "primeiro_mes_pagamento": "-",
            "valor_primeiro_mes": 0.0,
            "credito_final_dezembro": 0.0,
            "mes_maior_pagamento": "-",
            "valor_maior_pagamento": 0.0,
        }

    total_a_pagar = float(df["A Pagar"].sum())
    meses_pag = df[df["A Pagar"] > 0]
    meses_com_pagamento = int((df["A Pagar"] > 0).sum())
    if not meses_pag.empty:
        primeiro = meses_pag.iloc[0]
        primeiro_mes = f"{primeiro['Mês']}/{primeiro['Ano']}"
        valor_primeiro = float(primeiro["A Pagar"])
    else:
        primeiro_mes = "-"
        valor_primeiro = 0.0
    ultimo = df.iloc[-1]
    credito_final_dez = float(ultimo["Crédito Final"])
    idxmax = df["A Pagar"].idxmax()
    mes_maior = f"{df.loc[idxmax, 'Mês']}/{df.loc[idxmax, 'Ano']}"
    valor_maior = float(df.loc[idxmax, "A Pagar"])
    return {
        "total_a_pagar": total_a_pagar,
        "meses_com_pagamento": meses_com_pagamento,
        "primeiro_mes_pagamento": primeiro_mes,
        "valor_primeiro_mes": valor_primeiro,
        "credito_final_dezembro": credito_final_dez,
        "mes_maior_pagamento": mes_maior,
        "valor_maior_pagamento": valor_maior,
    }


def inject_css():
    st.markdown(
        """
        <style>
        .kpi-sticky { position: sticky; top: 0; z-index: 999; background: var(--background-color, #0e1117); padding: .5rem 0; }
        .badge { display:inline-block; padding:.15rem .5rem; border-radius:999px; font-size:.75rem; font-weight:600; }
        .badge-green { background:#133a20; color:#6ee7b7; border:1px solid #065f46; }
        .badge-red { background:#3a1616; color:#fca5a5; border:1px solid #7f1d1d; }
        .month-row { background:#1a2433; border-radius:8px; padding:10px; margin-bottom:6px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_bar(kpis: dict):
    inject_css()
    st.markdown("<div class='kpi-sticky'>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total a pagar (restante do ano)", format_brl(kpis["total_a_pagar"]))
    col2.metric("1º mês com pagamento", kpis["primeiro_mes_pagamento"])
    col3.metric("Meses com pagamento", kpis["meses_com_pagamento"])
    col4.metric("Crédito final (dez)", format_brl(kpis["credito_final_dezembro"]))
    st.markdown("</div>", unsafe_allow_html=True)


def render_smart_notices(kpis: dict):
    if kpis["meses_com_pagamento"] == 0:
        st.success("Crédito cobre todo o restante do ano.")
    else:
        st.info(
            f"Próximo desembolso em {kpis['primeiro_mes_pagamento']} no valor de {format_brl(kpis['valor_primeiro_mes'])}"
        )
        if kpis["valor_maior_pagamento"] > 100_000:
            st.warning(
                f"Desembolso elevado em {kpis['mes_maior_pagamento']} de {format_brl(kpis['valor_maior_pagamento'])}"
            )


def render_month_list(df: pd.DataFrame, detalhes: dict | None = None):
    for _, row in df.iterrows():
        status = "Sem pagamento" if row["A Pagar"] <= 0 else "A pagar"
        color = "green" if row["A Pagar"] <= 0 else "red"
        badge = chip(status, color)
        st.markdown(
            f"<div class='month-row'><b>{row['Período']}</b> {badge}<br>"
            f"Crédito Inicial {format_brl(row['Crédito Inicial'])} | Crédito do Mês {format_brl(row['Crédito do Mês'])} | "
            f"Débito do Mês {format_brl(row['Débito do Mês'])} | A Pagar {format_brl(row['A Pagar'])} | "
            f"Crédito Final {format_brl(row['Crédito Final'])}</div>",
            unsafe_allow_html=True,
        )
        if detalhes:
            chave = (row["Ano"], MES_PARA_NUM.get(row["Mês"], 0))
            det = detalhes.get(chave)
            if det:
                with st.expander("Detalhar"):
                    if {"cred_4"}.issubset(det.keys()):
                        col_c, col_d = st.columns(2)
                        with col_c:
                            st.markdown("*Entradas (Créditos)*")
                            st.markdown(f"Crédito 4% = {format_brl(det['cred_4'])}")
                            st.markdown(f"Crédito 7% = {format_brl(det['cred_7'])}")
                            st.markdown(f"Crédito 12% = {format_brl(det['cred_12'])}")
                            st.markdown(f"Crédito 19% = {format_brl(det['cred_19'])}")
                            st.markdown(f"**Total Créditos do mês: {format_brl(det['total_credito'])}**")
                        with col_d:
                            st.markdown("*Saídas (Débitos)*")
                            st.markdown(f"Débito 11% = {format_brl(det['deb_11'])}")
                            st.markdown(f"PROTEGE 1% = {format_brl(det['protege'])}")
                            st.markdown(f"Débito 12% = {format_brl(det['deb_12'])}")
                            st.markdown(f"Débito 19% = {format_brl(det['deb_19'])}")
                            st.markdown(f"**Total Débitos do mês: {format_brl(det['total_debito'])}**")
                        st.markdown("**Apuração do mês**")
                        st.markdown(f"Crédito Inicial: {format_brl(det['credito_inicial'])}")
                        st.markdown(f"Consumo de crédito: {format_brl(det['consumo'])}")
                        st.markdown(f"A Pagar: {format_brl(det['a_pagar'])}")
                        st.markdown(f"Crédito Final: {format_brl(det['credito_final'])}")
                    else:
                        st.markdown(f"Crédito do Mês: {format_brl(row['Crédito do Mês'])}")
                        st.markdown(f"Débito do Mês: {format_brl(row['Débito do Mês'])}")



def simulador_icms_manual(df=None, ano_sel=None, meses_sel=None):
    st.header("Simulação Manual de ICMS")
    ano_vig, mes_vig = _ultimo_mes_vigente(df if df is not None else pd.DataFrame())
    credito_inicial = _credito_acumulado_atual(df, ano_vig, mes_vig, "icms")
    st.markdown(f"Mês vigente: **{MESES_PT[mes_vig]} / {ano_vig}**")
    st.markdown(f"Crédito acumulado inicial: **{format_brl(credito_inicial)}**")
    meses = _meses_restantes_do_ano(ano_vig, mes_vig)
    valores = {}
    for ano, mes in meses:
        with st.expander(f"{MESES_PT[mes]}/{ano}", expanded=(mes == mes_vig)):
            col_e, col_s = st.columns(2)
            with col_e:
                e4 = st.number_input("Entrada 4%", min_value=0.0, key=f"icms_{ano}_{mes}_e4")
                e7 = st.number_input("Entrada 7%", min_value=0.0, key=f"icms_{ano}_{mes}_e7")
                e12 = st.number_input("Entrada 12%", min_value=0.0, key=f"icms_{ano}_{mes}_e12")
                e19 = st.number_input("Entrada 19%", min_value=0.0, key=f"icms_{ano}_{mes}_e19")
            with col_s:
                s11 = st.number_input("Saída 11%", min_value=0.0, key=f"icms_{ano}_{mes}_s11")
                s12 = st.number_input("Saída 12%", min_value=0.0, key=f"icms_{ano}_{mes}_s12")
                s19 = st.number_input("Saída 19%", min_value=0.0, key=f"icms_{ano}_{mes}_s19")
            valores[(ano, mes)] = (e4, e7, e12, e19, s11, s12, s19)

    if st.button("Simular projeção", key="btn_icms_proj"):
        detalhes = {}
        linhas = []
        credito_atual = credito_inicial
        for (ano, mes) in meses:
            e4, e7, e12, e19, s11, s12, s19 = valores.get((ano, mes), (0, 0, 0, 0, 0, 0, 0))
            c4 = e4 * 0.04
            c7 = e7 * 0.07
            c12 = e12 * 0.12
            c19 = e19 * 0.19
            total_cred = c4 + c7 + c12 + c19
            d11 = s11 * 0.11
            protege = s11 * 0.01
            d12 = s12 * 0.12
            d19 = s19 * 0.19
            total_deb = d11 + protege + d12 + d19
            consumo = min(total_deb, total_cred + credito_atual)
            a_pagar = total_deb - consumo
            credito_final = max(total_cred + credito_atual - consumo, 0.0)
            detalhes[(ano, mes)] = {
                "cred_4": c4,
                "cred_7": c7,
                "cred_12": c12,
                "cred_19": c19,
                "total_credito": total_cred,
                "deb_11": d11,
                "protege": protege,
                "deb_12": d12,
                "deb_19": d19,
                "total_debito": total_deb,
                "credito_inicial": credito_atual,
                "consumo": consumo,
                "a_pagar": a_pagar,
                "credito_final": credito_final,
            }
            linhas.append(
                {
                    "Período": f"{ano}-{mes:02d}",
                    "Ano": ano,
                    "Mês": MESES_PT[mes],
                    "Crédito Inicial": credito_atual,
                    "Crédito do Mês": total_cred,
                    "Débito do Mês": total_deb,
                    "A Pagar": a_pagar,
                    "Crédito Final": credito_final,
                }
            )
            credito_atual = credito_final
        df_res = pd.DataFrame(linhas)
        st.session_state["icms_resultados"] = detalhes
        st.session_state["icms_df"] = df_res
        st.session_state["icms_kpis"] = derive_kpis(df_res)
        st.experimental_rerun()

    if "icms_df" in st.session_state:
        df_res = st.session_state["icms_df"]
        kpis = st.session_state.get("icms_kpis", {})
        render_kpi_bar(kpis)
        render_smart_notices(kpis)
        render_month_list(df_res, st.session_state.get("icms_resultados"))


def simulador_pis_cofins_manual(df=None, ano_sel=None, meses_sel=None):
    st.header("Simulação Manual de PIS/COFINS")
    ano_vig, mes_vig = _ultimo_mes_vigente(df if df is not None else pd.DataFrame())
    credito_inicial = _credito_acumulado_atual(df, ano_vig, mes_vig, "pc")
    st.markdown(f"Mês vigente: **{MESES_PT[mes_vig]} / {ano_vig}**")
    st.markdown(f"Crédito acumulado inicial: **{format_brl(credito_inicial)}**")
    meses = _meses_restantes_do_ano(ano_vig, mes_vig)
    valores = {}
    for ano, mes in meses:
        with st.expander(f"{MESES_PT[mes]}/{ano}", expanded=(mes == mes_vig)):
            base_ent = st.number_input("Base Entradas", min_value=0.0, key=f"pc_{ano}_{mes}_be")
            base_sai = st.number_input("Base Saídas", min_value=0.0, key=f"pc_{ano}_{mes}_bs")
            valores[(ano, mes)] = (base_ent, base_sai)
    if st.button("Simular projeção", key="btn_pc_proj"):
        creditos, debitos, periodos = [], [], []
        for (ano, mes), (be, bs) in valores.items():
            creditos.append(be * 0.0925)
            debitos.append(bs * 0.0925)
            periodos.append((ano, mes))
        resultados = _rollforward(credito_inicial, creditos, debitos, periodos)
        df_res = pd.DataFrame(resultados)
        st.session_state["pc_df"] = df_res
        st.session_state["pc_kpis"] = derive_kpis(df_res)
        st.experimental_rerun()

    if "pc_df" in st.session_state:
        df_res = st.session_state["pc_df"]
        kpis = st.session_state.get("pc_kpis", {})
        render_kpi_bar(kpis)
        render_smart_notices(kpis)
        render_month_list(df_res)
