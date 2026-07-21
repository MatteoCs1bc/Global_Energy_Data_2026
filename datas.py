import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

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

# --- MAPPA COLORI ---
color_map = {
    'Coal': '#000000',        # Nero
    'Oil': '#4B5563',         # Grigio medio
    'Natural Gas': '#9CA3AF', # Grigio chiaro
    'Nuclear': '#9333EA',     # Viola
    'Hydro': '#3B82F6',       # Blu
    'Solar': '#FACC15',       # Giallo
    'Wind': '#22C55E',        # Verde
    'Biomass/Geo': '#8B4513', # Marrone
    'Other': '#D1D5DB'        # Grigio chiarissimo
}

# --- 2. FUNZIONI DI CARICAMENTO DATI ---
@st.cache_data
def load_data():
    file_path = "EI-Stats-Review-ALL-data (1).xlsx"
    
    def get_hist(sheet, val_name):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet, skiprows=2)
            df = df.rename(columns={df.columns[0]: 'Region'}).dropna(subset=['Region'])
            cols = [c for c in df.columns if isinstance(c, (int, float)) and 1960 < c <= 2025]
            df = df.melt(id_vars=['Region'], value_vars=cols, var_name='Year', value_name=val_name)
            df[val_name] = pd.to_numeric(df[val_name], errors='coerce').fillna(0)
            return df
        except: return pd.DataFrame()

    # Dati Primari (EJ)
    tes_oil = get_hist('Oil Consumption - EJ', 'EJ').assign(Fuel='Oil')
    tes_gas = get_hist('Gas Consumption - EJ', 'EJ').assign(Fuel='Natural Gas')
    tes_coal = get_hist('Coal Consumption - EJ', 'EJ').assign(Fuel='Coal')
    tes_nuc = get_hist('Nuclear Consumption - EJ', 'EJ').assign(Fuel='Nuclear')
    tes_hyd = get_hist('Hydro Consumption - EJ', 'EJ').assign(Fuel='Hydro')
    tes_sol = get_hist('Solar Consumption - EJ', 'EJ').assign(Fuel='Solar')
    tes_win = get_hist('Wind Consumption - EJ', 'EJ').assign(Fuel='Wind')
    tes_bio = get_hist('Geo Biomass Other - EJ', 'EJ').assign(Fuel='Biomass/Geo')
    df_tes = pd.concat([tes_oil, tes_gas, tes_coal, tes_nuc, tes_hyd, tes_sol, tes_win, tes_bio])

    # Dati Elettrici (TWh)
    el_nuc = get_hist('Nuclear Generation - TWh', 'TWh').assign(Fuel='Nuclear')
    el_hyd = get_hist('Hydro Generation - TWh', 'TWh').assign(Fuel='Hydro')
    el_sol = get_hist('Solar Generation - TWh', 'TWh').assign(Fuel='Solar')
    el_win = get_hist('Wind Generation - TWh', 'TWh').assign(Fuel='Wind')
    el_bio = get_hist('Geo Biomass Other - TWh', 'TWh').assign(Fuel='Biomass/Geo')
    el_tot = get_hist('Electricity Generation - TWh', 'TWh_Total')
    
    # Per i fossili storici usiamo un proxy proporzionale agli input
    in_oil = get_hist('Oil inputs - Elec generation ', 'In_EJ').assign(Fuel='Oil')
    in_gas = get_hist('Gas inputs - Elec generation', 'In_EJ').assign(Fuel='Natural Gas')
    in_coal = get_hist('Coal inputs - Elec generation ', 'In_EJ').assign(Fuel='Coal')
    df_in_fossils = pd.concat([in_oil, in_gas, in_coal])
    
    # Emissioni e Pro Capita
    df_emis = get_hist('CO2e Emissions ', 'MtCO2e')
    df_tes_pc = get_hist('TES per Capita', 'GJ_capita')
    
    # Capacità Installata
    cap_sol = get_hist('Solar Installed Capacity', 'MW').assign(Fuel='Solar')
    cap_win = get_hist('Wind Installed Capacity', 'MW').assign(Fuel='Wind')
    df_cap = pd.concat([cap_sol, cap_win])

    return df_tes, pd.concat([el_nuc, el_hyd, el_sol, el_win, el_bio]), el_tot, df_in_fossils, df_emis, df_tes_pc, df_cap

df_tes, df_elec_ren, df_elec_tot, df_in_fossils, df_emis, df_tes_pc, df_cap = load_data()
if df_tes.empty:
    st.stop()

# --- 3. SIDEBAR: FILTRI ---
st.sidebar.header("Impostazioni Analisi")
is_aggregate = df_tes['Region'].str.contains('Total|World|Union|OECD|Non-OECD', case=False, na=False)
view_type = st.sidebar.radio("Tipo di Area:", ("Stati Singoli", "Aggregati / Continenti"))

regions_list = df_tes[~is_aggregate]['Region'].unique() if view_type == "Stati Singoli" else df_tes[is_aggregate]['Region'].unique()
selected_region = st.sidebar.selectbox("Seleziona Area:", sorted([r for r in regions_list if r != 'Other']))

min_year, max_year = int(df_tes['Year'].min()), int(df_tes['Year'].max())
selected_year = st.sidebar.slider("Seleziona Anno:", min_value=min_year, max_value=max_year, value=max_year)

# --- 4. PREPARAZIONE DATI PER L'ANNO SELEZIONATO ---
def get_region_year(df, val_col):
    res = df[(df['Region'] == selected_region) & (df['Year'] == selected_year)]
    return res if not res.empty else pd.DataFrame(columns=df.columns)

r_tes = get_region_year(df_tes, 'EJ')
r_elec_ren = get_region_year(df_elec_ren, 'TWh')
r_elec_tot_val = get_region_year(df_elec_tot, 'TWh_Total')['TWh_Total'].sum()
r_in_fossils = get_region_year(df_in_fossils, 'In_EJ')
r_emis_val = get_region_year(df_emis, 'MtCO2e')['MtCO2e'].sum()
r_pc_val = get_region_year(df_tes_pc, 'GJ_capita')['GJ_capita'].sum()
r_cap = get_region_year(df_cap, 'MW')

# Ricostruzione Elettricità Fossile
ren_elec_twh = r_elec_ren['TWh'].sum()
fossil_elec_twh = max(0, r_elec_tot_val - ren_elec_twh)
tot_in_fossil = r_in_fossils['In_EJ'].sum()

elec_mix_rows = r_elec_ren.copy()
if tot_in_fossil > 0 and fossil_elec_twh > 0:
    for fuel in ['Oil', 'Natural Gas', 'Coal']:
        fuel_in = r_in_fossils[r_in_fossils['Fuel'] == fuel]['In_EJ'].sum()
        fuel_twh = fossil_elec_twh * (fuel_in / tot_in_fossil)
        elec_mix_rows = pd.concat([elec_mix_rows, pd.DataFrame([{'Region': selected_region, 'Year': selected_year, 'TWh': fuel_twh, 'Fuel': fuel}])])

primary_total_ej = r_tes['EJ'].sum()

# Calcolo Popolazione e Pro Capita
population_millions = (primary_total_ej * 1e9 / r_pc_val / 1e6) if r_pc_val > 0 else 0
elec_per_capita_mwh = (r_elec_tot_val * 1e6 / population_millions) if population_millions > 0 else 0
emis_per_capita_t = (r_emis_val / population_millions) if population_millions > 0 else 0

st.header(f"Analisi: {selected_region} ({selected_year})")

# Metriche
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Energia Primaria", f"{primary_total_ej:.1f} EJ")
m2.metric("Gen. Elettrica", f"{r_elec_tot_val:.1f} TWh")
m3.metric("Emissioni CO2e", f"{r_emis_val:.1f} Mt")
m4.metric("Primaria pro capite", f"{r_pc_val:.1f} GJ/cap")
m5.metric("Elettricità pro capite", f"{elec_per_capita_mwh:.1f} MWh/cap")
st.divider()

# --- TABS ---
tab_stat, tab_trend, tab_sankey = st.tabs(["📊 Statistiche & Capacità", "📈 Trend, Marchetti & Ternary", "🔄 Sankeys Termodinamici"])

# --- TAB 1: STATISTICHE ---
with tab_stat:
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.subheader("Domanda Primaria (EJ)")
        if not r_tes.empty:
            fig_tes = px.pie(r_tes, values='EJ', names='Fuel', hole=0.4, color='Fuel', color_discrete_map=color_map)
            fig_tes.update_layout(showlegend=False)
            st.plotly_chart(fig_tes, use_container_width=True)
            
    with c2:
        st.subheader("Produzione Elettrica (TWh)")
        if not elec_mix_rows.empty:
            fig_elec = px.bar(elec_mix_rows, x='Fuel', y='TWh', color='Fuel', color_discrete_map=color_map)
            fig_elec.update_layout(showlegend=False)
            st.plotly_chart(fig_elec, use_container_width=True)
            
    with c3:
        st.subheader("Capacità Installata (GW)")
        if not r_cap.empty and r_cap['MW'].sum() > 0:
            r_cap['GW'] = r_cap['MW'] / 1000
            fig_cap = px.bar(r_cap, x='Fuel', y='GW', color='Fuel', color_discrete_map=color_map)
            fig_cap.update_layout(showlegend=False)
            st.plotly_chart(fig_cap, use_container_width=True)
        else:
            st.info("Dati di capacità Eolica/Solare non disponibili per l'anno selezionato.")

# --- TAB 2: TREND, MARCHETTI E TERNARIO ---
with tab_trend:
    st.subheader("Emissioni Storiche e Intensità (MtCO2e)")
    df_em_reg = df_emis[df_emis['Region'] == selected_region]
    if not df_em_reg.empty:
        fig_em = px.area(df_em_reg, x='Year', y='MtCO2e', color_discrete_sequence=['#4B5563'])
        st.plotly_chart(fig_em, use_container_width=True)

    st.divider()
    c_m1, c_m2 = st.columns(2)
    
    with c_m1:
        st.subheader("Sostituzione Fonti Primarie (Marchetti)")
        st.markdown("Asse Y: $log_{10}(f / (1-f))$ dove $f$ è la quota di mercato.")
        df_tes_h = df_tes[df_tes['Region'] == selected_region].copy()
        if not df_tes_h.empty:
            tot_y = df_tes_h.groupby('Year')['EJ'].sum().reset_index().rename(columns={'EJ':'Total'})
            df_tes_h = pd.merge(df_tes_h, tot_y, on='Year')
            df_tes_h = df_tes_h[df_tes_h['Total'] > 0]
            df_tes_h['f'] = np.clip(df_tes_h['EJ'] / df_tes_h['Total'], 0.0001, 0.9999)
            df_tes_h['Marchetti'] = np.log10(df_tes_h['f'] / (1 - df_tes_h['f']))
            fig_m1 = px.line(df_tes_h, x='Year', y='Marchetti', color='Fuel', color_discrete_map=color_map)
            fig_m1.update_layout(yaxis_title="log(f / 1-f)")
            st.plotly_chart(fig_m1, use_container_width=True)

    with c_m2:
        st.subheader("Evoluzione Mix Elettrico (Marchetti)")
        st.markdown("Competizione tra le fonti nella generazione elettrica.")
        df_elec_ren_h = df_elec_ren[df_elec_ren['Region'] == selected_region].copy()
        df_elec_tot_h = df_elec_tot[df_elec_tot['Region'] == selected_region].copy()
        df_in_foss_h = df_in_fossils[df_in_fossils['Region'] == selected_region].copy()
        
        if not df_elec_ren_h.empty and not df_elec_tot_h.empty:
            merged_elec_h = []
            for y in df_elec_tot_h['Year'].unique():
                tot_e = df_elec_tot_h[df_elec_tot_h['Year']==y]['TWh_Total'].sum()
                ren_y = df_elec_ren_h[df_elec_ren_h['Year']==y]
                foss_in_y = df_in_foss_h[df_in_foss_h['Year']==y]
                
                ren_twh = ren_y['TWh'].sum()
                foss_twh = max(0, tot_e - ren_twh)
                tot_in = foss_in_y['In_EJ'].sum()
                
                for _, row in ren_y.iterrows():
                    merged_elec_h.append({'Year': y, 'Fuel': row['Fuel'], 'TWh': row['TWh']})
                
                if tot_in > 0 and foss_twh > 0:
                    for _, row in foss_in_y.iterrows():
                        merged_elec_h.append({'Year': y, 'Fuel': row['Fuel'], 'TWh': foss_twh * (row['In_EJ']/tot_in)})
                        
            df_elec_hist_full = pd.DataFrame(merged_elec_h)
            tot_e_y = df_elec_hist_full.groupby('Year')['TWh'].sum().reset_index().rename(columns={'TWh':'Total'})
            df_elec_hist_full = pd.merge(df_elec_hist_full, tot_e_y, on='Year')
            df_elec_hist_full = df_elec_hist_full[df_elec_hist_full['Total'] > 0]
            df_elec_hist_full['f'] = np.clip(df_elec_hist_full['TWh'] / df_elec_hist_full['Total'], 0.0001, 0.9999)
            df_elec_hist_full['Marchetti'] = np.log10(df_elec_hist_full['f'] / (1 - df_elec_hist_full['f']))
            
            fig_m2 = px.line(df_elec_hist_full, x='Year', y='Marchetti', color='Fuel', color_discrete_map=color_map)
            fig_m2.update_layout(yaxis_title="log(f / 1-f)")
            st.plotly_chart(fig_m2, use_container_width=True)

    st.subheader("La rotta verso l'Elettrificazione (Ternary Plot)")
    st.markdown("Quota stimata della domanda: Fossili, Elettroni e Biomassa/Altro (Ember Style).")
    if not df_tes_h.empty:
        pivot_df = df_tes_h.pivot_table(index='Year', columns='Fuel', values='EJ', aggfunc='sum').fillna(0)
        pivot_df['Total'] = pivot_df.sum(axis=1)
        pivot_df['Fossil'] = pivot_df.get('Coal',0) + pivot_df.get('Natural Gas',0) + pivot_df.get('Oil',0)
        pivot_df['Bio & Other'] = pivot_df.get('Biomass/Geo',0)
        pivot_df['Electrons'] = pivot_df.get('Nuclear',0) + pivot_df.get('Hydro',0) + pivot_df.get('Solar',0) + pivot_df.get('Wind',0)
        
        for col in ['Fossil', 'Bio & Other', 'Electrons']:
            pivot_df[col] = pivot_df[col] / pivot_df['Total'] * 100
            
        pivot_df = pivot_df.reset_index()
        fig_t = px.scatter_ternary(pivot_df, a="Fossil", b="Electrons", c="Bio & Other", hover_name="Year", color="Year")
        fig_t.update_traces(mode="lines+markers", line=dict(color='#22C55E', width=2), marker=dict(size=6))
        st.plotly_chart(fig_t, use_container_width=True)

# --- TAB 3: SANKEYS ---
with tab_sankey:
    if not elec_mix_rows.empty and not r_tes.empty:
        def get_val(df, col_name, fuel, default=0):
            val = df[df['Fuel'] == fuel][col_name].sum()
            return val if pd.notnull(val) else default

        # Estrazione Valori
        pe_hydro = get_val(r_tes, 'EJ', 'Hydro')
        pe_solar = get_val(r_tes, 'EJ', 'Solar')
        pe_wind = get_val(r_tes, 'EJ', 'Wind')
        pe_bio = get_val(r_tes, 'EJ', 'Biomass/Geo')
        pe_nuc = get_val(r_tes, 'EJ', 'Nuclear')
        pe_coal = get_val(r_tes, 'EJ', 'Coal')
        pe_oil = get_val(r_tes, 'EJ', 'Oil')
        pe_gas = get_val(r_tes, 'EJ', 'Natural Gas')
        
        el_hydro = get_val(elec_mix_rows, 'TWh', 'Hydro') * 0.0036
        el_solar = get_val(elec_mix_rows, 'TWh', 'Solar') * 0.0036
        el_wind = get_val(elec_mix_rows, 'TWh', 'Wind') * 0.0036
        el_bio = get_val(elec_mix_rows, 'TWh', 'Biomass/Geo') * 0.0036
        el_nuc = get_val(elec_mix_rows, 'TWh', 'Nuclear') * 0.0036
        el_coal = get_val(elec_mix_rows, 'TWh', 'Coal') * 0.0036
        el_oil = get_val(elec_mix_rows, 'TWh', 'Oil') * 0.0036
        el_gas = get_val(elec_mix_rows, 'TWh', 'Natural Gas') * 0.0036

        pe_electro = pe_hydro + pe_solar + pe_wind
        pe_therm = pe_coal + pe_oil + pe_gas + pe_nuc + pe_bio
        
        elec_from_electro = el_hydro + el_solar + el_wind
        elec_from_thermal = el_coal + el_oil + el_gas + el_nuc + el_bio
        
        eff_el, eff_th = 0.92, 0.29
        
        in_el = min(pe_electro, elec_from_electro / eff_el) if elec_from_electro > 0 else 0
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
        
        # --- 1. SANKEY EMBER (Primaria -> Utile) ---
        st.subheader("1. Flusso Primaria -> Energia Utile")
        nodes1 = ["Electro (Rinn/Idro)", "Termiche (Foss/Nuc/Bio)", "Elettroni", "Molecole", "Lavoro Utile", "Calore Utile", "Energia Persa"]
        colors1 = ['#22C55E', '#4B5563', '#FACC15', '#9CA3AF', '#3B82F6', '#F97316', 'rgba(239, 68, 68, 0.5)']
        
        link_colors1 = ['#FACC15', 'rgba(239, 68, 68, 0.3)', '#FACC15', '#000000', 'rgba(239, 68, 68, 0.3)',
                        '#FACC15', '#FACC15', 'rgba(239, 68, 68, 0.3)', '#000000', '#000000', 'rgba(239, 68, 68, 0.3)']

        fig_s1 = go.Figure(data=[go.Sankey(
            node=dict(pad=20, thickness=25, label=nodes1, color=colors1),
            link=dict(source=[0,0,1,1,1,2,2,2,3,3,3], target=[2,6,2,3,6,4,5,6,4,5,6], 
                      value=[elec_from_electro, w_el, elec_from_thermal, f_mol, w_th+w_mol, el_w*0.68, el_h*0.91, el_w*0.32+el_h*0.09, mol_w*0.29, mol_h*0.64, mol_w*0.71+mol_h*0.36],
                      color=link_colors1)
        )])
        fig_s1.update_layout(height=450, margin=dict(t=20, b=20))
        st.plotly_chart(fig_s1, use_container_width=True)

        st.divider()

        # --- 2. SANKEY SETTORIALE (Primaria -> Fonti -> Settori) ---
        st.subheader("2. Flusso Primaria -> Settori Finali")
        st.markdown("I flussi verso i settori sono stime proxy (Modello Ember). **Colori:** Elettricità (Giallo), Fossili (Nero), Perdite Termodinamiche (Rosso).")
        
        # Stima input termici per la generazione
        in_coal_el = el_coal / eff_th if el_coal > 0 else 0
        in_gas_el = el_gas / eff_th if el_gas > 0 else 0
        in_oil_el = el_oil / eff_th if el_oil > 0 else 0
        in_nuc_el = el_nuc / eff_th if el_nuc > 0 else 0
        in_bio_el = el_bio / eff_th if el_bio > 0 else 0
        
        # Molecole dirette
        dir_coal = max(0, pe_coal - in_coal_el)
        dir_gas = max(0, pe_gas - in_gas_el)
        dir_oil = max(0, pe_oil - in_oil_el)
        dir_bio = max(0, pe_bio - in_bio_el)
        
        tot_dir = dir_coal + dir_gas + dir_oil + dir_bio
        
        nodes2 = ["Carbone", "Gas", "Petrolio", "Nucleare", "Biomasse", "Idro", "Solare", "Eolico", 
                  "Elettricità", "Molecole Dirette", "Trasporti", "Industria", "Edifici/Civile", "Perdite Termodinamiche"]
        
        colors2 = [color_map['Coal'], color_map['Natural Gas'], color_map['Oil'], color_map['Nuclear'], color_map['Biomass/Geo'], 
                   color_map['Hydro'], color_map['Solar'], color_map['Wind'], 
                   '#FACC15', '#4B5563', '#3B82F6', '#F97316', '#10B981', 'rgba(239, 68, 68, 0.5)']
        
        src2 = [0,1,2,3,4,5,6,7, 0,1,2,4, 8,8,8, 8, 9,9,9]
        tgt2 = [8,8,8,8,8,8,8,8, 9,9,9,9, 10,11,12, 13, 10,11,12]
        
        val2 = [
            el_coal, el_gas, el_oil, el_nuc, el_bio, el_hydro, el_solar, el_wind,
            dir_coal, dir_gas, dir_oil, dir_bio,
            el_tot * 0.05, el_tot * 0.45, el_tot * 0.50,
            (in_coal_el+in_gas_el+in_oil_el+in_nuc_el+in_bio_el) - (el_coal+el_gas+el_oil+el_nuc+el_bio) + w_el,
            tot_dir * 0.50, tot_dir * 0.30, tot_dir * 0.20
        ]
        
        link_colors2 = [
            '#FACC15', '#FACC15', '#FACC15', '#FACC15', '#FACC15', '#FACC15', '#FACC15', '#FACC15',
            '#000000', '#000000', '#000000', '#000000',
            '#FACC15', '#FACC15', '#FACC15', 'rgba(239, 68, 68, 0.4)',
            '#000000', '#000000', '#000000'
        ]

        fig_s2 = go.Figure(data=[go.Sankey(
            node=dict(pad=15, thickness=20, label=nodes2, color=colors2),
            link=dict(source=src2, target=tgt2, value=val2, color=link_colors2, hovertemplate='%{value:.1f} EJ<extra></extra>')
        )])
        fig_s2.update_layout(height=600, margin=dict(t=20, b=20))
        st.plotly_chart(fig_s2, use_container_width=True)
