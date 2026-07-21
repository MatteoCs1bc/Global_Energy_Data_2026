import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# --- 0. CONFIGURAZIONE PAGINA E INTESTAZIONE ---
st.set_page_config(page_title="Energy Data Explorer", layout="wide")
st.title("🌍 Energy Supply & Ember-Style Sankey")


# --- 1. CONFIGURAZIONE PAGINA E INTESTAZIONE ---
st.set_page_config(page_title="Energy Data Explorer", layout="wide")
st.title("🌍 Energy Supply, Transizione & Sankey")

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

# --- MAPPA COLORI ---
color_map = {
    'Coal': '#000000',        # Nero
    'Oil': '#555555',         # Grigio medio
    'Natural Gas': '#AAAAAA', # Grigio chiaro
    'Nuclear': '#9333EA',     # Viola
    'Hydro': '#3B82F6',       # Blu
    'Solar': '#FACC15',       # Giallo
    'Wind': '#22C55E',        # Verde
    'Biomass/Geo': '#8B4513', # Marrone
    'Renewables': '#22C55E',  # Verde generico
    'Other': '#D1D5DB'        # Grigio chiarissimo
}

# --- 2. FUNZIONI DI CARICAMENTO DATI ---
@st.cache_data
def load_data():
    file_path = "EI-Stats-Review-ALL-data (1).xlsx"
    
    # 1. Energia Primaria (TES) - Flussi 2024 vs 2025
    df_tes_raw = pd.read_excel(file_path, sheet_name='TES by fuel', skiprows=2)
    names = ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Total']
    df_24 = df_tes_raw.iloc[:, [0, 1, 2, 3, 4, 5, 6, 7]].copy()
    df_24.columns = names; df_24['Year'] = 2024
    df_25 = df_tes_raw.iloc[:, [0, 8, 9, 10, 11, 12, 13, 14]].copy()
    df_25.columns = names; df_25['Year'] = 2025
    df_tes_flows = pd.concat([df_24, df_25]).dropna(subset=['Region'])
    for col in names[1:]: df_tes_flows[col] = pd.to_numeric(df_tes_flows[col], errors='coerce').fillna(0)
    
    # 2. Generazione Elettrica 2025 (Indici corretti per TWh)
    try:
        df_elec_raw = pd.read_excel(file_path, sheet_name='Elec generation by fuel', skiprows=2)
        df_elec = df_elec_raw.iloc[:, [0, 9, 10, 11, 12, 13, 14, 15, 16]].copy()
        df_elec.columns = ['Region', 'Oil', 'Natural Gas', 'Coal', 'Nuclear', 'Hydro', 'Renewables', 'Other', 'Total']
        df_elec = df_elec.dropna(subset=['Region'])
        for col in df_elec.columns[1:]: df_elec[col] = pd.to_numeric(df_elec[col], errors='coerce').fillna(0)
    except: df_elec = pd.DataFrame()

    # Estrazione Dettaglio Rinnovabili (2025)
    def extract_ren_2025(sheet):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet, skiprows=2).iloc[:, [0, 61]]
            df.columns = ['Region', 'Value']
            return df.dropna().set_index('Region')['Value'].apply(pd.to_numeric, errors='coerce').fillna(0)
        except: return pd.Series(dtype=float)
    df_ren_breakdown = pd.DataFrame({'Solar': extract_ren_2025('Solar Generation - TWh'),
                                     'Wind': extract_ren_2025('Wind Generation - TWh'),
                                     'Biomass/Geo': extract_ren_2025('Geo Biomass Other - TWh')}).reset_index()

    # 3. Serie Storiche (Melted DataFrames)
    def get_hist(sheet, val_name='Value'):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet, skiprows=2).rename(columns={pd.read_excel(file_path, sheet_name=sheet, skiprows=2).columns[0]: 'Region'}).dropna(subset=['Region'])
            cols = [c for c in df.columns if isinstance(c, (int, float)) and 1900 < c < 2100]
            df = df.melt(id_vars=['Region'], value_vars=cols, var_name='Year', value_name=val_name)
            df[val_name] = pd.to_numeric(df[val_name], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame()

    # Storici specifici per Marchetti e Ternary
    def get_fuel_hist(sheet, fuel, is_elec=False):
        df = get_hist(sheet)
        if df.empty: return df
        df['Fuel'] = fuel
        df['Type'] = 'Electricity (TWh)' if is_elec else 'Primary (EJ)'
        return df

    hist_tes = pd.concat([
        get_fuel_hist('Oil Consumption - EJ', 'Oil'), get_fuel_hist('Gas Consumption - EJ', 'Natural Gas'),
        get_fuel_hist('Coal Consumption - EJ', 'Coal'), get_fuel_hist('Nuclear Consumption - EJ', 'Nuclear'),
        get_fuel_hist('Hydro Consumption - EJ', 'Hydro'), get_fuel_hist('Renewables Consumption -EJ', 'Renewables')
    ])
    
    hist_elec = pd.concat([
        get_fuel_hist('Electricity Generation - TWh', 'Total', True) # Semplificato per evitare caricamenti lenti, usiamo 'Elec generation by fuel' per i dettagli se necessario
    ])
    
    df_emis_hist = get_hist('CO2e Emissions ', 'Emissions_MtCO2e')
    
    return df_tes_flows, df_elec, df_ren_breakdown, hist_tes, hist_elec, df_emis_hist

df_tes_flows, df_elec, df_ren_breakdown, hist_tes, hist_elec, df_emis_hist = load_data()

# --- 3. SIDEBAR ---
st.sidebar.header("Impostazioni")
is_aggregate = df_tes_flows['Region'].str.contains('Total|World|Union|OECD|Non-OECD', case=False, na=False)
view_type = st.sidebar.radio("Analisi:", ("Stati Singoli", "Aggregati / Continenti"))

regions_list = df_tes_flows[~is_aggregate]['Region'].unique() if view_type == "Stati Singoli" else df_tes_flows[is_aggregate]['Region'].unique()
selected_region = st.sidebar.selectbox("Seleziona Area:", sorted([r for r in regions_list if r != 'Other']))

# --- 4. PREPARAZIONE DATI ---
reg_tes_25 = df_tes_flows[(df_tes_flows['Region'] == selected_region) & (df_tes_flows['Year'] == 2025)].iloc[0]
reg_tes_24 = df_tes_flows[(df_tes_flows['Region'] == selected_region) & (df_tes_flows['Year'] == 2024)].iloc[0]
reg_elec_data = df_elec[df_elec['Region'] == selected_region]
reg_elec_row = reg_elec_data.iloc[0] if not reg_elec_data.empty else None
reg_ren_data = df_ren_breakdown[df_ren_breakdown['Region'] == selected_region]
reg_ren_row = reg_ren_data.iloc[0] if not reg_ren_data.empty else None

primary_total = reg_tes_25['Total']
elec_total_twh = reg_elec_row['Total'] if reg_elec_row is not None else 0
rinnovabili_twh = (reg_elec_row['Hydro'] + reg_elec_row['Renewables']) if reg_elec_row is not None else 0

st.header(f"Dati: {selected_region}")

# --- TABS ---
tab_stat, tab_trend, tab_sankey = st.tabs(["📊 Statistiche & Capacità", "📈 Trend, Marchetti & Ternary", "🔄 Sankeys Termodinamici"])

# --- TAB 1: STATISTICHE ---
with tab_stat:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Energia Primaria (2025)", f"{primary_total:.2f} EJ")
    m2.metric("Generazione Elettrica", f"{elec_total_twh:.1f} TWh")
    m3.metric("Copertura Rinnovabile", f"{(rinnovabili_twh/elec_total_twh*100):.1f} %" if elec_total_twh > 0 else "0 %")
    m4.metric("Elettrificazione (EJ su EJ)", f"{(elec_total_twh*0.0036/primary_total*100):.1f} %" if primary_total > 0 else "0 %")
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Mix Energia Primaria (EJ)")
        sources = ['Coal', 'Natural Gas', 'Oil', 'Nuclear', 'Hydro', 'Renewables']
        tes_data = pd.DataFrame({'Fonte': sources, 'EJ': [reg_tes_25[s] for s in sources]})
        fig_tes = px.pie(tes_data, values='EJ', names='Fonte', hole=0.4, color='Fonte', color_discrete_map=color_map)
        st.plotly_chart(fig_tes, use_container_width=True)

    with c2:
        if reg_elec_row is not None and reg_ren_row is not None:
            st.subheader("Mix Generazione Elettrica (TWh)")
            elec_src_det = ['Coal', 'Natural Gas', 'Oil', 'Nuclear', 'Hydro', 'Biomass/Geo', 'Solar', 'Wind', 'Other']
            elec_vals = [reg_elec_row['Coal'], reg_elec_row['Natural Gas'], reg_elec_row['Oil'], reg_elec_row['Nuclear'], reg_elec_row['Hydro'],
                         reg_ren_row['Biomass/Geo'], reg_ren_row['Solar'], reg_ren_row['Wind'], reg_elec_row['Other']]
            elec_data = pd.DataFrame({'Fonte': elec_src_det, 'TWh': elec_vals})
            fig_elec = px.bar(elec_data, x='Fonte', y='TWh', color='Fonte', color_discrete_map=color_map)
            st.plotly_chart(fig_elec, use_container_width=True)


# --- TAB 2: TREND, MARCHETTI E TERNARIO ---
with tab_trend:
    st.subheader("Emissioni Storiche (MtCO2e)")
    df_em_reg = df_emis_hist[df_emis_hist['Region'] == selected_region]
    if not df_em_reg.empty:
        fig_em = px.area(df_em_reg, x='Year', y='Emissions_MtCO2e', color_discrete_sequence=['#4B5563'])
        st.plotly_chart(fig_em, use_container_width=True)

    c_m, c_t = st.columns(2)
    
    with c_m:
        st.subheader("Sostituzione delle Fonti (Stile Marchetti)")
        st.markdown("Asse Y logaritmico della frazione di mercato: $log_{10}(f / (1-f))$")
        df_tes_r = hist_tes[hist_tes['Region'] == selected_region].copy()
        if not df_tes_r.empty:
            total_per_year = df_tes_r.groupby('Year')['Value'].sum().reset_index().rename(columns={'Value':'Total'})
            df_tes_r = pd.merge(df_tes_r, total_per_year, on='Year')
            df_tes_r['f'] = np.clip(df_tes_r['Value'] / df_tes_r['Total'], 0.001, 0.999) # Clip per evitare log(0) e div/0
            df_tes_r['Marchetti'] = np.log10(df_tes_r['f'] / (1 - df_tes_r['f']))
            
            fig_m = px.line(df_tes_r, x='Year', y='Marchetti', color='Fuel', color_discrete_map=color_map)
            fig_m.update_layout(yaxis_title="log(f / 1-f)", xaxis_title="Anno")
            st.plotly_chart(fig_m, use_container_width=True)

    with c_t:
        st.subheader("La rotta verso l'Elettrificazione (Ternary Plot)")
        st.markdown("Quota stimata della domanda: Fossili Diretti, Elettricità (Electrons) e Biomasse (Bio/Other).")
        if not df_tes_r.empty:
            # Creiamo un proxy per il Ternary Plot (Ember style)
            # Electrons proxy = Energia Elettrica Prodotta + Import Netto (approssimato all'energia idro/nuc/rinnovabili se mancano dati diretti storici elettrici unificati, ma usiamo la quota stimata)
            # Per semplificare usiamo:
            # Fossil = (Coal + Oil + Gas) / Total
            # Bio & Other = Renewables / Total
            # L'elettrificazione la stimiamo estraendo una proxy.
            
            pivot_df = df_tes_r.pivot_table(index='Year', columns='Fuel', values='Value', aggfunc='sum').fillna(0)
            pivot_df['Total'] = pivot_df.sum(axis=1)
            
            # Approssimazione grossolana ad uso di dashboard esplorativa
            pivot_df['Fossil'] = pivot_df.get('Coal',0) + pivot_df.get('Natural Gas',0) + pivot_df.get('Oil',0)
            pivot_df['Bio & Other'] = pivot_df.get('Renewables',0)
            pivot_df['Electrons_Proxy'] = pivot_df.get('Nuclear',0) + pivot_df.get('Hydro',0) # Ipotizziamo queste come base puramente elettrica per differenziare la terza asse
            
            # Normalizziamo a 100
            for col in ['Fossil', 'Bio & Other', 'Electrons_Proxy']:
                pivot_df[col] = pivot_df[col] / pivot_df['Total'] * 100
                
            pivot_df = pivot_df.reset_index()
            
            fig_t = px.scatter_ternary(pivot_df, a="Fossil", b="Electrons_Proxy", c="Bio & Other", hover_name="Year", color="Year")
            fig_t.update_traces(mode="lines+markers", line=dict(color='#22C55E', width=2), marker=dict(size=6))
            st.plotly_chart(fig_t, use_container_width=True)


# --- TAB 3: SANKEYS ---
with tab_sankey:
    if reg_elec_row is not None:
        st.subheader("1. Da Primaria a Utile (Lavoro vs Calore)")
        st.markdown("Applica i ratei di conversione globale (Ember) ai dati locali.")
        
        pe_elec = reg_tes_25['Hydro'] + reg_tes_25['Renewables']
        pe_therm = reg_tes_25['Oil'] + reg_tes_25['Natural Gas'] + reg_tes_25['Coal'] + reg_tes_25['Nuclear']
        
        elec_from_electro = (reg_elec_row['Hydro'] + reg_elec_row['Renewables']) * 0.0036
        elec_from_thermal = (reg_elec_row['Oil'] + reg_elec_row['Natural Gas'] + reg_elec_row['Coal'] + reg_elec_row['Nuclear'] + reg_elec_row['Other']) * 0.0036
        
        eff_el, eff_th = 0.92, 0.29
        
        in_el = min(pe_elec, elec_from_electro / eff_el) if elec_from_electro > 0 else 0
        w_el = max(0, in_el - elec_from_electro)
        in_th = elec_from_thermal / eff_th if elec_from_thermal > 0 else 0
        w_th = max(0, in_th - elec_from_thermal)
        
        mol_in = max(0, pe_therm - in_th)
        f_mol = mol_in * 0.85
        w_mol = mol_in * 0.15
        
        el_tot = elec_from_electro + elec_from_thermal
        el_w, el_h = el_tot * 0.77, el_tot * 0.23
        mol_w, mol_h = f_mol * 0.48, f_mol * 0.52
        
        w_end = (el_w * 0.32) + (el_h * 0.09) + (mol_w * 0.71) + (mol_h * 0.36)
        
        nodes1 = ["Electro (Rinn/Idro)", "Termiche (Foss/Nuc)", "Elettroni", "Molecole", "Lavoro Utile", "Calore Utile", "Energia Persa"]
        colors1 = ['#3B82F6', '#555555', '#FACC15', '#AAAAAA', '#22C55E', '#F97316', 'rgba(239, 68, 68, 0.5)'] # Persa = Rosso trasparente, Elettricità = Gialla, Fossili = Grigio/Nero
        
        # Flussi colore: 0=Blue, 1=Grey, 2=Yellow, 3=Grey, 4/5=Green/Orange, 6=RedTransparent
        link_colors1 = ['#3B82F6', 'rgba(239, 68, 68, 0.3)', '#555555', '#555555', 'rgba(239, 68, 68, 0.3)',
                        '#FACC15', '#FACC15', 'rgba(239, 68, 68, 0.3)', '#AAAAAA', '#AAAAAA', 'rgba(239, 68, 68, 0.3)']

        fig_s1 = go.Figure(data=[go.Sankey(
            node=dict(pad=20, thickness=25, label=nodes1, color=colors1),
            link=dict(source=[0,0,1,1,1,2,2,2,3,3,3], target=[2,6,2,3,6,4,5,6,4,5,6], 
                      value=[elec_from_electro, w_el, elec_from_thermal, f_mol, w_th+w_mol, el_w*0.68, el_h*0.91, el_w*0.32+el_h*0.09, mol_w*0.29, mol_h*0.64, mol_w*0.71+mol_h*0.36],
                      color=link_colors1)
        )])
        fig_s1.update_layout(height=500, title_text="1. Sistema Energetico: Lavoro, Calore e Inefficienze")
        st.plotly_chart(fig_s1, use_container_width=True)

        st.divider()

        st.subheader("2. Da Primaria a Settori (Stima Proxy)")
        st.markdown("*(Nota: Il dataset non contiene la divisione per settori finali. I flussi verso Trasporti, Industria e Edifici sono stimati sui pesi medi globali Ember per dimostrazione).*")
        
        # Proxy settoriale (stima fittizia basata su ratei generali OECD)
        transp_share_mol, ind_share_mol, build_share_mol = 0.50, 0.30, 0.20
        transp_share_el, ind_share_el, build_share_el = 0.05, 0.45, 0.50

        nodes2 = ["Carbone", "Petrolio", "Gas", "Nucleare", "Rinnovabili/Idro", "Settore Elettrico", "Molecole Dirette", "Trasporti", "Industria", "Edifici/Civile", "Perdite Generazione"]
        colors2 = ['#000000', '#555555', '#AAAAAA', '#9333EA', '#22C55E', '#FACC15', '#555555', '#3B82F6', '#F97316', '#10B981', 'rgba(239, 68, 68, 0.5)']
        
        # Input alla generazione
        in_el_coal = reg_elec_row['Coal'] * 0.0036 / eff_th
        in_el_oil = reg_elec_row['Oil'] * 0.0036 / eff_th
        in_el_gas = reg_elec_row['Natural Gas'] * 0.0036 / eff_th
        in_el_nuc = reg_elec_row['Nuclear'] * 0.0036 / eff_th
        in_el_ren = min(pe_elec, elec_from_electro / eff_el)
        
        # Input molecole dirette
        dir_coal = max(0, reg_tes_25['Coal'] - in_el_coal)
        dir_oil = max(0, reg_tes_25['Oil'] - in_el_oil)
        dir_gas = max(0, reg_tes_25['Natural Gas'] - in_el_gas)
        
        tot_dir = dir_coal + dir_oil + dir_gas
        
        src = [0,1,2,3,4, 0,1,2, 5,5,5, 5, 6,6,6]
        tgt = [5,5,5,5,5, 6,6,6, 7,8,9, 10, 7,8,9]
        val = [
            in_el_coal, in_el_oil, in_el_gas, in_el_nuc, in_el_ren,
            dir_coal, dir_oil, dir_gas,
            el_tot * transp_share_el, el_tot * ind_share_el, el_tot * build_share_el,
            (in_el_coal+in_el_oil+in_el_gas+in_el_nuc+in_el_ren) - el_tot,
            tot_dir * transp_share_mol, tot_dir * ind_share_mol, tot_dir * build_share_mol
        ]
        
        link_colors2 = [
            '#000000', '#555555', '#AAAAAA', '#9333EA', '#22C55E',
            '#000000', '#555555', '#AAAAAA',
            '#FACC15', '#FACC15', '#FACC15', 'rgba(239, 68, 68, 0.4)',
            '#555555', '#555555', '#555555'
        ]

        fig_s2 = go.Figure(data=[go.Sankey(
            node=dict(pad=20, thickness=25, label=nodes2, color=colors2),
            link=dict(source=src, target=tgt, value=val, color=link_colors2, hovertemplate='%{value:.1f} EJ<extra></extra>')
        )])
        fig_s2.update_layout(height=550)
        st.plotly_chart(fig_s2, use_container_width=True)
