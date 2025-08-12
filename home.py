import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

from app.meses import MESES_PT, MES_PARA_NUM

from app.relatorio_fiscal import calcular_resumo_fiscal_mes_a_mes, gerar_excel_resumo
from app.relatorio_fiscal import simulador_icms_manual, simulador_pis_cofins_manual  # <-- Adicione aqui
from app.relatorio_contabil import mostrar_resumo_contabil
from app.relatorio_graficos import mostrar_dashboard, mostrar_entradas_saidas

DATA_PATH = Path(r"U:\Automações PYTHON\Acompanhamento de empresas\data\notas_fiscais.xlsx")
LOGO_PATH = Path(r"U:\Automações PYTHON\Acompanhamento de empresas\assets\logo.png")

st.set_page_config(page_title="Acompanhamento de Empresas", layout="wide")

def format_brl(valor):
    if pd.isna(valor):
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.markdown(
    """
    <style>
    .main {background-color: #181c23;}
    .stAlert, .st-emotion-cache-1kyxreq {background: #1a2e43;}
    .st-emotion-cache-1avcm0n {background: #202734;}
    .st-emotion-cache-13k62yr {background: #232f3e;}
    .card {
        border-radius: 18px;
        padding: 22px 12px;
        background: #22293a;
        margin-bottom: 10px;
        text-align: center;
        color: #eaeaea;
        font-size: 1.18em;
        box-shadow: 0 1px 6px #0002;
    }
    .card.red {background: #3c1c1c;}
    .card.green {background: #183c1c;}
    .card.blue {background: #18243c;}
    .card.orange {background: #b6860a;}
    .titulo-apuracao {
        margin: 12px 0 2px 0;
        color: #b8b8b8;
        font-size: 1.12em;
        font-weight: 600;
        letter-spacing: 1.5px;
    }
    .sidebar-folder {
        font-size: 1.15em !important;
        color: #ffdf7f !important;
        margin-top: 18px !important;
        margin-bottom: 5px !important;
        font-weight: 700;
        letter-spacing: .5px;
        display: flex;
        align-items: center;
        gap: 7px;
    }
    .sidebar-doc {
        font-size: 1.05em !important;
        color: #b0b0b0 !important;
        margin-left: 9px !important;
        margin-bottom: 2px !important;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .card-destaque {
        border-radius: 18px;
        padding: 26px 0 18px 0;
        background: #2d3507;
        color: #fcff80;
        font-size: 1.48em;
        font-weight: 700;
        margin-bottom: 18px;
        text-align: center;
        box-shadow: 0 2px 9px #0003;
        border: 2px solid #d5df27;
        letter-spacing: .5px;
    }
    .card-destaque-red {
        border-radius: 18px;
        padding: 24px 0 14px 0;
        background: #3c1c1c;
        color: #ffc2c2;
        font-size: 1.38em;
        font-weight: 700;
        margin-bottom: 18px;
        text-align: center;
        border: 2px solid #e74c3c;
        box-shadow: 0 2px 9px #0003;
        letter-spacing: .5px;
    }
    .card-destaque-green {
        border-radius: 18px;
        padding: 24px 0 14px 0;
        background: #183c1c;
        color: #cafcca;
        font-size: 1.38em;
        font-weight: 700;
        margin-bottom: 18px;
        text-align: center;
        border: 2px solid #69e137;
        box-shadow: 0 2px 9px #0003;
        letter-spacing: .5px;
    }
    </style>
    """, unsafe_allow_html=True
)

# ===== SIDEBAR (MENU LATERAL) =====
with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=200)
    st.markdown("<h4 style='text-align:center; color:#cead43;'>Neto Contabilidade</h4>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("#### Filtros de Período")
    @st.cache_data
    def carregar_df_unico(path):
        all_sheets = pd.read_excel(path, sheet_name=None)
        df_list = [
            df for name, df in all_sheets.items()
            if name.strip().lower() in ["entradas", "saídas"]
        ]
        if not df_list:
            return pd.DataFrame()
        df_full = pd.concat(df_list, ignore_index=True)
        return df_full

    @st.cache_data
    def get_periodos(df):
        if "Data Emissão" not in df.columns:
            return [], [], []
        datas = pd.to_datetime(df["Data Emissão"], format="%d/%m/%Y", errors='coerce')
        anos = sorted(datas.dt.year.dropna().unique().astype(int).tolist())
        meses = sorted(datas.dt.month.dropna().unique().astype(int).tolist())
        return anos, meses, datas

    try:
        df = carregar_df_unico(DATA_PATH)
        anos, meses, datas = get_periodos(df)
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        df = pd.DataFrame()
        anos, meses, datas = [], [], []

    ano_sel = st.selectbox(
        "Ano",
        options=anos if anos else [2025],
        index=0 if anos else 0,
    )

    meses_lista = [MESES_PT[m] for m in meses] if meses else [MESES_PT[1]]
    meses_lista = ["Todos"] + meses_lista
    meses_sel = st.multiselect(
        "Meses",
        options=meses_lista,
        default=["Todos"],
    )

    st.markdown("---")
    st.markdown(
        "<div class='sidebar-folder'>📂 Tipo de Relatório:</div>",
        unsafe_allow_html=True
    )
    tipo_opcoes = {
        "📁 Fiscal": "Fiscal",
        "📊 Contábil": "Contábil",
        "📈 Dashboards": "Dashboards"
    }
    tipo_relatorio = st.radio(
        "",
        options=list(tipo_opcoes.keys()),
        format_func=lambda x: x.replace("📁 ", "").replace("📊 ", "").replace("📈 ", ""),
        label_visibility="collapsed",
        index=0
    )

    # Sub-relatórios por tipo
    relatorio_fiscal_opcoes = [
        "Apuração de Tributos Fiscais",
        "Simulação Manual de ICMS",
        "Simulação Manual de PIS/COFINS"   # <-- Aqui!
    ]
    relatorio_contabil_opcoes = ["DRE", "Balanço Patrimonial"]
    relatorio_dash_opcoes = ["Resumo Gráfico", "Indicadores"]

    if tipo_relatorio == "📁 Fiscal":
        st.markdown(
            "<div class='sidebar-doc'>📄 Relatórios Fiscais:</div>",
            unsafe_allow_html=True
        )
        relatorio_escolhido = st.selectbox(
            "",
            options=relatorio_fiscal_opcoes,
            index=0,
            key="rel_fiscal"
        )
    elif tipo_relatorio == "📊 Contábil":
        st.markdown(
            "<div class='sidebar-doc'>📄 Relatórios Contábeis:</div>",
            unsafe_allow_html=True
        )
        relatorio_escolhido = st.selectbox(
            "",
            options=relatorio_contabil_opcoes,
            key="rel_contabil"
        )
    elif tipo_relatorio == "📈 Dashboards":
        st.markdown(
            "<div class='sidebar-doc'>📄 Dashboards:</div>",
            unsafe_allow_html=True
        )
        relatorio_escolhido = st.selectbox(
            "",
            options=relatorio_dash_opcoes,
            key="rel_dash"
        )

st.title("Apuração Fiscal")

# --------- APURAÇÃO DO PERÍODO VIGENTE -----------
if tipo_relatorio == "📁 Fiscal" and relatorio_escolhido == "Apuração de Tributos Fiscais":
    resumo_mensal_full = calcular_resumo_fiscal_mes_a_mes(df, ano_sel, meses_sel)
    if resumo_mensal_full and isinstance(resumo_mensal_full, list):
        ultimo = resumo_mensal_full[-1]
        mes_vigente = ultimo.get("Mês", "-")
        ano_vigente = ultimo.get("Ano", "-")

        # ICMS
        icms_credito = ultimo.get("Crédito ICMS Transportado", 0.0)
        icms_pagar = ultimo.get("ICMS a Pagar", 0.0)

        # PIS/COFINS
        pis_credito = ultimo.get("Crédito PIS/COFINS Transportado", 0.0)
        pis_pagar = ultimo.get("PIS/COFINS a Pagar", 0.0)

        st.markdown(f"### Apuração do Período Vigente — {mes_vigente} {ano_vigente}")

        col_icms, col_pis = st.columns(2)
        # ICMS
        if icms_pagar > 0:
            col_icms.markdown(
                f"<div class='card-destaque-red'>ICMS A PAGAR<br><span style='font-size:1.15em;'>{format_brl(icms_pagar)}</span></div>",
                unsafe_allow_html=True
            )
        else:
            col_icms.markdown(
                f"<div class='card-destaque-green'>Crédito ICMS a Transportar<br><span style='font-size:1.15em;'>{format_brl(icms_credito)}</span></div>",
                unsafe_allow_html=True
            )
        # PIS/COFINS
        if pis_pagar > 0:
            col_pis.markdown(
                f"<div class='card-destaque-red'>PIS/COFINS A PAGAR<br><span style='font-size:1.15em;'>{format_brl(pis_pagar)}</span></div>",
                unsafe_allow_html=True
            )
        else:
            col_pis.markdown(
                f"<div class='card-destaque-green'>Crédito PIS/COFINS a Transportar<br><span style='font-size:1.15em;'>{format_brl(pis_credito)}</span></div>",
                unsafe_allow_html=True
            )
        entradas_fiscal = df[df['Tipo'].eq('Entrada')]
        saidas_fiscal = df[df['Tipo'].eq('Saída')]
        mostrar_entradas_saidas(
            entradas_fiscal,
            saidas_fiscal,
            [ano_sel],
            meses_sel,
            somente_tributaveis=True,
        )


st.markdown("---")
st.subheader("Relatórios disponíveis")

# RESTANTE: idêntico ao anterior...
if tipo_relatorio == "📁 Fiscal":
    if relatorio_escolhido == "Apuração de Tributos Fiscais":
        resumo_mensal = resumo_mensal_full  # já carregado acima para evitar cálculo duplo
        if resumo_mensal:
            for linha in resumo_mensal:
                with st.expander(f"{linha['Mês']} {linha['Ano']}", expanded=(linha['Mês'] == MESES_PT[datas.dt.month.min()])):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.markdown(f"<div class='card blue'>TOTAL ENTRADAS<br><b>{format_brl(linha['Entradas (Revenda + Frete)'])}</b></div>", unsafe_allow_html=True)
                    col_b.markdown(f"<div class='card blue'>TOTAL SAÍDAS<br><b>{format_brl(linha['Saídas'])}</b></div>", unsafe_allow_html=True)
                    resultado = linha['Resultado Líquido']
                    cor_resultado = "green" if resultado >= 0 else "red"
                    col_c.markdown(f"<div class='card {cor_resultado}'>RESULTADO<br><b>{format_brl(resultado)}</b></div>", unsafe_allow_html=True)

                    view_mode = st.radio(
                        "Ver",
                        ["Por mês", "Total"],
                        key=f"view_{linha['Ano']}_{linha['Mês']}",
                        horizontal=True,
                    )
                    if view_mode == "Por mês":
                        valores = [
                            linha["Entradas (Revenda + Frete)"],
                            linha["Saídas"],
                        ]
                    else:
                        total_ent = sum(l["Entradas (Revenda + Frete)"] for l in resumo_mensal)
                        total_sai = sum(l["Saídas"] for l in resumo_mensal)
                        valores = [total_ent, total_sai]
                    df_bar = pd.DataFrame({"Tipo": ["Entradas", "Saídas"], "Valor": valores})
                    fig = px.bar(df_bar, x="Tipo", y="Valor", text="Valor", template="plotly_dark")
                    fig.update_traces(texttemplate="R$ %{y:,.2f}", textposition="outside")
                    fig.update_layout(margin=dict(t=30, b=10))
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown("<div class='titulo-apuracao'>APURAÇÃO ICMS</div>", unsafe_allow_html=True)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.markdown(f"<div class='card'>ICMS ENTRADA<br><b>{format_brl(linha['ICMS Entradas'])}</b></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='card'>ICMS SAÍDA<br><b>{format_brl(linha['ICMS Saídas'])}</b></div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='card green'>ICMS TRANSPORTADO<br><b>{format_brl(linha['Crédito ICMS Transportado'])}</b></div>", unsafe_allow_html=True)
                    c4.markdown(f"<div class='card red'>ICMS A PAGAR<br><b>{format_brl(linha['ICMS a Pagar'])}</b></div>", unsafe_allow_html=True)

                    st.markdown("<div class='titulo-apuracao'>APURAÇÃO PIS/COFINS</div>", unsafe_allow_html=True)
                    d1, d2, d3, d4 = st.columns(4)
                    d1.markdown(f"<div class='card'>PIS/COFINS ENTRADA<br><b>{format_brl(linha['PIS/COFINS Entradas'])}</b></div>", unsafe_allow_html=True)
                    d2.markdown(f"<div class='card'>PIS/COFINS SAÍDA<br><b>{format_brl(linha['PIS/COFINS Saídas'])}</b></div>", unsafe_allow_html=True)
                    d3.markdown(f"<div class='card green'>PIS/COFINS TRANSPORTADO<br><b>{format_brl(linha['Crédito PIS/COFINS Transportado'])}</b></div>", unsafe_allow_html=True)
                    d4.markdown(f"<div class='card red'>PIS/COFINS A PAGAR<br><b>{format_brl(linha['PIS/COFINS a Pagar'])}</b></div>", unsafe_allow_html=True)

                    st.markdown(" ")
                    df_mes = pd.DataFrame([linha])
                    excel_mes = gerar_excel_resumo([linha])
                    st.download_button(
                        label=f"Baixar planilha deste mês ({linha['Mês']})",
                        data=excel_mes,
                        file_name=f"resumo_fiscal_{linha['Ano']}_{linha['Mês']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            st.markdown("---")
            st.subheader("Baixar Tabela Detalhada (todos os meses selecionados)")
            df_todos = pd.DataFrame(resumo_mensal)
            excel_all = gerar_excel_resumo(resumo_mensal)
            st.download_button(
                label="📥 Baixar planilha detalhada (.xlsx)",
                data=excel_all,
                file_name="resumo_fiscal_mes_a_mes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Nenhum dado fiscal disponível.")
    elif relatorio_escolhido == "Mapa por UF":
        st.info("Mapa por UF: (implementação futura)")
    elif relatorio_escolhido == "Simulação Manual de ICMS":
        # --------- SIMULAÇÃO MANUAL DE ICMS -----------
        simulador_icms_manual(df=df, ano_sel=ano_sel, meses_sel=meses_sel)
    elif relatorio_escolhido == "Simulação Manual de PIS/COFINS":
        # Simulador PIS/COFINS - NOVA FUNÇÃO
        simulador_pis_cofins_manual(df, ano_sel, meses_sel)
elif tipo_relatorio == "📊 Contábil":
    st.info(f"Relatório selecionado: {relatorio_escolhido} (implementação futura)")
elif tipo_relatorio == "📈 Dashboards":
    # Carrega as abas separadas
    entradas = pd.read_excel(DATA_PATH, sheet_name="Entradas")
    saidas = pd.read_excel(DATA_PATH, sheet_name="Saídas")
    mostrar_dashboard(entradas, saidas, [ano_sel], meses_sel)
else:
    st.info("Nenhum relatório configurado ainda. Selecione um tipo acima para iniciar.")

st.markdown(
    """
    <footer style="margin-top:2em;text-align:center; color:#888;">
    Neto Contabilidade &copy; 2025 — Todos os direitos reservados.
    </footer>
    """, unsafe_allow_html=True
)
