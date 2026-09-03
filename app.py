# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.markdown("### 🩺 Ambulatório RNI")
    
    # Navegação
    pagina = st.radio("", ["📊 Dashboard", "👤 Pacientes"], label_visibility="collapsed")
    
    st.markdown("---")
    
    # Lista de pacientes (apenas quando estiver na página de Pacientes)
    if pagina == "👤 Pacientes":
        conn = get_connection()
        pacientes_raw = conn.execute("SELECT * FROM pacientes ORDER BY name").fetchall()
        conn.close()
        
        pacientes_sidebar = [dict(p) for p in pacientes_raw]
        
        if pacientes_sidebar:
            st.markdown("### Lista de Pacientes")
            
            # Inicializar estado
            if 'paciente_selecionado' not in st.session_state:
                st.session_state['paciente_selecionado'] = None
            
            # Exibir pacientes como botões clicáveis
            for p in pacientes_sidebar:
                qtd_meds = contar_medicamentos(p['meds'] or "")
                classificacao, classe_badge = classificar_polifarmacia(qtd_meds)
                
                is_active = st.session_state['paciente_selecionado'] == p['id']
                
                # Botão com estilo
                if is_active:
                    botao_label = f"🔵 **{p['name']}**"
                else:
                    botao_label = f"⚪ {p['name']}"
                
                if st.button(
                    botao_label,
                    key=f"sidebar_paciente_{p['id']}",
                    use_container_width=True,
                    help=f"{p['age']} anos | {p['indication']} | {classificacao}"
                ):
                    st.session_state['paciente_selecionado'] = p['id']
                    st.rerun()
        else:
            st.info("Nenhum paciente cadastrado.")
        
        st.markdown("---")
    
    # Cadastro de paciente
    with st.expander("➕ Cadastrar Paciente"):
        with st.form("form_add_paciente", clear_on_submit=True):
            novo_nome = st.text_input("Nome Completo:")
            nova_idade = st.number_input("Idade:", min_value=1, max_value=120, value=65)
            
            nova_indicacao = st.selectbox("Indicação:", INDICACOES_CLINICAS)
            if nova_indicacao == "Outra":
                nova_indicacao_final = st.text_input("Especifique:") or "Outra"
            else:
                nova_indicacao_final = nova_indicacao
            
            nova_faixa = st.selectbox("Faixa Alvo:", FAIXAS_TERAPEUTICAS)
            nova_dose = st.number_input("Dose Semanal (mg):", value=35.0, step=2.5)
            meds_iniciais = st.text_area("Medicamentos:", placeholder="Ex: Amiodarona, Omeprazol...")
            
            if st.form_submit_button("Salvar") and novo_nome:
                conn = get_connection()
                try:
                    conn.execute("""
                        INSERT INTO pacientes (name, age, indication, target, weekly_dose, meds)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (novo_nome.strip(), nova_idade, nova_indicacao_final, nova_faixa, nova_dose, meds_iniciais))
                    conn.commit()
                    st.success("✅ Paciente cadastrado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error(f"⚠️ Paciente '{novo_nome}' já existe!")
                finally:
                    conn.close()
    
    st.markdown("---")
    
    # Backup
    with st.expander("💾 Backup de Dados"):
        json_backup = exportar_backup()
        st.download_button(
            "📥 Exportar Backup",
            data=json_backup,
            file_name=f"backup_rni_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
        
        arquivo_upload = st.file_uploader("📤 Importar Backup", type=["json"])
        if arquivo_upload and st.button("🔄 Restaurar", use_container_width=True, type="primary"):
            sucesso, msg = importar_backup(arquivo_upload.read().decode("utf-8"))
            if sucesso:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
