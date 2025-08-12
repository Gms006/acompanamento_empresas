# app/relatorio_graficos.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.meses import MESES_PT, MES_PARA_NUM
from app.relatorio_fiscal import calcular_resumo_fiscal_mes_a_mes

def brl_format(val: float) -> str:
    """Formata número para R$ 1.234.567,89"""
    s = f"R$ {val:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def abbr_format(val: float) -> str:
    """Abrevia valores: 1.200 -> 1.2K, 2.500.000 -> 2.5M"""
    abs_val = abs(val)
    if abs_val >= 1_000_000:
        return f"R$ {val/1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"R$ {val/1_000:.1f}K"
    return brl_format(val)

def create_kpi_cards_html(total_ent, total_sai, saldo):
    """Cria os KPI cards com design customizado"""
    # Define cor do saldo baseado no valor
    saldo_color = "rgba(46,160,67,0.9)" if saldo >= 0 else "rgba(214,39,40,0.9)"
    saldo_gradient = "linear-gradient(135deg, rgba(46,160,67,0.9) 0%, rgba(102,187,106,0.8) 100%)" if saldo >= 0 else "linear-gradient(135deg, rgba(214,39,40,0.9) 0%, rgba(255,107,107,0.8) 100%)"
    saldo_border = "#66bb6a" if saldo >= 0 else "#ff6b6b"
    
    return f"""
    <style>
    .kpi-container {{
        display: flex;
        gap: 20px;
        margin: 30px 0;
        justify-content: space-between;
    }}
    .kpi-card {{
        flex: 1;
        padding: 28px 24px;
        border-radius: 16px;
        text-align: left;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
    }}
    .kpi-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: currentColor;
    }}
    .kpi-entradas {{
        background: linear-gradient(135deg, rgba(31,119,180,0.9) 0%, rgba(74,158,255,0.8) 100%);
        color: white;
        border-left: 4px solid #4a9eff;
    }}
    .kpi-saidas {{
        background: linear-gradient(135deg, rgba(255,127,14,0.9) 0%, rgba(255,179,102,0.8) 100%);
        color: white;
        border-left: 4px solid #ffb366;
    }}
    .kpi-saldo {{
        background: {saldo_gradient};
        color: white;
        border-left: 4px solid {saldo_border};
    }}
    .kpi-label {{
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 12px;
        opacity: 0.85;
        color: rgba(255,255,255,0.9);
    }}
    .kpi-value {{
        font-size: 32px;
        font-weight: 800;
        font-family: 'Inter', 'Roboto', sans-serif;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        line-height: 1;
    }}
    .kpi-icon {{
        position: absolute;
        top: 24px;
        right: 24px;
        font-size: 28px;
        opacity: 0.15;
        font-weight: bold;
    }}
    </style>
    
    <div class="kpi-container">
        <div class="kpi-card kpi-entradas">
            <div class="kpi-icon">📈</div>
            <div class="kpi-label">Total Entradas</div>
            <div class="kpi-value">{brl_format(total_ent)}</div>
        </div>
        <div class="kpi-card kpi-saidas">
            <div class="kpi-icon">💰</div>
            <div class="kpi-label">Total Saídas</div>
            <div class="kpi-value">{brl_format(total_sai)}</div>
        </div>
        <div class="kpi-card kpi-saldo">
            <div class="kpi-icon">⚖️</div>
            <div class="kpi-label">Saldo Líquido</div>
            <div class="kpi-value">{brl_format(saldo)}</div>
        </div>
    </div>
    """

def create_modern_bar_chart(df, x_col, y_col, color_col, title, color_map, template="plotly_dark"):
    """Cria gráfico de barras com design moderno"""
    fig = px.bar(
        df,
        x=x_col, 
        y=y_col, 
        color=color_col,
        barmode="group",
        text="LabelAbbr" if "LabelAbbr" in df.columns else None,
        template=template,
        color_discrete_map=color_map
    )
    
    # Configurações visuais modernas
    fig.update_layout(
        title={
            'text': title,
            'x': 0,
            'font': {'size': 20, 'family': 'Inter, sans-serif', 'color': '#FFFFFF'}
        },
        xaxis_title="",
        yaxis_title="",
        legend_title_text="",
        font={'family': 'Inter, sans-serif', 'color': '#FFFFFF'},
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=60, b=50, l=50, r=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font={'size': 13, 'color': '#E8E8E8'},
            bgcolor='rgba(40,40,40,0.6)',
            bordercolor='rgba(255,255,255,0.1)',
            borderwidth=1
        )
    )
    
    # Configurações das barras
    fig.update_traces(
        textposition="outside",
        textfont={'size': 13, 'color': '#FFFFFF', 'family': 'Inter, sans-serif'},
        hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:$,.2f}<extra></extra>",
        marker_line_width=0,
        opacity=0.95
    )
    
    # Grid mais sutil e eixos melhorados
    fig.update_xaxes(
        showgrid=False,
        tickfont={'size': 12, 'color': '#D0D0D0', 'family': 'Inter, sans-serif'},
        tickangle=-45 if len(df[x_col].unique()) > 4 else 0
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(255,255,255,0.08)',
        tickfont={'size': 12, 'color': '#D0D0D0', 'family': 'Inter, sans-serif'},
        tickformat='$,.0f',
        zeroline=True,
        zerolinewidth=2,
        zerolinecolor='rgba(255,255,255,0.2)'
    )

    return fig


def mostrar_entradas_saidas(
    df_entradas: pd.DataFrame,
    df_saidas: pd.DataFrame,
    anos: list[int],
    meses: list[int],
    somente_tributaveis: bool = False,
):
    """Exibe gráfico comparativo de Entradas x Saídas.

    Parâmetros
    ----------
    df_entradas, df_saidas : DataFrames das notas.
    anos : lista contendo o ano selecionado.
    meses : lista de números dos meses (1-12).
    somente_tributaveis : quando True, filtra apenas
        entradas classificadas como Mercadoria para Revenda ou Frete.
    """

    ano_sel = anos[0] if isinstance(anos, (list, tuple)) else anos
    meses_num = meses if meses else list(range(1, 13))

    def prepara(df: pd.DataFrame, is_entrada: bool) -> pd.DataFrame:
        df = df.copy()
        df["Data Emissão"] = pd.to_datetime(
            df["Data Emissão"], format="%d/%m/%Y", errors="coerce"
        )
        df = df[
            (df["Data Emissão"].dt.year == ano_sel)
            & (df["Data Emissão"].dt.month.isin(meses_num))
        ]
        if is_entrada and somente_tributaveis:
            df = df[
                df["Classificação"].str.contains(
                    r"(Mercadoria para Revenda|Frete)",
                    case=False,
                    na=False,
                )
            ]
        return df

    df_ent = prepara(df_entradas, True)
    df_sai = prepara(df_saidas, False)

    ent_mes = df_ent.groupby(df_ent["Data Emissão"].dt.month)["Valor Líquido"].sum()
    sai_mes = df_sai.groupby(df_sai["Data Emissão"].dt.month)["Valor Líquido"].sum()
    df_mes = pd.concat([ent_mes, sai_mes], axis=1).fillna(0)
    df_mes.columns = ["Entradas", "Saídas"]
    df_mes = df_mes.reset_index()

    col0 = df_mes.columns[0]
    df_mes = df_mes.rename(columns={col0: "mes"})
    if "mes" not in df_mes.columns:
        if "Mês" in df_mes.columns:
            inv = {v: k for k, v in MESES_PT.items()}
            df_mes["mes"] = df_mes["Mês"].map(inv)
        elif "Data Emissão" in df_mes.columns:
            df_mes["mes"] = pd.to_datetime(
                df_mes["Data Emissão"], errors="coerce"
            ).dt.month

    df_mes["Mês"] = df_mes["mes"].map(MESES_PT)
    df_mes = df_mes.sort_values("mes")

    st.markdown(
        '<h2 class="section-title">Entradas x Saídas por Período</h2>',
        unsafe_allow_html=True,
    )

    mostrar_por_mes = set(meses_num) == set(range(1, 13))
    if mostrar_por_mes:
        df_plot = df_mes.melt(
            id_vars=["Mês"],
            value_vars=["Entradas", "Saídas"],
            var_name="Tipo",
            value_name="Valor",
        )
        df_plot["LabelAbbr"] = df_plot["Valor"].apply(abbr_format)
        fig_es = create_modern_bar_chart(
            df_plot,
            "Mês",
            "Valor",
            "Tipo",
            "",
            {"Entradas": "#1f77b4", "Saídas": "#ff7f0e"},
        )
    else:
        total_ent = df_mes["Entradas"].sum()
        total_sai = df_mes["Saídas"].sum()
        df_total = pd.DataFrame(
            {"Tipo": ["Entradas", "Saídas"], "Valor": [total_ent, total_sai]}
        )
        df_total["LabelAbbr"] = df_total["Valor"].apply(abbr_format)
        fig_es = create_modern_bar_chart(
            df_total,
            "Tipo",
            "Valor",
            "Tipo",
            "",
            {"Entradas": "#1f77b4", "Saídas": "#ff7f0e"},
        )

    st.plotly_chart(fig_es, use_container_width=True)

    return df_mes

def create_modern_pie_chart(df, names_col, values_col, title):
    """Cria gráfico de pizza com design moderno e melhor contraste"""
    # Paleta de cores mais vibrante e contrastante
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
              '#DDA0DD', '#98D8E8', '#F7DC6F', '#BB8FCE', '#85C1E9']
    
    fig = px.pie(
        df,
        names=names_col,
        values=values_col,
        hole=0.5,
        template="plotly_dark",
        color_discrete_sequence=colors
    )
    
    fig.update_layout(
        title={
            'text': title,
            'x': 0,
            'font': {'size': 20, 'family': 'Inter, sans-serif', 'color': '#FFFFFF'}
        },
        font={'family': 'Inter, sans-serif'},
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=60, b=40, l=40, r=40),
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05,
            font={'size': 14, 'color': '#E8E8E8', 'family': 'Inter, sans-serif'},
            bgcolor='rgba(40,40,40,0.8)',
            bordercolor='rgba(255,255,255,0.1)',
            borderwidth=1,
            itemsizing="constant"
        )
    )
    
    fig.update_traces(
        textinfo="percent",
        texttemplate="<b>%{percent}</b>",
        textfont={'size': 14, 'color': '#000000', 'family': 'Inter, sans-serif'},
        textposition="inside",
        hovertemplate="<b>%{label}</b><br>Valor: %{value:$,.2f}<br>Percentual: %{percent}<extra></extra>",
        marker_line_width=3,
        marker_line_color='rgba(255,255,255,0.8)',
        pull=[0.05] * len(df)  # Separar ligeiramente as fatias
    )
    
    return fig

def mostrar_dashboard(df_entradas: pd.DataFrame,
                      df_saidas: pd.DataFrame,
                      anos: list[int],
                      meses: list[int]):

    # CSS personalizado para o dashboard
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    .main-title {
        font-size: 36px;
        font-weight: 800;
        color: #FFFFFF;
        font-family: 'Inter', sans-serif;
        text-align: center;
        margin: 20px 0 50px 0;
        text-shadow: 0 4px 8px rgba(0,0,0,0.3);
        letter-spacing: -0.5px;
    }
    .section-title {
        font-size: 22px;
        font-weight: 700;
        color: #FFFFFF;
        font-family: 'Inter', sans-serif;
        margin: 50px 0 25px 0;
        padding: 15px 20px;
        border-left: 4px solid #1f77b4;
        background: linear-gradient(90deg, rgba(31,119,180,0.15) 0%, rgba(31,119,180,0.05) 100%);
        border-radius: 0 8px 8px 0;
        letter-spacing: -0.3px;
    }
    .stPlotlyChart {
        background: linear-gradient(145deg, rgba(45,55,75,0.4) 0%, rgba(25,35,55,0.6) 100%);
        border-radius: 16px;
        padding: 25px;
        margin: 25px 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        border: 1px solid rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
    }
    .main .block-container {
        padding-top: 2rem;
        max-width: 1400px;
    }
    /* Melhoria no contraste geral */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #FFFFFF !important;
        font-family: 'Inter', sans-serif !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Título principal
    st.markdown('<h1 class="main-title">Apuração Fiscal</h1>', unsafe_allow_html=True)

    # 1) Período
    ano_sel = anos[0] if isinstance(anos, (list, tuple)) else anos
    meses_num = meses if meses else list(range(1, 13))

    # 2) Filtrar
    def filtrar(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Data Emissão"] = pd.to_datetime(df["Data Emissão"], format="%d/%m/%Y", errors="coerce")
        return df[
            (df["Data Emissão"].dt.year == ano_sel) &
            (df["Data Emissão"].dt.month.isin(meses_num))
        ]

    df_ent = filtrar(df_entradas)
    df_sai = filtrar(df_saidas)

    # 3) KPI Cards customizados
    total_ent = df_ent["Valor Líquido"].sum()
    total_sai = df_sai["Valor Líquido"].sum()
    saldo = total_sai - total_ent

    st.markdown(create_kpi_cards_html(total_ent, total_sai, saldo), unsafe_allow_html=True)

    mostrar_entradas_saidas(df_ent, df_sai, [ano_sel], meses_num)

    # 1) Mercadorias por Estado
    st.markdown('<h2 class="section-title">Mercadorias por Estado</h2>', unsafe_allow_html=True)
    df_comp = df_ent[df_ent["Classificação"]
                     .str.contains("Mercadoria para Revenda", case=False, na=False)]
    comp_uf = df_comp.groupby("UF Emitente")["Valor Líquido"]\
                     .sum().reset_index().rename(columns={"Valor Líquido":"Entradas"})
    # Apenas entradas, sem saídas
    df_merc = comp_uf.copy()
    df_merc["LabelAbbr"] = df_merc["Entradas"].apply(abbr_format)
    # Paleta igual à do gráfico de pizza
    pie_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                  '#DDA0DD', '#98D8E8', '#F7DC6F', '#BB8FCE', '#85C1E9']
    # Mapear cores para cada UF (em ordem de aparição)
    unique_ufs = df_merc["UF Emitente"].unique()
    color_map = {uf: pie_colors[i % len(pie_colors)] for i, uf in enumerate(unique_ufs)}
    fig_merc = create_modern_bar_chart(
        df_merc,
        "UF Emitente", "Entradas", None,
        "",
        color_map
    )
    st.plotly_chart(fig_merc, use_container_width=True)

    # 2) Pizza de crédito ICMS
    st.markdown('<h2 class="section-title">Distribuição do Crédito ICMS por UF</h2>', unsafe_allow_html=True)
    df_credito_uf = df_ent.groupby("UF Emitente")["Valor ICMS"]\
                          .sum().reset_index()
    df_credito_uf["LabelAbbr"] = df_credito_uf["Valor ICMS"].apply(abbr_format)
    fig_pie = create_modern_pie_chart(
        df_credito_uf,
        "UF Emitente",
        "Valor ICMS",
        ""
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    # 3) ICMS
    st.markdown('<h2 class="section-title">Crédito x Débito de ICMS</h2>', unsafe_allow_html=True)
    df_all = pd.concat([df_ent, df_sai], ignore_index=True)
    rel_ic = calcular_resumo_fiscal_mes_a_mes(df_all, ano_sel, meses_num)
    df_ic = pd.DataFrame(rel_ic)
    df_ic["Período"] = df_ic["Ano"].astype(str) + "-" + df_ic["Mês"].map(MES_PARA_NUM).apply(lambda m: f"{m:02d}")
    df_ic_long = df_ic.melt(
        id_vars=["Período"],
        value_vars=["ICMS Entradas","ICMS Saídas"],
        var_name="Tipo",
        value_name="Valor"
    )
    df_ic_long["LabelAbbr"] = df_ic_long["Valor"].apply(abbr_format)
    fig_ic = create_modern_bar_chart(
        df_ic_long,
        "Período", "Valor", "Tipo",
        "",
        {"ICMS Entradas":"#2ca02c","ICMS Saídas":"#d62728"}
    )
    st.plotly_chart(fig_ic, use_container_width=True)

    # 4) PIS & COFINS
    st.markdown('<h2 class="section-title">Crédito x Débito de PIS/COFINS</h2>', unsafe_allow_html=True)
    rel_pc = calcular_resumo_fiscal_mes_a_mes(df_all, ano_sel, meses_num)
    df_pc = pd.DataFrame(rel_pc)
    df_pc["Período"] = df_pc["Ano"].astype(str) + "-" + df_pc["Mês"].map(MES_PARA_NUM).apply(lambda m: f"{m:02d}")
    df_pc_long = df_pc.melt(
        id_vars=["Período"],
        value_vars=["PIS/COFINS Entradas","PIS/COFINS Saídas"],
        var_name="Tipo",
        value_name="Valor"
    )
    df_pc_long["LabelAbbr"] = df_pc_long["Valor"].apply(abbr_format)
    fig_pc = create_modern_bar_chart(
        df_pc_long,
        "Período", "Valor", "Tipo",
        "",
        {"PIS/COFINS Entradas":"#9467bd","PIS/COFINS Saídas":"#ff7f0e"}
    )
    st.plotly_chart(fig_pc, use_container_width=True)