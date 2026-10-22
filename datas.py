import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --- 1. CONFIGURAZIONE PAGINA E INTESTAZIONE ---
st.set_page_config(page_title="Energy Data Explorer", layout="wide")
st.title("🌍 Energy Supply, Transizione & Sankeys")

st.markdown(
    "<div style='font-size:0.8em; color:#888; margin-top:-8px; margin-bottom:8px;'>"
    "Sviluppato da <b>Matteo De Piccoli</b> e <b>cs1bc</b><br>"
    "Autore di <a href='https://www.peoplepub.it/pagina-prodotto/avete-rotto-l-atomo' "
    "target='_blank' style='color:#888;'><i>Avete rotto l'atomo</i></a><br>"
    "<a href='https://unbelclima.it/' target='_blank' "
    "style='color:#16A34A; text-decoration:none;'>🌍 Ci Sarà un Bel Clima</a>"
    "</div>",
    unsafe_allow_html=True
)

FILE_PATH = "EI-Stats-Review-ALL-data (1).xlsx"
TWH_TO_EJ = 0.0036

# --- MAPPA COLORI ---
color_map = {
    'Coal': '#111827',
    'Oil': '#4B5563',
    'Natural Gas': '#9CA3AF',
    'Nuclear': '#9333EA',
    'Hydro': '#3B82F6',
    'Solar': '#FACC15',
    'Wind': '#22C55E',
    'Biomass/Geo': '#8B4513',
    'Biofuels': '#B45309',
    'Other': '#D1D5DB',
}
fuel_it = {
    'Coal': 'Carbone', 'Oil': 'Petrolio', 'Natural Gas': 'Gas', 'Nuclear': 'Nucleare',
    'Hydro': 'Idro', 'Solar': 'Solare', 'Wind': 'Eolico', 'Biomass/Geo': 'Biomasse/Geo',
    'Biofuels': 'Biocarburanti', 'Other': 'Altro (pompaggi, rifiuti)',
}

# --- AREE: nomi puliti, classificazione, etichette ---
CONTINENTS = ['Total North America', 'Total S. & Cent. America', 'Total Europe', 'Total CIS',
              'Total Middle East', 'Total Africa', 'Total Asia Pacific']
ECON_GROUPS = ['OECD', 'Non-OECD', 'European Union']
AREA_LABELS = {
    'Total World': 'Mondo',
    'Total North America': 'Nord America',
    'Total S. & Cent. America': 'America Centrale e Meridionale',
    'Total Europe': 'Europa',
    'Total CIS': 'CSI (ex URSS)',
    'Total Middle East': 'Medio Oriente',
    'Total Africa': 'Africa',
    'Total Asia Pacific': 'Asia Pacifico',
    'OECD': 'OCSE',
    'Non-OECD': 'Non-OCSE',
    'European Union': 'Unione Europea',
    'USSR': 'URSS (serie storica)',
    'Central America': 'America Centrale',
    'Other Caribbean': 'Altri Caraibi',
    'Other South America': 'Altri Sud America',
    'Other S. & Cent. America': 'Altri America Centro-Sud',
    'Other Europe': 'Altri Europa',
    'Other CIS': 'Altri CSI',
    'Other Middle East': 'Altri Medio Oriente',
    'Eastern Africa': 'Africa orientale',
    'Middle Africa': 'Africa centrale',
    'Western Africa': 'Africa occidentale',
    'Other Northern Africa': 'Altri Nord Africa',
    'Other Southern Africa': 'Altri Africa australe',
    'Other Africa': 'Altri Africa',
    'Other Asia Pacific': 'Altri Asia Pacifico',
}
NAME_ALIASES = {'Viet Nam': 'Vietnam'}


def clean_region(name):
    """Normalizza i nomi EI: spazi, 'of which:', simboli di nota (#, *, ^, ♦)."""
    s = str(name).strip()
    s = re.sub(r'^of which:\s*', '', s, flags=re.I)
    s = re.sub(r'[\s#*^♦]+$', '', s).strip()
    return NAME_ALIASES.get(s, s)


def area_kind(r):
    if r == 'Total World' or r in CONTINENTS or r in ECON_GROUPS:
        return 'aggregate'
    if r == 'USSR' or r.startswith('Other ') or r == 'Central America' or (
            r.endswith(' Africa') and r != 'South Africa'):
        return 'residual'
    return 'country'


def area_label(r):
    return AREA_LABELS.get(r, r)


# --- 2. CARICAMENTO DATI ---
def _is_year(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return f.is_integer() and 1900 < f <= 2100


def parse_sheet(raw, val_name):
    """Legge un foglio EI 'regioni x anni' trovando da solo la riga delle intestazioni.
    Scarta le righe senza numeri (note a piè di pagina) e i blocchi ripetuti."""
    hdr = None
    for i in range(min(12, len(raw))):
        if sum(_is_year(v) for v in raw.iloc[i, 1:]) >= 5:
            hdr = i
            break
    if hdr is None:
        return pd.DataFrame(columns=['Region', 'Year', val_name])
    year_cols = {}
    for j, v in enumerate(raw.iloc[hdr]):
        if j > 0 and _is_year(v) and int(float(v)) not in year_cols.values():
            year_cols[j] = int(float(v))  # solo la prima occorrenza (le altre sono tassi/quote)
    body = raw.iloc[hdr + 1:, [0] + list(year_cols)].copy()
    body.columns = ['Region'] + list(year_cols.values())
    body = body.dropna(subset=['Region'])
    vals = body.iloc[:, 1:].apply(pd.to_numeric, errors='coerce')
    body = body[vals.notna().any(axis=1)]
    body['Region'] = body['Region'].map(clean_region)
    body = body.drop_duplicates(subset='Region', keep='first')
    df = body.melt(id_vars='Region', var_name='Year', value_name=val_name)
    df['Year'] = df['Year'].astype(int)
    df[val_name] = pd.to_numeric(df[val_name], errors='coerce').fillna(0.0)
    return df


SHEETS = {
    # Energia primaria (EJ). Metodo EI 2026: idro/solare/eolico = contenuto energetico
    # dell'elettricità prodotta (1:1); nucleare con rendimento convenzionale 33%.
    'tes_total': ('Total Energy Supply (TES) -EJ', 'EJ', None),
    'Oil': ('Oil Consumption - EJ', 'EJ', 'Oil'),
    'Natural Gas': ('Gas Consumption - EJ', 'EJ', 'Natural Gas'),
    'Coal': ('Coal Consumption - EJ', 'EJ', 'Coal'),
    'Nuclear': ('Nuclear Consumption - EJ', 'EJ', 'Nuclear'),
    'Hydro': ('Hydro Consumption - EJ', 'EJ', 'Hydro'),
    'Solar': ('Solar Consumption - EJ', 'EJ', 'Solar'),
    'Wind': ('Wind Consumption - EJ', 'EJ', 'Wind'),
    'Biomass/Geo': ('Geo Biomass Other - EJ', 'EJ', 'Biomass/Geo'),
    'Biofuels': ('Biofuels consumption - PJ', 'EJ', 'Biofuels'),  # PJ -> EJ sotto
    # Generazione elettrica (TWh). I fogli "... inputs - Elec generation" sono già
    # generazione per fonte in TWh, non input di combustibile.
    'el_Nuclear': ('Nuclear Generation - TWh', 'TWh', 'Nuclear'),
    'el_Hydro': ('Hydro Generation - TWh', 'TWh', 'Hydro'),
    'el_Solar': ('Solar Generation - TWh', 'TWh', 'Solar'),
    'el_Wind': ('Wind Generation - TWh', 'TWh', 'Wind'),
    'el_Biomass/Geo': ('Geo Biomass Other - TWh', 'TWh', 'Biomass/Geo'),
    'el_Oil': ('Oil inputs - Elec generation ', 'TWh', 'Oil'),
    'el_Natural Gas': ('Gas inputs - Elec generation', 'TWh', 'Natural Gas'),
    'el_Coal': ('Coal inputs - Elec generation ', 'TWh', 'Coal'),
    'el_Other': ('Other inputs - Elec generation', 'TWh', 'Other'),
    'el_total': ('Electricity Generation - TWh', 'TWh_Total', None),
    'emis': ('CO2e Emissions ', 'MtCO2e', None),
    'tes_pc': ('TES per Capita', 'GJ_capita', None),
    'cap_Solar': ('Solar Installed Capacity', 'MW', 'Solar'),
    'cap_Wind': ('Wind Installed Capacity', 'MW', 'Wind'),
}


@st.cache_data
def load_data():
    names = sorted({v[0] for v in SHEETS.values()})
    raw = pd.read_excel(FILE_PATH, sheet_name=names, header=None)
    out = {}
    for key, (sheet, val, fuel) in SHEETS.items():
        df = parse_sheet(raw[sheet], val)
        if key == 'Biofuels':
            df['EJ'] = df['EJ'] / 1000.0
        if fuel:
            df['Fuel'] = fuel
        out[key] = df
    prim_fuels = ['Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Solar', 'Wind', 'Biomass/Geo', 'Biofuels']
    df_tes = pd.concat([out[f] for f in prim_fuels], ignore_index=True)
    df_elec = pd.concat([out[k] for k in out if k.startswith('el_') and k != 'el_total'], ignore_index=True)
    df_cap = pd.concat([out['cap_Solar'], out['cap_Wind']], ignore_index=True)
    return df_tes, df_elec, out['el_total'], out['tes_total'], out['emis'], out['tes_pc'], df_cap


df_tes, df_elec, df_elec_tot, df_tes_tot, df_emis, df_tes_pc, df_cap = load_data()
if df_tes.empty:
    st.error("Impossibile leggere il file Excel dei dati.")
    st.stop()

# --- 3. SIDEBAR: FILTRI ---
st.sidebar.header("Impostazioni Analisi")
all_regions = [r for r in df_tes_tot['Region'].unique()]
countries = sorted([r for r in all_regions if area_kind(r) == 'country'])
aggregates = [r for r in ['Total World'] + CONTINENTS + ECON_GROUPS if r in all_regions]
residuals = sorted([r for r in all_regions if area_kind(r) == 'residual'], key=area_label)

view_type = st.sidebar.radio("Tipo di Area:", ("Stati", "Continenti e aggregati", "Altre aree (residui EI)"))
if view_type == "Stati":
    options = countries
    default = options.index('Italy') if 'Italy' in options else 0
    help_txt = None
elif view_type == "Continenti e aggregati":
    options = aggregates
    default = 0
    help_txt = "Mondo, continenti EI e raggruppamenti economici (OCSE, Non-OCSE, UE)."
else:
    options = residuals
    default = 0
    help_txt = ("Gruppi residui dell'Energy Institute: paesi non riportati singolarmente "
                "(es. 'Altri Europa') e serie storiche (URSS).")

selected_region = st.sidebar.selectbox("Seleziona Area:", options, index=default,
                                       format_func=area_label, help=help_txt)
region_label = area_label(selected_region)

min_year, max_year = int(df_tes['Year'].min()), int(df_tes['Year'].max())
selected_year = st.sidebar.slider("Seleziona Anno:", min_value=min_year, max_value=max_year, value=max_year)
st.sidebar.caption("Fonte: Energy Institute, *Statistical Review of World Energy* 2026. "
                   "Dati elettrici dal 1985, emissioni CO2e dal 1990.")


# --- 4. PREPARAZIONE DATI ---
def get_region_year(df):
    return df[(df['Region'] == selected_region) & (df['Year'] == selected_year)]


def elec_history(region):
    """Mix elettrico (TWh) per fonte e anno, direttamente dai fogli EI.
    Solo gli anni con generazione totale disponibile (dal 1985): prima mancano i fossili."""
    ok_years = df_elec_tot[(df_elec_tot['Region'] == region) & (df_elec_tot['TWh_Total'] > 0)]['Year']
    d = df_elec[(df_elec['Region'] == region) & (df_elec['Year'].isin(ok_years))]
    return d.groupby(['Year', 'Fuel'], as_index=False)['TWh'].sum()


r_tes = get_region_year(df_tes)
r_tes = r_tes[r_tes['EJ'] > 0]
primary_total_ej = get_region_year(df_tes_tot)['EJ'].sum() or r_tes['EJ'].sum()
r_elec_tot_val = get_region_year(df_elec_tot)['TWh_Total'].sum()
r_emis_val = get_region_year(df_emis)['MtCO2e'].sum()
r_pc_val = get_region_year(df_tes_pc)['GJ_capita'].sum()
r_cap = get_region_year(df_cap).copy()

elec_hist = elec_history(selected_region)
elec_mix_rows = elec_hist[(elec_hist['Year'] == selected_year) & (elec_hist['TWh'] > 0)]

# Popolazione dedotta da TES / TES pro capite
population_millions = (primary_total_ej * 1e9 / r_pc_val / 1e6) if r_pc_val > 0 else 0
elec_per_capita_mwh = (r_elec_tot_val / population_millions) if population_millions > 0 else 0  # TWh/Mpers = MWh/pers
emis_per_capita_t = (r_emis_val / population_millions) if population_millions > 0 else 0

st.header(f"Analisi: {region_label} ({selected_year})")
if primary_total_ej <= 0:
    st.warning(f"Nessun dato di energia primaria per {region_label} nel {selected_year}. "
               "Prova un altro anno: alcune serie (es. URSS) coprono solo alcuni periodi.")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Energia Primaria", f"{primary_total_ej:.1f} EJ")
m2.metric("Gen. Elettrica", f"{r_elec_tot_val:.1f} TWh" if r_elec_tot_val else "n.d.")
m3.metric("Emissioni CO2e", f"{r_emis_val:.1f} Mt" if r_emis_val else "n.d.")
m4.metric("Primaria pro capite", f"{r_pc_val:.1f} GJ/cap" if r_pc_val else "n.d.")
m5.metric("Elettricità pro capite", f"{elec_per_capita_mwh:.1f} MWh/cap" if elec_per_capita_mwh else "n.d.")
st.divider()

tab_stat, tab_trend, tab_sankey = st.tabs(["📊 Statistiche & Capacità", "📈 Trend, Marchetti & Ternary", "🔄 Sankeys Termodinamici"])

# --- TAB 1: STATISTICHE ---
with tab_stat:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Domanda Primaria (EJ)")
        if not r_tes.empty:
            fig_tes = px.pie(r_tes.assign(Fonte=r_tes['Fuel'].map(fuel_it)), values='EJ', names='Fonte', hole=0.4,
                             color='Fuel', color_discrete_map=color_map)
            fig_tes.update_layout(showlegend=False)
            st.plotly_chart(fig_tes, width='stretch')
        else:
            st.info("Dati non disponibili.")
    with c2:
        st.subheader("Produzione Elettrica (TWh)")
        if not elec_mix_rows.empty:
            em = elec_mix_rows.sort_values('TWh', ascending=False).assign(Fonte=lambda d: d['Fuel'].map(fuel_it))
            fig_elec = px.bar(em, x='Fonte', y='TWh', color='Fuel', color_discrete_map=color_map)
            fig_elec.update_layout(showlegend=False, xaxis_title=None)
            st.plotly_chart(fig_elec, width='stretch')
        else:
            st.info("Dati elettrici non disponibili per l'anno selezionato (serie dal 1985).")
    with c3:
        st.subheader("Capacità Installata (GW)")
        if not r_cap.empty and r_cap['MW'].sum() > 0:
            r_cap['GW'] = r_cap['MW'] / 1000
            fig_cap = px.bar(r_cap.assign(Fonte=r_cap['Fuel'].map(fuel_it)), x='Fonte', y='GW',
                             color='Fuel', color_discrete_map=color_map)
            fig_cap.update_layout(showlegend=False, xaxis_title=None)
            st.plotly_chart(fig_cap, width='stretch')
        else:
            st.info("Dati di capacità Eolica/Solare non disponibili per l'area o l'anno selezionati (serie dal 2000).")

# --- TAB 2: TREND, MARCHETTI E TERNARIO ---
with tab_trend:
    st.subheader("Emissioni Storiche (MtCO2e)")
    df_em_reg = df_emis[(df_emis['Region'] == selected_region) & (df_emis['MtCO2e'] > 0)]
    if not df_em_reg.empty:
        fig_em = px.area(df_em_reg, x='Year', y='MtCO2e', color_discrete_sequence=['#4B5563'])
        st.plotly_chart(fig_em, width='stretch')
    else:
        st.info("Emissioni non disponibili per quest'area.")

    st.divider()
    c_m1, c_m2 = st.columns(2)
    df_tes_h = df_tes[df_tes['Region'] == selected_region].copy()

    with c_m1:
        st.subheader("Sostituzione Fonti Primarie (Marchetti)")
        st.markdown("Asse Y: $log_{10}(f / (1-f))$ dove $f$ è la quota di mercato.")
        if not df_tes_h.empty:
            tot_y = df_tes_h.groupby('Year')['EJ'].sum().rename('Total').reset_index()
            d = pd.merge(df_tes_h, tot_y, on='Year')
            d = d[(d['Total'] > 0) & (d['EJ'] > 0)]
            d['f'] = np.clip(d['EJ'] / d['Total'], 0.0001, 0.9999)
            d['Marchetti'] = np.log10(d['f'] / (1 - d['f']))
            fig_m1 = px.line(d, x='Year', y='Marchetti', color='Fuel', color_discrete_map=color_map)
            fig_m1.update_layout(yaxis_title="log(f / 1-f)")
            st.plotly_chart(fig_m1, width='stretch')

    with c_m2:
        st.subheader("Evoluzione Mix Elettrico (Marchetti)")
        st.markdown("Competizione tra le fonti nella generazione elettrica.")
        d = elec_hist[elec_hist['TWh'] > 0].copy()
        if not d.empty:
            d = d.merge(d.groupby('Year')['TWh'].sum().rename('Total').reset_index(), on='Year')
            d['f'] = np.clip(d['TWh'] / d['Total'], 0.0001, 0.9999)
            d['Marchetti'] = np.log10(d['f'] / (1 - d['f']))
            fig_m2 = px.line(d, x='Year', y='Marchetti', color='Fuel', color_discrete_map=color_map)
            fig_m2.update_layout(yaxis_title="log(f / 1-f)")
            st.plotly_chart(fig_m2, width='stretch')

    st.subheader("La rotta verso l'Elettrificazione (Ternary Plot)")
    st.markdown("Quote dell'energia primaria: Fossili, fonti 'elettriche' (nucleare, idro, solare, eolico) "
                "e Biomasse/Altro. Metodo EI: rinnovabili elettriche contate 1:1, nucleare a rendimento 33%.")
    if not df_tes_h.empty:
        p = df_tes_h.pivot_table(index='Year', columns='Fuel', values='EJ', aggfunc='sum').fillna(0)
        p['Total'] = p.sum(axis=1)
        p = p[p['Total'] > 0]
        g = lambda c: p[c] if c in p else 0
        p['Fossil'] = g('Coal') + g('Natural Gas') + g('Oil')
        p['Bio & Other'] = g('Biomass/Geo') + g('Biofuels')
        p['Electrons'] = g('Nuclear') + g('Hydro') + g('Solar') + g('Wind')
        for col in ['Fossil', 'Bio & Other', 'Electrons']:
            p[col] = p[col] / p['Total'] * 100
        p = p.reset_index()
        fig_t = px.scatter_ternary(p, a="Fossil", b="Electrons", c="Bio & Other", hover_name="Year", color="Year")
        fig_t.update_traces(mode="lines+markers", line=dict(color='#22C55E', width=2), marker=dict(size=6))
        st.plotly_chart(fig_t, width='stretch')


# --- TAB 3: SANKEYS ---
def rgba(hex_color, alpha):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


LOSS = '#EF4444'
ELEC = '#EAB308'
MOL = '#6B7280'


class SankeyBuilder:
    """Costruisce un Sankey a colonne fisse, salta flussi nulli, etichette con EJ e %."""

    def __init__(self, ref_total, fixed=False):
        self.fixed = fixed
        self.ref = ref_total if ref_total > 0 else 1
        self.nodes, self.links = {}, []

    def node(self, key, label, color, col, order):
        self.nodes.setdefault(key, dict(label=label, color=color, col=col, order=order))

    def link(self, s, t, v, color):
        if v is not None and v > 1e-4:
            self.links.append((s, t, float(v), color))

    def figure(self, height, n_cols):
        # ordine dei flussi = ordine verticale dei nodi: riduce gli incroci
        nd = self.nodes
        self.links.sort(key=lambda l: (nd[l[0]]['col'], nd[l[0]]['order'], nd[l[1]]['col'], nd[l[1]]['order']))
        used = [k for k in self.nodes if any(k in (l[0], l[1]) for l in self.links)]
        idx = {k: i for i, k in enumerate(used)}
        val = {k: max(sum(l[2] for l in self.links if l[1] == k), sum(l[2] for l in self.links if l[0] == k))
               for k in used}
        # posizioni: colonne fisse, nodi impilati per ordine dichiarato
        xs, ys = {}, {}
        for c in range(n_cols):
            col_nodes = sorted([k for k in used if self.nodes[k]['col'] == c], key=lambda k: self.nodes[k]['order'])
            tot = sum(val[k] for k in col_nodes) or 1
            gap = 0.04
            span = 1 - gap * max(len(col_nodes) - 1, 0)
            y = 0.0
            for k in col_nodes:
                h = val[k] / tot * span
                xs[k] = 0.001 if c == 0 else (0.999 if c == n_cols - 1 else c / (n_cols - 1))
                ys[k] = min(max(y + h / 2, 0.01), 0.985)
                y += h + gap
        labels, hover = [], []
        for k in used:
            n = self.nodes[k]
            pct = val[k] / self.ref * 100
            v_txt = f"{val[k]:.1f}" if val[k] >= 1 else f"{val[k]:.2f}"
            labels.append(f"{n['label']}  {v_txt} EJ ({pct:.0f}%)")
            hover.append(f"<b>{n['label']}</b><br>{val[k]:.2f} EJ — {pct:.1f}% della primaria")
        fig = go.Figure(go.Sankey(
            arrangement='fixed' if self.fixed else 'snap',
            valueformat='.2f', valuesuffix=' EJ',
            node=dict(pad=18, thickness=18, label=labels, align='left', color=[self.nodes[k]['color'] for k in used],
                      **(dict(x=[xs[k] for k in used], y=[ys[k] for k in used]) if self.fixed else {}),
                      customdata=hover, hovertemplate='%{customdata}<extra></extra>',
                      line=dict(width=0)),
            link=dict(source=[idx[l[0]] for l in self.links], target=[idx[l[1]] for l in self.links],
                      value=[l[2] for l in self.links], color=[l[3] for l in self.links],
                      customdata=[[self.nodes[l[0]]['label'], self.nodes[l[1]]['label']] for l in self.links],
                      hovertemplate='%{customdata[0]} → %{customdata[1]}<br><b>%{value:.2f} EJ</b><extra></extra>'),
        ))
        fig.update_traces(textfont=dict(size=13, color='#111827', shadow='1px 1px 2px white, -1px -1px 2px white'))
        fig.update_layout(height=height, margin=dict(t=30, b=30, l=10, r=10))
        return fig


with tab_sankey:
    if elec_mix_rows.empty or r_tes.empty:
        st.info("Per i Sankey servono sia l'energia primaria sia il mix elettrico: "
                "dati elettrici disponibili dal 1985 e non per tutte le aree residue.")
    else:
        st.markdown(
            "**Come leggere i diagrammi.** Da sinistra a destra: fonti primarie → vettori "
            "(elettricità e combustibili usati direttamente) → usi finali. Ogni nodo riporta EJ e "
            "quota sull'energia primaria. I flussi **rossi** (in basso) sono perdite. "
            "I dati primari ed elettrici sono EI; rendimenti e ripartizioni a valle sono **ipotesi** "
            "modificabili qui sotto e uguali per tutti i paesi."
        )
        with st.expander("⚙️ Ipotesi del modello", expanded=False):
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**Rendimento centrali fossili**")
                eta = {
                    'Coal': st.slider("Carbone", 0.25, 0.50, 0.37, 0.01),
                    'Natural Gas': st.slider("Gas", 0.30, 0.60, 0.45, 0.01),
                    'Oil': st.slider("Petrolio", 0.25, 0.50, 0.33, 0.01),
                }
                st.caption("Nucleare e biomasse/geo: input = consumo primario EI. "
                           "Idro/solare/eolico: 1:1 (metodo EI).")
            with a2:
                st.markdown("**Perdite a monte degli usi finali**")
                grid_loss = st.slider("Rete e autoconsumi elettrici", 0.0, 0.20, 0.08, 0.01)
                mol_up_loss = st.slider("Filiera combustibili (raffinazione, trasporto, autoconsumi)", 0.0, 0.30, 0.15, 0.01)
                non_energy = st.slider("Combustibili per usi non energetici (materia prima)", 0.0, 0.30, 0.12, 0.01)
            with a3:
                st.markdown("**Rendimento negli usi finali**")
                el_work_share = st.slider("Elettricità: quota per lavoro/servizi", 0.0, 1.0, 0.77, 0.01)
                el_work_eff = st.slider("Elettricità: rendimento lavoro", 0.3, 1.0, 0.68, 0.01)
                el_heat_eff = st.slider("Elettricità: rendimento calore", 0.5, 4.0, 0.91, 0.01,
                                        help="Valori >1 rappresentano pompe di calore (COP).")
                mol_work_share = st.slider("Combustibili: quota per lavoro (motori)", 0.0, 1.0, 0.48, 0.01)
                mol_work_eff = st.slider("Combustibili: rendimento lavoro", 0.1, 0.6, 0.29, 0.01)
                mol_heat_eff = st.slider("Combustibili: rendimento calore", 0.3, 1.0, 0.64, 0.01)
            st.markdown("**Ripartizione per settore (diagramma 2)**")
            b1, b2 = st.columns(2)
            with b1:
                st.caption("Elettricità finale (%)")
                e_tr = st.number_input("Trasporti", 0, 100, 2, key='e_tr')
                e_in = st.number_input("Industria", 0, 100, 43, key='e_in')
                e_bu = st.number_input("Edifici/Civile", 0, 100, 55, key='e_bu')
            with b2:
                st.caption("Combustibili finali, usi energetici (%)")
                m_tr = st.number_input("Trasporti", 0, 100, 45, key='m_tr')
                m_in = st.number_input("Industria", 0, 100, 33, key='m_in')
                m_bu = st.number_input("Edifici/Civile", 0, 100, 22, key='m_bu')

        def norm(*v):
            s = sum(v)
            return [x / s for x in v] if s > 0 else [1 / len(v)] * len(v)

        e_split = norm(e_tr, e_in, e_bu)
        m_split = norm(m_tr, m_in, m_bu)

        # --- Bilancio per fonte ---
        pe = {f: r_tes.loc[r_tes['Fuel'] == f, 'EJ'].sum() for f in color_map}
        el = {f: elec_mix_rows.loc[elec_mix_rows['Fuel'] == f, 'TWh'].sum() * TWH_TO_EJ for f in color_map}

        to_power, conv_loss, direct = {}, {}, {}
        for f in color_map:
            e = el[f]
            if f in ('Hydro', 'Solar', 'Wind', 'Other'):
                inp = e
            elif f in ('Nuclear', 'Biomass/Geo'):
                inp = max(pe[f], e)
            elif f in eta:
                inp = min(pe[f], e / eta[f]) if e > 0 else 0.0
                inp = max(inp, e)
            else:
                inp = 0.0
            to_power[f] = inp
            conv_loss[f] = inp - e
            direct[f] = max(0.0, pe[f] - inp) if f not in ('Hydro', 'Solar', 'Wind', 'Other') else 0.0

        E_gen = sum(el.values())
        E_grid_loss = E_gen * grid_loss
        E_fin = E_gen - E_grid_loss
        M_dir = sum(direct.values())
        M_up_loss = M_dir * mol_up_loss
        M_fin = M_dir - M_up_loss
        M_nonen = M_fin * non_energy
        M_energy = M_fin - M_nonen

        el_w, el_h = E_fin * el_work_share, E_fin * (1 - el_work_share)
        mol_w, mol_h = M_energy * mol_work_share, M_energy * (1 - mol_work_share)
        useful_work = el_w * el_work_eff + mol_w * mol_work_eff
        useful_heat = el_h * el_heat_eff + mol_h * mol_heat_eff
        end_loss = max(0.0, el_w * (1 - el_work_eff) + el_h * (1 - el_heat_eff)) + mol_w * (1 - mol_work_eff) + mol_h * (1 - mol_heat_eff)
        # con pompe di calore (COP>1) il calore ambiente entra come input aggiuntivo
        ambient = max(0.0, el_h * (el_heat_eff - 1))

        total_in = sum(pe.values()) + el['Other']
        tot_loss = sum(conv_loss.values()) + E_grid_loss + M_up_loss + end_loss

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Energia utile / primaria", f"{(useful_work + useful_heat) / total_in * 100:.0f}%")
        k2.metric("Perdite totali", f"{tot_loss:.1f} EJ", f"{tot_loss / total_in * 100:.0f}% della primaria", delta_color="off")
        k3.metric("Perdite nelle centrali", f"{sum(conv_loss.values()):.1f} EJ")
        k4.metric("Quota elettrica negli usi finali", f"{E_fin / (E_fin + M_fin) * 100:.0f}%" if (E_fin + M_fin) else "n.d.")

        # --- 1. SANKEY: primaria -> vettori -> energia utile ---
        st.subheader("1. Dalla primaria all'energia utile")
        st.caption("Fonti raggruppate. Colonna centrale: elettricità generata, combustibili usati direttamente "
                   "e perdite di trasformazione nelle centrali. A destra: servizio energetico effettivamente reso.")
        groups = [
            ('Idro, solare, eolico', ['Hydro', 'Solar', 'Wind'], '#16A34A'),
            ('Altro (pompaggi, rifiuti)', ['Other'], '#9CA3AF'),
            ('Fossili', ['Coal', 'Oil', 'Natural Gas'], '#374151'),
            ('Biomasse, geo, biocarburanti', ['Biomass/Geo', 'Biofuels'], color_map['Biomass/Geo']),
            ('Nucleare', ['Nuclear'], color_map['Nuclear']),
        ]
        sb = SankeyBuilder(total_in)
        for i, (name, fuels, colr) in enumerate(groups):
            sb.node(name, name, colr, 0, i)
            sb.link(name, 'elec', sum(el[f] for f in fuels), rgba(colr, 0.45))
            sb.link(name, 'mol', sum(direct[f] for f in fuels), rgba(colr, 0.45))
            sb.link(name, 'conv', sum(conv_loss[f] for f in fuels), rgba(LOSS, 0.35))
        sb.node('elec', 'Elettricità', ELEC, 1, 0)
        sb.node('ambient', 'Calore ambiente (pompe di calore)', '#60A5FA', 1, 1)
        sb.node('mol', 'Combustibili (uso diretto)', MOL, 1, 2)
        sb.node('conv', 'Perdite nelle centrali', LOSS, 1, 3)
        sb.node('work', 'Lavoro utile (moto, servizi)', '#2563EB', 2, 0)
        sb.node('heat', 'Calore utile', '#F97316', 2, 1)
        sb.node('nonen', 'Usi non energetici (materia)', '#A8A29E', 2, 2)
        sb.node('loss2', 'Perdite a valle (rete, filiera, usi finali)', LOSS, 2, 3)
        sb.link('elec', 'loss2', E_grid_loss + el_w * (1 - el_work_eff) + el_h * max(0.0, 1 - el_heat_eff), rgba(LOSS, 0.35))
        sb.link('elec', 'work', el_w * el_work_eff, rgba(ELEC, 0.5))
        sb.link('elec', 'heat', el_h * min(el_heat_eff, 1.0), rgba(ELEC, 0.5))
        sb.link('ambient', 'heat', ambient, rgba('#60A5FA', 0.4))
        sb.link('mol', 'loss2', M_up_loss + mol_w * (1 - mol_work_eff) + mol_h * (1 - mol_heat_eff), rgba(LOSS, 0.35))
        sb.link('mol', 'work', mol_w * mol_work_eff, rgba(MOL, 0.45))
        sb.link('mol', 'heat', mol_h * mol_heat_eff, rgba(MOL, 0.45))
        sb.link('mol', 'nonen', M_nonen, rgba(MOL, 0.3))
        st.plotly_chart(sb.figure(520, 3), width='stretch')

        st.divider()

        # --- 2. SANKEY: fonti -> vettori -> settori ---
        st.subheader("2. Dalle fonti ai settori finali")
        st.caption("Fonti in dettaglio. Le perdite nelle centrali partono dalla fonte che le genera; "
                   "la ripartizione per settore è un'ipotesi (vedi ⚙️).")
        order = ['Hydro', 'Wind', 'Solar', 'Other', 'Oil', 'Biofuels', 'Natural Gas', 'Coal', 'Biomass/Geo', 'Nuclear']
        sb2 = SankeyBuilder(total_in)
        for i, f in enumerate(order):
            sb2.node(f, fuel_it[f], color_map[f], 0, i)
            sb2.link(f, 'elec', el[f], rgba(color_map[f], 0.5))
            sb2.link(f, 'mol', direct[f], rgba(color_map[f], 0.5))
            sb2.link(f, 'conv', conv_loss[f], rgba(LOSS, 0.35))
        sb2.node('elec', 'Elettricità', ELEC, 1, 0)
        sb2.node('mol', 'Combustibili (uso diretto)', MOL, 1, 1)
        sb2.node('conv', 'Perdite nelle centrali', LOSS, 1, 2)
        sb2.node('dist', 'Perdite di rete e filiera', LOSS, 2, 5)
        sb2.link('elec', 'dist', E_grid_loss, rgba(LOSS, 0.35))
        sb2.link('mol', 'dist', M_up_loss, rgba(LOSS, 0.35))
        # e_split / m_split sono nell'ordine Trasporti, Industria, Edifici
        sectors = [(2, 'bu', 'Edifici/Civile', '#10B981'), (1, 'in', 'Industria', '#F97316'), (0, 'tr', 'Trasporti', '#3B82F6')]
        for pos, (j, k, name, colr) in enumerate(sectors):
            sb2.node(k, name, colr, 2, pos)
            sb2.link('elec', k, E_fin * e_split[j], rgba(ELEC, 0.5))
            sb2.link('mol', k, M_energy * m_split[j], rgba(MOL, 0.45))
        sb2.node('nonen', 'Usi non energetici (materia)', '#A8A29E', 2, 3)
        sb2.link('mol', 'nonen', M_nonen, rgba(MOL, 0.3))
        st.plotly_chart(sb2.figure(650, 3), width='stretch')
