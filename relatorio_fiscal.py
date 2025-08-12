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

        if meses_sel and "Todos os meses" not in meses_sel:
            meses_num = [MES_PARA_NUM.get(m, None) for m in meses_sel if m in MES_PARA_NUM]
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
        df, ano_sel, [MESES_PT[m] for m in range(1, 13)]
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

def format_currency_input(value):
    """Formata valor para exibição com máscara de moeda"""
    if value == 0:
        return ""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def simulador_icms_manual(df=None, ano_sel=None, meses_sel=None):
    st.header("Simulação Manual de Créditos e Débitos de ICMS")

    # Inicializar valores no session_state se não existirem
    if 'entrada_4_text' not in st.session_state:
        st.session_state.entrada_4_text = ""
    if 'entrada_7_text' not in st.session_state:
        st.session_state.entrada_7_text = ""
    if 'entrada_12_text' not in st.session_state:
        st.session_state.entrada_12_text = ""
    if 'entrada_19_text' not in st.session_state:
        st.session_state.entrada_19_text = ""
    if 'saida_12_text' not in st.session_state:
        st.session_state.saida_12_text = ""
    if 'saida_11_text' not in st.session_state:
        st.session_state.saida_11_text = ""
    if 'saida_19_text' not in st.session_state:
        st.session_state.saida_19_text = ""
    if 'simulacao_executada' not in st.session_state:
        st.session_state.simulacao_executada = False

    # Puxar crédito acumulado do último mês, se DataFrame for fornecido
    credito_acumulado = 0.0
    if df is not None and ano_sel is not None:
        if meses_sel:
            meses_param = meses_sel
        else:
            meses_param = [MESES_PT[m] for m in range(1, 13)]
        
        todos_meses = calcular_resumo_fiscal_mes_a_mes(df, ano_sel, meses_param)
        if todos_meses:
            credito_acumulado = todos_meses[-1].get('Crédito ICMS Transportado', 0.0)

    # Converter valores de texto para float
    entrada_4 = moeda_to_float(st.session_state.entrada_4_text)
    entrada_7 = moeda_to_float(st.session_state.entrada_7_text)
    entrada_12 = moeda_to_float(st.session_state.entrada_12_text)
    entrada_19 = moeda_to_float(st.session_state.entrada_19_text)
    saida_12 = moeda_to_float(st.session_state.saida_12_text)
    saida_11 = moeda_to_float(st.session_state.saida_11_text)
    saida_19 = moeda_to_float(st.session_state.saida_19_text)

    # 1. CARDS DE INPUTS LADO A LADO
    col_entradas, col_saidas = st.columns(2, gap="large")

    with col_entradas:
        st.markdown(
            """
            <div style="
                background: #1a2433;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #2c3e50;
            ">
                <h3 style="color: white; margin: 0 0 16px 0; font-size: 1.1em; font-weight: bold;">
                    Entradas — Simulação de Créditos de ICMS
                </h3>
            """,
            unsafe_allow_html=True
        )
        
        # Campo 4%
        st.session_state.entrada_4_text = st.text_input(
            "4%", 
            value=st.session_state.entrada_4_text,
            key="input_entrada_4_text",
            placeholder="Ex: 10000,00"
        )
        if st.session_state.entrada_4_text:
            st.markdown(f"<div style='color: #27ae60; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💰 {moeda_format(st.session_state.entrada_4_text)}</div>", unsafe_allow_html=True)
        
        # Campo 7%
        st.session_state.entrada_7_text = st.text_input(
            "7%", 
            value=st.session_state.entrada_7_text,
            key="input_entrada_7_text",
            placeholder="Ex: 5000,50"
        )
        if st.session_state.entrada_7_text:
            st.markdown(f"<div style='color: #27ae60; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💰 {moeda_format(st.session_state.entrada_7_text)}</div>", unsafe_allow_html=True)
        
        # Campo 12%
        st.session_state.entrada_12_text = st.text_input(
            "12%", 
            value=st.session_state.entrada_12_text,
            key="input_entrada_12_text",
            placeholder="Ex: 25000,75"
        )
        if st.session_state.entrada_12_text:
            st.markdown(f"<div style='color: #27ae60; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💰 {moeda_format(st.session_state.entrada_12_text)}</div>", unsafe_allow_html=True)
        
        # Campo 19%
        st.session_state.entrada_19_text = st.text_input(
            "19%", 
            value=st.session_state.entrada_19_text,
            key="input_entrada_19_text",
            placeholder="Ex: 15000,00"
        )
        if st.session_state.entrada_19_text:
            st.markdown(f"<div style='color: #27ae60; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💰 {moeda_format(st.session_state.entrada_19_text)}</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    with col_saidas:
        st.markdown(
            """
            <div style="
                background: #1a2433;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #2c3e50;
            ">
                <h3 style="color: white; margin: 0 0 16px 0; font-size: 1.1em; font-weight: bold;">
                    Saídas — Simulação de Débitos de ICMS
                </h3>
            """,
            unsafe_allow_html=True
        )
        
        # Campo 12%
        st.session_state.saida_12_text = st.text_input(
            "12%", 
            value=st.session_state.saida_12_text,
            key="input_saida_12_text",
            placeholder="Ex: 30000,00"
        )
        if st.session_state.saida_12_text:
            st.markdown(f"<div style='color: #e74c3c; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💸 {moeda_format(st.session_state.saida_12_text)}</div>", unsafe_allow_html=True)
        
        # Campo 11% PROTEGE
        st.session_state.saida_11_text = st.text_input(
            "11% PROTEGE", 
            value=st.session_state.saida_11_text,
            key="input_saida_11_text",
            placeholder="Ex: 8000,25"
        )
        if st.session_state.saida_11_text:
            st.markdown(f"<div style='color: #e74c3c; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💸 {moeda_format(st.session_state.saida_11_text)}</div>", unsafe_allow_html=True)
        
        # Campo 19%
        st.session_state.saida_19_text = st.text_input(
            "19%", 
            value=st.session_state.saida_19_text,
            key="input_saida_19_text",
            placeholder="Ex: 12000,80"
        )
        if st.session_state.saida_19_text:
            st.markdown(f"<div style='color: #e74c3c; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💸 {moeda_format(st.session_state.saida_19_text)}</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    # 2. BOTÃO DE SIMULAÇÃO CENTRALIZADO E PROFISSIONAL
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Verificar se há pelo menos um valor preenchido
    tem_valores = any([
        st.session_state.entrada_4_text, st.session_state.entrada_7_text,
        st.session_state.entrada_12_text, st.session_state.entrada_19_text,
        st.session_state.saida_12_text, st.session_state.saida_11_text,
        st.session_state.saida_19_text
    ])
    
    # Container centralizado para o botão
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Botão com estilo profissional adaptado à estética do script
        if tem_valores:
            botao_html = """
            <div style="text-align: center; margin: 20px 0;">
                <style>
                    .btn-simular {
                        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                        border: 2px solid #1a2433;
                        border-radius: 12px;
                        color: white;
                        padding: 16px 40px;
                        font-size: 1.1em;
                        font-weight: bold;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        text-transform: uppercase;
                        letter-spacing: 1px;
                        width: 100%;
                        max-width: 300px;
                    }
                    .btn-simular:hover {
                        background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%);
                        transform: translateY(-2px);
                        box-shadow: 0 6px 16px rgba(0,0,0,0.25);
                        border-color: #27ae60;
                    }
                    .btn-simular:active {
                        transform: translateY(0);
                        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                    }
                </style>
            </div>
            """
            st.markdown(botao_html, unsafe_allow_html=True)
            
            simular = st.button(
                "🔄 EXECUTAR SIMULAÇÃO",
                key="btn_simular",
                use_container_width=True,
                type="primary"
            )
            
            if simular:
                st.session_state.simulacao_executada = True
                st.success("✅ Simulação executada com sucesso!")
        else:
            st.markdown(
                """
                <div style="
                    text-align: center;
                    padding: 16px;
                    background: #2c3e50;
                    border-radius: 12px;
                    border: 2px dashed #7f8c8d;
                ">
                    <span style="color: #bdc3c7; font-size: 1.1em; font-weight: bold;">
                        💡 Preencha pelo menos um campo para simular
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )

    # 3. MOSTRAR RESULTADOS APENAS APÓS SIMULAÇÃO
    if st.session_state.simulacao_executada and tem_valores:
        
        # Cálculos (executados apenas quando necessário)
        credito_4 = entrada_4 * 0.04
        credito_7 = entrada_7 * 0.07
        credito_12 = entrada_12 * 0.12
        credito_19 = entrada_19 * 0.19

        debito_12 = saida_12 * 0.12
        debito_11 = saida_11 * 0.11
        debito_protege = saida_11 * 0.01
        debito_19 = saida_19 * 0.19

        total_creditos = credito_4 + credito_7 + credito_12 + credito_19
        total_debitos = debito_12 + debito_11 + debito_protege + debito_19
        apuracao = credito_acumulado + total_creditos - total_debitos

        # CARD GRANDE DO RESULTADO
        cor_fundo = "#27ae60" if apuracao >= 0 else "#e74c3c"
        
        st.markdown(
            f"""
            <div style="
                background: {cor_fundo};
                border-radius: 16px;
                padding: 24px;
                text-align: center;
                margin: 24px 0;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                animation: slideIn 0.5s ease-out;
            ">
                <h2 style="color: white; margin: 0; font-size: 1.5em; font-weight: bold;">
                    🎯 RESULTADO DA SIMULAÇÃO ICMS
                </h2>
                <div style="color: white; font-size: 2.5em; font-weight: bold; margin: 12px 0;">
                    {format_brl(apuracao)}
                </div>
                <div style="color: white; font-size: 0.9em; margin-top: 8px; font-weight: bold;">
                    Crédito acumulado atual: {format_brl(credito_acumulado)}
                </div>
            </div>
            <style>
                @keyframes slideIn {{
                    from {{ opacity: 0; transform: translateY(-20px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
            </style>
            """,
            unsafe_allow_html=True
        )

        # RESULTADOS DETALHADOS
        col_res1, col_res2 = st.columns(2, gap="large")
        
        with col_res1:
            st.markdown(
                """
                <div style="
                    background: #1a2433;
                    border-radius: 12px;
                    padding: 20px;
                    border: 1px solid #2c3e50;
                ">
                    <h4 style="color: white; margin: 0 0 16px 0; font-weight: bold;">
                        Créditos por ICMS
                    </h4>
                """,
                unsafe_allow_html=True
            )
            
            st.markdown(f"""
                <div style="font-family: 'Segoe UI', sans-serif; line-height: 1.6;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">4%:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(credito_4)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">7%:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(credito_7)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">12%:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(credito_12)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">19%:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(credito_19)}</span>
                    </div>
                    <hr style="margin: 12px 0; border: none; border-top: 2px solid #ecf0f1;">
                    <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 1.1em;">
                        <span style="color: white;">Total:</span>
                        <span style="color: white;">{format_brl(total_creditos)}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)

        with col_res2:
            st.markdown(
                """
                <div style="
                    background: #1a2433;
                    border-radius: 12px;
                    padding: 20px;
                    border: 1px solid #2c3e50;
                ">
                    <h4 style="color: white; margin: 0 0 16px 0; font-weight: bold;">
                        Débitos por ICMS
                    </h4>
                """,
                unsafe_allow_html=True
            )
            
            st.markdown(f"""
                <div style="font-family: 'Segoe UI', sans-serif; line-height: 1.6;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">12%:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(debito_12)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">11%:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(debito_11)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">PROTEGE:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(debito_protege)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">19%:</span>
                        <span style="color: white; font-weight: bold;">{format_brl(debito_19)}</span>
                    </div>
                    <hr style="margin: 12px 0; border: none; border-top: 2px solid #ecf0f1;">
                    <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 1.1em;">
                        <span style="color: white;">Total:</span>
                        <span style="color: white;">{format_brl(total_debitos)}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
def simulador_pis_cofins_manual(df=None, ano_sel=None, meses_sel=None):
    st.header("Simulação Manual de PIS/COFINS")

    # Inicializar session_state
    if 'entrada_pis_text' not in st.session_state:
        st.session_state.entrada_pis_text = ""
    if 'saida_pis_text' not in st.session_state:
        st.session_state.saida_pis_text = ""
    if 'simulacao_pis_executada' not in st.session_state:
        st.session_state.simulacao_pis_executada = False

    # Puxar crédito acumulado do último mês, se DataFrame for fornecido
    credito_acumulado = 0.0
    if df is not None and ano_sel is not None:
        if meses_sel:
            meses_param = meses_sel
        else:
            meses_param = [MESES_PT[m] for m in range(1, 13)]
        todos_meses = calcular_resumo_fiscal_mes_a_mes(df, ano_sel, meses_param)
        if todos_meses:
            credito_acumulado = todos_meses[-1].get('Crédito PIS/COFINS Transportado', 0.0)

    # Converter valores de texto para float
    entrada_valor = moeda_to_float(st.session_state.entrada_pis_text)
    saida_valor = moeda_to_float(st.session_state.saida_pis_text)

    col_entradas, col_saidas = st.columns(2, gap="large")
    with col_entradas:
        st.markdown(
            """
            <div style="
                background: #1a2433;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #2c3e50;
            ">
                <h3 style="color: white; margin: 0 0 16px 0; font-size: 1.1em; font-weight: bold;">
                    Entradas — Créditos PIS/COFINS
                </h3>
            """,
            unsafe_allow_html=True
        )
        st.session_state.entrada_pis_text = st.text_input(
            "Total Entradas (NFs com direito a crédito)", 
            value=st.session_state.entrada_pis_text,
            key="input_entrada_pis_text",
            placeholder="Ex: 50000,00"
        )
        if st.session_state.entrada_pis_text:
            st.markdown(f"<div style='color: #27ae60; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💰 {moeda_format(st.session_state.entrada_pis_text)}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_saidas:
        st.markdown(
            """
            <div style="
                background: #1a2433;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #2c3e50;
            ">
                <h3 style="color: white; margin: 0 0 16px 0; font-size: 1.1em; font-weight: bold;">
                    Saídas — Débitos PIS/COFINS
                </h3>
            """,
            unsafe_allow_html=True
        )
        st.session_state.saida_pis_text = st.text_input(
            "Total Saídas (Faturamento tributado)", 
            value=st.session_state.saida_pis_text,
            key="input_saida_pis_text",
            placeholder="Ex: 70000,00"
        )
        if st.session_state.saida_pis_text:
            st.markdown(f"<div style='color: #e74c3c; font-weight: bold; margin-top: -10px; margin-bottom: 10px;'>💸 {moeda_format(st.session_state.saida_pis_text)}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Botão de simulação
    st.markdown("<br>", unsafe_allow_html=True)
    tem_valores = st.session_state.entrada_pis_text or st.session_state.saida_pis_text
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if tem_valores:
            st.markdown("""
            <div style="text-align: center; margin: 20px 0;">
                <style>
                    .btn-simular {
                        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                        border: 2px solid #1a2433;
                        border-radius: 12px;
                        color: white;
                        padding: 16px 40px;
                        font-size: 1.1em;
                        font-weight: bold;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                        text-transform: uppercase;
                        letter-spacing: 1px;
                        width: 100%;
                        max-width: 300px;
                    }
                    .btn-simular:hover {
                        background: linear-gradient(135deg, #34495e 0%, #2c3e50 100%);
                        transform: translateY(-2px);
                        box-shadow: 0 6px 16px rgba(0,0,0,0.25);
                        border-color: #27ae60;
                    }
                    .btn-simular:active {
                        transform: translateY(0);
                        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                    }
                </style>
            </div>
            """, unsafe_allow_html=True)
            simular = st.button(
                "🔄 EXECUTAR SIMULAÇÃO",
                key="btn_simular_pis",
                use_container_width=True,
                type="primary"
            )
            if simular:
                st.session_state.simulacao_pis_executada = True
                st.success("✅ Simulação executada com sucesso!")
        else:
            st.markdown("""
                <div style="
                    text-align: center;
                    padding: 16px;
                    background: #2c3e50;
                    border-radius: 12px;
                    border: 2px dashed #7f8c8d;
                ">
                    <span style="color: #bdc3c7; font-size: 1.1em; font-weight: bold;">
                        💡 Preencha pelo menos um campo para simular
                    </span>
                </div>
            """, unsafe_allow_html=True)

    # Resultado apenas se simulado
    if st.session_state.simulacao_pis_executada and tem_valores:
        credito_entradas = entrada_valor * 0.0925
        debito_saidas = saida_valor * 0.0925
        apuracao = credito_acumulado + credito_entradas - debito_saidas
        cor_fundo = "#27ae60" if apuracao >= 0 else "#e74c3c"
        st.markdown(
            f"""
            <div style="
                background: {cor_fundo};
                border-radius: 16px;
                padding: 24px;
                text-align: center;
                margin: 24px 0;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                animation: slideIn 0.5s ease-out;
            ">
                <h2 style="color: white; margin: 0; font-size: 1.5em; font-weight: bold;">
                    🎯 RESULTADO DA SIMULAÇÃO PIS/COFINS
                </h2>
                <div style="color: white; font-size: 2.5em; font-weight: bold; margin: 12px 0;">
                    {format_brl(apuracao)}
                </div>
                <div style="color: white; font-size: 0.9em; margin-top: 8px; font-weight: bold;">
                    Crédito acumulado atual: {format_brl(credito_acumulado)}
                </div>
            </div>
            <style>
                @keyframes slideIn {{
                    from {{ opacity: 0; transform: translateY(-20px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
            </style>
            """,
            unsafe_allow_html=True
        )

        col_res1, col_res2 = st.columns(2, gap="large")
        with col_res1:
            st.markdown(
                """
                <div style="
                    background: #1a2433;
                    border-radius: 12px;
                    padding: 20px;
                    border: 1px solid #2c3e50;
                ">
                    <h4 style="color: white; margin: 0 0 16px 0; font-weight: bold;">
                        Créditos de PIS/COFINS
                    </h4>
                """,
                unsafe_allow_html=True
            )
            st.markdown(f"""
                <div style="font-family: 'Segoe UI', sans-serif; line-height: 1.6;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">Total Entradas:</span>
                        <span style="color: white; font-weight: bold;">{moeda_format(st.session_state.entrada_pis_text)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">Crédito PIS/COFINS (9,25%):</span>
                        <span style="color: white; font-weight: bold;">{format_brl(credito_entradas)}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with col_res2:
            st.markdown(
                """
                <div style="
                    background: #1a2433;
                    border-radius: 12px;
                    padding: 20px;
                    border: 1px solid #2c3e50;
                ">
                    <h4 style="color: white; margin: 0 0 16px 0; font-weight: bold;">
                        Débitos de PIS/COFINS
                    </h4>
                """,
                unsafe_allow_html=True
            )
            st.markdown(f"""
                <div style="font-family: 'Segoe UI', sans-serif; line-height: 1.6;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">Total Saídas:</span>
                        <span style="color: white; font-weight: bold;">{moeda_format(st.session_state.saida_pis_text)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span style="color: white; font-weight: bold;">Débito PIS/COFINS (9,25%):</span>
                        <span style="color: white; font-weight: bold;">{format_brl(debito_saidas)}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
