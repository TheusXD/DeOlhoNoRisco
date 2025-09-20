import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import qrcode
from io import BytesIO
import random
import time
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="De olho no risco", page_icon="🏆", layout="wide")

# --- CONFIGURAÇÕES E CONSTANTES ---
QUESTION_TIMER = 30
CORRECT_MESSAGES = ["Excelente!", "Mandou bem!", "Correto!", "Isso aí!", "Perfeito!"]
WRONG_MESSAGES = ["Não foi dessa vez.", "Quase lá!", "Ops!", "Resposta incorreta."]


# --- FUNÇÕES AUXILIARES E CONEXÃO ---
def df_to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Ranking')
    return output.getvalue()


@st.cache_resource
def connect_to_google_sheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
    except (FileNotFoundError, KeyError):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name("google_sheets_credentials.json", scopes)
        except FileNotFoundError:
            st.error("Credenciais não encontradas.")
            st.stop()
    return gspread.authorize(creds)


gsheets_client = connect_to_google_sheets()


@st.cache_data(ttl=60)
def load_data(sheet_id, sheet_name):
    try:
        sheet = gsheets_client.open_by_key(sheet_id).worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


def update_sheet_from_df(sheet_id, sheet_name, dataframe):
    try:
        sheet = gsheets_client.open_by_key(sheet_id).worksheet(sheet_name)
        sheet.clear()
        sheet.update([dataframe.columns.values.tolist()] + dataframe.values.tolist())
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar planilha: {e}")
        return False


def append_row_to_sheet(sheet_id, sheet_name, row_list):
    try:
        sheet = gsheets_client.open_by_key(sheet_id).worksheet(sheet_name)
        sheet.append_row(row_list)
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar linha: {e}")
        return False


# --- ESTILO CSS MELHORADO ---
def inject_custom_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* -------------------------
       1) FUNDO PRINCIPAL (FORÇA)
       ------------------------- */
    html, body, .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stAppViewContainer"] > .main {
        background-color: #064e3b !important;
        background-image:
            radial-gradient(circle at 20% 80%, rgba(16,185,129,0.07) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(5,150,105,0.06) 0%, transparent 50%),
            linear-gradient(135deg, #064e3b 0%, #065f46 50%, #047857 100%) !important;
        background-attachment: fixed !important;
        background-repeat: no-repeat !important;
        min-height: 100vh !important;
        position: relative !important;
    }

    /* Garante que área principal do Streamlit é transparente para deixar o gradiente visível */
    div[data-testid="stAppViewContainer"] .main, 
    div[data-testid="stAppViewContainer"] .block-container,
    .reportview-container .main, 
    .css-1d391kg, /* fallback para algumas versões */
    section.main {
        background: transparent !important;
        background-color: transparent !important;
    }

    /* Remove/neutraliza qualquer background inline dentro do app (aplica apenas ao app) */
    div[data-testid="stAppViewContainer"] *[style*="background"] {
        background-image: none !important;
        background-color: transparent !important;
    }

    /* -------------------------
       2) TEXTURA (leve)
       ------------------------- */
    div[data-testid="stAppViewContainer"]::before {
        content: '';
        position: fixed;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 0;
        background-image:
            repeating-linear-gradient(
                45deg,
                transparent,
                transparent 50px,
                rgba(255,255,255,0.012) 50px,
                rgba(255,255,255,0.012) 52px
            );
        mix-blend-mode: overlay;
    }

    /* -------------------------
       3) CAMADA DE CONTEÚDO
       ------------------------- */
    /* garante que conteúdos fiquem acima do background */
    div[data-testid="stAppViewContainer"] > .main, 
    div[data-testid="stAppViewContainer"] .block-container {
        position: relative !important;
        z-index: 1 !important;
    }

    /* -------------------------
       4) HEADER / FOOTER / MENU
       ------------------------- */
    header[data-testid="stHeader"], #MainMenu, footer, .stDeployButton {
        display: none !important;
        visibility: hidden !important;
    }

    /* -------------------------
       5) TIPOGRAFIA E CORES
       ------------------------- */
    body, .stApp {
        font-family: 'Inter', sans-serif !important;
        color: #fff !important;
    }

    /* Forçar cor branca em textos dentro de cards/containers */
    div[data-testid="stAppViewContainer"] .main * {
        color: #ffffff !important;
    }

    /* -------------------------
       6) BOTÕES E INPUTS (mantém legibilidade)
       ------------------------- */
    div.stButton > button, div.stDownloadButton > button {
        background: linear-gradient(135deg, #10b981 0%, #059669 50%, #047857 100%) !important;
        color: #fff !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        box-shadow: 0 6px 18px rgba(0,0,0,0.25) !important;
    }

    .stTextInput input, input, textarea, select {
        background: rgba(255,255,255,0.96) !important;
        color: #064e3b !important;
        border: 3px solid rgba(16,185,129,0.28) !important;
        border-radius: 12px !important;
    }

    /* -------------------------
       7) FALLBACKS: seletores que mudam entre versões do Streamlit
       ------------------------- */
    /* wildcard para classes dinâmicas que contenham "css-" */
    div[data-testid="stAppViewContainer"] [class*="css-"] {
        background: transparent !important;
    }

    /* impede que cards aplicados pelo Streamlit tornem o fundo sólido */
    div[data-testid="stAppViewContainer"] .stAlert, 
    div[data-testid="stAppViewContainer"] .stExpander {
        background: rgba(255,255,255,0.03) !important;
        box-shadow: none !important;
    }

    </style>
    """, unsafe_allow_html=True)



# --- INICIALIZAÇÃO DA SESSÃO ---
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.screen = 'home'
    st.session_state.player_name = ''
    st.session_state.current_question = 0
    st.session_state.score = 0
    st.session_state.questions = []
    st.session_state.answer_submitted = False
    st.session_state.timer = QUESTION_TIMER
    st.session_state.sheet_id = "1HUDx8d2t-C9NoDi3E3lXrijtCKH9_6O4eMb-4yZgtwM"
    st.session_state.questions_tab = "Perguntas"
    st.session_state.is_admin = False
    st.session_state.feedback_message = None
    st.session_state.feedback_type = None
    st.session_state.total_time = 0.0
    st.session_state.quiz_enabled = True  # Controle do quiz


# --- FUNÇÕES DE CONTROLE DO QUIZ ---
def load_quiz_status():
    """Carrega o status do quiz da planilha"""
    try:
        config_df = load_data(st.session_state.sheet_id, "Config")
        if not config_df.empty and 'quiz_enabled' in config_df.columns:
            status = config_df.iloc[0]['quiz_enabled']
            return str(status).lower() in ['true', '1', 'sim', 'habilitado', 'enabled']
        return True  # Default habilitado se não encontrar configuração
    except Exception as e:
        # Se a planilha Config não existir, retorna True (habilitado por padrão)
        return True


def save_quiz_status(enabled):
    """Salva o status do quiz na planilha"""
    try:
        config_data = pd.DataFrame({
            'quiz_enabled': [enabled],
            'last_updated': [time.strftime('%Y-%m-%d %H:%M:%S')],
            'updated_by': ['Admin']
        })

        # Tentar atualizar planilha existente
        try:
            return update_sheet_from_df(st.session_state.sheet_id, "Config", config_data)
        except:
            # Se falhar, tentar criar nova planilha
            try:
                workbook = gsheets_client.open_by_key(st.session_state.sheet_id)
                config_sheet = workbook.add_worksheet(title="Config", rows=100, cols=10)
                config_sheet.update([config_data.columns.values.tolist()] + config_data.values.tolist())
                return True
            except Exception as create_error:
                st.error(f"Erro ao criar planilha Config: {create_error}")
                return False

    except Exception as e:
        st.error(f"Erro ao salvar status: {e}")
        return False


def check_quiz_availability():
    """Verifica se o quiz está disponível"""
    return load_quiz_status()


# --- FUNÇÕES DO QUIZ ---
def start_quiz():
    # Verificar se o quiz está habilitado
    if not check_quiz_availability():
        st.error("🚫 O quiz não está disponível no momento. Aguarde a liberação pela organização do evento.")
        return

    name = st.session_state.player_name_input
    if name:
        st.session_state.player_name = name.strip()
        questions_df = load_data(st.session_state.sheet_id, st.session_state.questions_tab)
        if not questions_df.empty and not questions_df['pergunta'].isnull().all():
            st.session_state.questions = questions_df.dropna(subset=['pergunta']).to_dict('records')
            st.session_state.current_question = 0
            st.session_state.score = 0
            st.session_state.total_time = 0.0
            st.session_state.feedback_message = None
            st.session_state.answer_submitted = False
            st.session_state.timer = QUESTION_TIMER
            st.session_state.screen = 'quiz'
        else:
            st.error("Nenhuma pergunta encontrada.")
    else:
        st.warning("Por favor, digite seu nome.")


def next_question():
    if (st.session_state.current_question + 1) < len(st.session_state.questions):
        st.session_state.current_question += 1
        st.session_state.answer_submitted = False
        st.session_state.timer = QUESTION_TIMER
        st.session_state.feedback_message = None
    else:
        append_row_to_sheet(st.session_state.sheet_id, "Ranking",
                            [st.session_state.player_name, st.session_state.score, st.session_state.total_time])
        st.session_state.screen = 'end'


def show_admin_panel():
    # CONTROLE DE ESTADO DO QUIZ
    st.header("🎮 Controle do Quiz")

    # Carregar status atual
    current_status = load_quiz_status()

    col1, col2 = st.columns(2)

    with col1:
        if current_status:
            st.success("✅ Quiz HABILITADO - Participantes podem jogar")
        else:
            st.error("🚫 Quiz DESABILITADO - Participantes não podem jogar")

    with col2:
        # Botões de controle
        if current_status:
            if st.button("🛑 Desabilitar Quiz", type="secondary"):
                with st.spinner("Desabilitando quiz..."):
                    if save_quiz_status(False):
                        st.success("Quiz desabilitado com sucesso!")
                        st.cache_data.clear()  # Limpar cache para atualizar status
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Erro ao desabilitar quiz.")
        else:
            if st.button("✅ Habilitar Quiz", type="primary"):
                with st.spinner("Habilitando quiz..."):
                    if save_quiz_status(True):
                        st.success("Quiz habilitado com sucesso!")
                        st.cache_data.clear()  # Limpar cache para atualizar status
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Erro ao habilitar quiz.")

    # Instruções para primeira configuração
    st.info("""
    💡 **Primeira vez usando o sistema?**

    1. Clique em "Habilitar Quiz" ou "Desabilitar Quiz" para criar a configuração inicial
    2. A planilha "Config" será criada automaticamente no Google Sheets
    3. Depois disso, o sistema funcionará normalmente
    """)

    # Status detalhado
    with st.expander("📊 Configuração do Sistema", expanded=False):
        try:
            config_df = load_data(st.session_state.sheet_id, "Config")
            if not config_df.empty:
                st.success("📋 Configuração encontrada:")
                st.dataframe(config_df, use_container_width=True)
            else:
                st.warning("⚠️ Planilha 'Config' está vazia ou não foi inicializada")
                st.write("👆 Use os botões acima para criar a configuração inicial")
        except Exception as e:
            st.warning("⚠️ Planilha 'Config' não encontrada")
            st.write("👆 Use os botões acima para criar a configuração inicial")
            st.write(f"Detalhes do erro: {str(e)}")

    st.markdown("---")

    # GERENCIAMENTO DE PERGUNTAS
    st.header("🔧 Gerenciar Perguntas")

    with st.expander("⬆️ Upload de Arquivo (CSV/Excel)", expanded=False):
        uploaded_file = st.file_uploader("Substituir perguntas com um novo arquivo", type=['csv', 'xlsx'])
        if uploaded_file:
            try:
                new_questions_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(
                    uploaded_file)
                required_cols = {'pergunta', 'opcoes', 'resposta_correta'}
                if not required_cols.issubset(new_questions_df.columns):
                    st.error(f"O arquivo precisa ter as colunas: {', '.join(required_cols)}")
                else:
                    st.dataframe(new_questions_df, use_container_width=True)
                    if st.button("✅ Confirmar e Substituir Tudo"):
                        with st.spinner("Atualizando..."):
                            if update_sheet_from_df(st.session_state.sheet_id, st.session_state.questions_tab,
                                                    new_questions_df):
                                st.success("✅ Perguntas substituídas com sucesso!")
                                st.cache_data.clear()
                            else:
                                st.error("❌ Falha ao atualizar.")
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")

    st.subheader("📝 Editar Perguntas")
    questions_df = load_data(st.session_state.sheet_id, st.session_state.questions_tab)
    if not questions_df.empty:
        edited_df = st.data_editor(questions_df, num_rows="dynamic", use_container_width=True)
        if st.button("💾 Salvar Alterações"):
            with st.spinner("Salvando..."):
                if update_sheet_from_df(st.session_state.sheet_id, st.session_state.questions_tab, edited_df):
                    st.success("✅ Alterações salvas!")
                    st.cache_data.clear()
                else:
                    st.error("❌ Não foi possível salvar.")
    else:
        st.info("📋 Nenhuma pergunta para editar.")


def show_qrcode_generator():
    st.header("📱 Gerador de QR Code")
    app_url = st.text_input("Cole a URL do aplicativo aqui:", placeholder="https://seu-app.streamlit.app")
    if app_url:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(app_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        st.image(buf.getvalue(), caption="📱 Escaneie para acessar o quiz!", width=300)


def show_home():
    st.markdown("""
    <div class="quiz-header">
        <h2 class="sipat-title">⚡ SIPAT 2025 ⚡</h2>
        <h1 class="main-title">🏆 De olho no risco 👁️</h1>
        <p class="subtitle">
            🛡️ Seu radar para perigos está calibrado? Ative seus sentidos e prove que nada escapa do seu olhar atento! 🎯
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Verificar se o quiz está disponível
    quiz_available = check_quiz_availability()

    tab_player, tab_admin = st.tabs(["🎮 Jogar Quiz", "🔑 Administrador"])

    with tab_player:
        if not quiz_available:
            st.markdown("""
            <div class="info-section">
                <h3>⏳ Quiz Temporariamente Indisponível</h3>
                <p>O quiz será liberado no momento do evento pela organização da SIPAT. Aguarde a liberação!</p>
            </div>
            """, unsafe_allow_html=True)

            st.warning("🚫 O quiz não está disponível no momento. Aguarde a liberação pela organização do evento.")

            # Input desabilitado
            st.text_input(
                "Digite seu nome para começar:",
                key="player_name_input",
                placeholder="Aguarde a liberação do quiz...",
                disabled=True
            )
            st.button("⏳ Aguardando Liberação", disabled=True)

        else:
            st.markdown("""
            <div class="info-section">
                <h3>🚀 Pronto para o desafio?</h3>
                <p>Digite seu nome e mostre que você tem olho aguçado para identificar riscos!</p>
            </div>
            """, unsafe_allow_html=True)

            st.text_input(
                "Digite seu nome para começar:",
                key="player_name_input",
                placeholder="Seu nome aqui..."
            )
            st.button("🚀 Iniciar Quiz", on_click=start_quiz)

    with tab_admin:
        st.markdown("""
        <div class="info-section">
            <h3>🔐 Painel Administrativo</h3>
            <p>Acesso restrito para gerenciar perguntas e configurações do sistema.</p>
        </div>
        """, unsafe_allow_html=True)

        admin_password = st.text_input(
            "Senha de Administrador:",
            type="password",
            key="admin_password_input",
            placeholder="Digite a senha..."
        )

        if st.button("🔓 Acessar Painel"):
            try:
                correct_password = st.secrets["admin_password"]
            except (FileNotFoundError, KeyError):
                correct_password = "admin"

            if admin_password == correct_password:
                st.session_state.is_admin = True
                st.session_state.screen = 'admin'
                st.success("✅ Acesso autorizado! Redirecionando...")
                time.sleep(1.5)
            elif admin_password:
                st.error("❌ Credenciais inválidas.")


def show_quiz():
    q_index = st.session_state.current_question
    question_data = st.session_state.questions[q_index]
    correct_answer = str(question_data.get('resposta_correta', ''))

    # Timer logic
    if not st.session_state.answer_submitted and st.session_state.timer > 0:
        st_autorefresh(interval=1000, key=f"timer_{q_index}")
        st.session_state.timer -= 1
    elif st.session_state.timer <= 0 and not st.session_state.answer_submitted:
        st.session_state.total_time += QUESTION_TIMER
        st.session_state.answer_submitted = True
        st.session_state.feedback_message = f"Tempo esgotado! A resposta era: **{correct_answer}**"
        st.session_state.feedback_type = "error"

    # Header do quiz
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"### Jogador: {st.session_state.player_name}")
    with col2:
        st.markdown(f"### Pontos: {st.session_state.score}")

    # Timer
    timer_class = "timer-critical" if st.session_state.timer <= 10 else ""
    st.markdown(f"""
    <div class="timer-display {timer_class}">
        ⏱️ {st.session_state.timer}s
    </div>
    """, unsafe_allow_html=True)

    # Pergunta
    st.markdown(f"""
    <div class="question-box">
        <h3>Pergunta {q_index + 1} de {len(st.session_state.questions)}</h3>
        <h3>{question_data['pergunta']}</h3>
    </div>
    """, unsafe_allow_html=True)

    # Feedback
    if st.session_state.feedback_message:
        if st.session_state.feedback_type == "success":
            st.success(st.session_state.feedback_message)
        else:
            st.error(st.session_state.feedback_message)

    # Opções de resposta
    options = str(question_data.get('opcoes', '')).split(';')
    styles = [
        {"class": "red", "shape": "🔺"},
        {"class": "blue", "shape": "♦️"},
        {"class": "yellow", "shape": "🟡"},
        {"class": "green", "shape": "🟩"}
    ]

    cols = st.columns(2)
    for i, option in enumerate(options):
        if i < len(styles):
            with cols[i % 2]:
                style = styles[i]
                button_label = f"{style['shape']} {option.strip()}"
                st.markdown(f'<div class="answer-btn {style["class"]}">', unsafe_allow_html=True)
                if st.button(button_label, key=f"q{q_index}_opt{i}", disabled=st.session_state.answer_submitted):
                    time_taken = QUESTION_TIMER - st.session_state.timer
                    st.session_state.total_time += time_taken
                    st.session_state.answer_submitted = True

                    if option.strip().lower() == correct_answer.strip().lower():
                        st.session_state.score += 10
                        st.session_state.feedback_message = f"{random.choice(CORRECT_MESSAGES)}"
                        st.session_state.feedback_type = "success"
                        st.balloons()
                    else:
                        st.session_state.feedback_message = f"{random.choice(WRONG_MESSAGES)} A resposta correta era: **{correct_answer}**"
                        st.session_state.feedback_type = "error"
                st.markdown('</div>', unsafe_allow_html=True)

    # Botão próxima pergunta
    if st.session_state.answer_submitted:
        if (q_index + 1) < len(st.session_state.questions):
            st.button("Próxima Pergunta", on_click=next_question)
        else:
            st.button("Finalizar e Ver Ranking", on_click=next_question)


def show_end_screen():
    st.balloons()

    st.markdown(f"""
    <div class="quiz-header">
        <h1>🎉 Parabéns, {st.session_state.player_name}!</h1>
        <h2>Sua pontuação final: {st.session_state.score} pontos</h2>
        <p style="font-size: 18px;">Tempo total: {st.session_state.total_time:.1f} segundos</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("🏆 Ranking Geral - Top 100")

    # Limpar cache e carregar ranking
    st.cache_data.clear()
    ranking_df = load_data(st.session_state.sheet_id, "Ranking")

    if not ranking_df.empty:
        ranking_df['nome'] = ranking_df['nome'].astype(str)
        if 'tempo_total' not in ranking_df.columns:
            ranking_df['tempo_total'] = 999.0
        ranking_df['pontuacao'] = pd.to_numeric(ranking_df['pontuacao'], errors='coerce').fillna(0)
        ranking_df['tempo_total'] = pd.to_numeric(ranking_df['tempo_total'], errors='coerce').fillna(999)

        sorted_ranking = ranking_df.sort_values(
            by=['pontuacao', 'tempo_total'],
            ascending=[False, True]
        ).head(100).reset_index(drop=True)

        sorted_ranking['Tempo (s)'] = sorted_ranking['tempo_total'].apply(lambda t: f"{t:.1f}")
        display_ranking = sorted_ranking[['nome', 'pontuacao', 'Tempo (s)']]
        display_ranking.columns = ['Nome', 'Pontuação', 'Tempo (s)']
        display_ranking.index += 1

        st.dataframe(display_ranking, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 Baixar CSV",
                sorted_ranking.to_csv(index=False).encode('utf-8'),
                "ranking.csv",
                "text/csv"
            )
        with col2:
            st.download_button(
                "📊 Baixar Excel",
                df_to_excel_bytes(sorted_ranking),
                "ranking.xlsx"
            )
    else:
        st.info("🎯 Você é o primeiro! Ainda não há outras pontuações no ranking.")

    if st.button("🔄 Jogar Novamente"):
        st.session_state.screen = 'home'
        st.session_state.player_name = ''
        st.session_state.current_question = 0
        st.session_state.score = 0
        st.session_state.total_time = 0.0
        st.session_state.feedback_message = None
        st.rerun()


def show_admin_screen():
    st.markdown("""
    <div class="quiz-header">
        <h1>🔑 Painel de Administração</h1>
        <p style="font-size: 18px;">Gerencie perguntas e configurações do quiz</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("⬅️ Voltar para a Tela Inicial"):
        st.session_state.screen = 'home'

    st.markdown("---")
    show_admin_panel()

    st.markdown("---")
    show_qrcode_generator()

    st.markdown("---")
    st.warning("⚠️ A ação de sair irá desconectar sua sessão de administrador.")
    if st.button("🚪 Sair do modo Admin"):
        st.session_state.is_admin = False
        st.session_state.screen = 'home'


def main():
    inject_custom_styles()
    st.markdown('<div class="main-container">', unsafe_allow_html=True)

    current_screen = st.session_state.get('screen', 'home')
    if current_screen == 'admin' and not st.session_state.get('is_admin', False):
        st.warning("⚠️ Acesso negado.")
        st.session_state.screen = 'home'
        current_screen = 'home'

    screen_functions = {
        'home': show_home,
        'quiz': show_quiz,
        'end': show_end_screen,
        'admin': show_admin_screen
    }

    screen_to_show = screen_functions.get(current_screen, show_home)
    screen_to_show()

    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()