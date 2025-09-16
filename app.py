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
st.set_page_config(page_title="Radar de Risco", page_icon="🏆", layout="centered")

# --- CONFIGURAÇÕES E CONSTANTES ---
QUESTION_TIMER = 30
CORRECT_MESSAGES = ["Excelente!", "Mandou bem!", "Correto!", "Isso aí!", "Perfeito!"]
WRONG_MESSAGES = ["Não foi dessa vez.", "Quase lá!", "Ops!", "Resposta incorreta."]


# --- FUNÇÕES AUXILIARES ---
def df_to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Ranking')
    return output.getvalue()


# --- CONEXÃO COM GOOGLE SHEETS ---
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
            st.error("Credenciais não encontradas. Configure 'secrets.toml' ou 'google_sheets_credentials.json'.")
            st.stop()
    return gspread.authorize(creds)


gsheets_client = connect_to_google_sheets()


@st.cache_data(ttl=60)
def load_data(sheet_id, sheet_name):
    try:
        spreadsheet = gsheets_client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        st.warning(f"Aba '{sheet_name}' não encontrada. Criando...")
        try:
            spreadsheet = gsheets_client.open_by_key(sheet_id)
            headers = ["nome", "pontuacao", "tempo_total"] if sheet_name == "Ranking" else ["pergunta", "opcoes",
                                                                                            "resposta_correta", "dica"]
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols=len(headers))
            worksheet.append_row(headers)
            return pd.DataFrame(columns=headers)
        except Exception as e:
            st.error(f"Não foi possível criar a aba '{sheet_name}': {e}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


def update_sheet_from_df(sheet_id, sheet_name, dataframe):
    try:
        spreadsheet = gsheets_client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
        worksheet.update([dataframe.columns.values.tolist()] + dataframe.astype(str).values.tolist())
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar a planilha: {e}")
        return False


def append_row_to_sheet(sheet_id, sheet_name, row_list):
    try:
        spreadsheet = gsheets_client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.append_row(row_list)
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar linha na planilha: {e}")
        return False


# --- ESTILO CSS (TEMA ESCURO) ---
def inject_dark_theme_styles():
    st.markdown("""
    <style>
        /* ... (CSS completo) ... */
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
        body, .stApp { background-color: #121212 !important; color: #FFFFFF !important; font-family: 'Montserrat', sans-serif; }
        header[data-testid="stHeader"] { display: none !important; }
        .block-container { padding: 2rem !important; }
        h1, h2, h3, h4, h5, h6, p, label, .st-emotion-cache-1avcm0n p { color: #FFFFFF !important; }
        .st-emotion-cache-10trblm { text-align: center; }
        .stTabs [data-baseweb="tab-list"] { justify-content: center; border-bottom-color: #333 !important; }
        .stTabs [data-baseweb="tab"] p { color: #888 !important; font-weight: 600; }
        .stTabs [data-baseweb="tab"][aria-selected="true"] { border-bottom-color: #FFFFFF !important; }
        .stTabs [data-baseweb="tab"][aria-selected="true"] p { color: #FFFFFF !important; }
        .stTextInput input { background-color: #2E2E2E !important; color: #FFFFFF !important; border: 1px solid #555 !important; border-radius: 8px; }
        .stButton button { background-color: #333; color: #FFF; border-radius: 8px; font-weight: 600; border: 1px solid #555; transition: all 0.2s ease; }
        .stButton button:hover { background-color: #444; border-color: #777; }
        .question-box { background-color: #FFFFFF; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .question-box h3 { color: #121212 !important; font-weight: 700; font-size: 24px; margin: 0; }
        .answer-btn button { background-color: #2E2E2E; font-size: 18px; padding: 20px; margin-bottom: 10px; }
        .answer-btn button:hover { border-color: #FFF; }
    </style>
    """, unsafe_allow_html=True)


# --- CALLBACKS ---
def start_quiz():
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


# --- FUNÇÕES DE ADMIN ---
def show_admin_panel():
    st.header("Gerenciar Perguntas")
    with st.expander("⬆️ Upload (CSV/Excel)"):
        uploaded_file = st.file_uploader("Substituir perguntas com um novo arquivo", type=['csv', 'xlsx'])
        if uploaded_file:
            try:
                new_questions_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(
                    uploaded_file)
                required_cols = {'pergunta', 'opcoes', 'resposta_correta'}
                if not required_cols.issubset(new_questions_df.columns):
                    st.error(f"O arquivo precisa ter as colunas: {', '.join(required_cols)}")
                else:
                    st.dataframe(new_questions_df)
                    if st.button("Confirmar e Substituir Tudo"):
                        with st.spinner("Atualizando..."):
                            if update_sheet_from_df(st.session_state.sheet_id, st.session_state.questions_tab,
                                                    new_questions_df):
                                st.success("Perguntas substituídas!")
                                st.cache_data.clear()
                            else:
                                st.error("Falha ao atualizar.")
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")
    st.subheader("📝 Editar na Planilha")
    questions_df = load_data(st.session_state.sheet_id, st.session_state.questions_tab)
    if not questions_df.empty:
        edited_df = st.data_editor(questions_df, num_rows="dynamic", use_container_width=True)
        if st.button("Salvar Alterações"):
            with st.spinner("Salvando..."):
                if update_sheet_from_df(st.session_state.sheet_id, st.session_state.questions_tab, edited_df):
                    st.success("Alterações salvas!")
                    st.cache_data.clear()
                else:
                    st.error("Não foi possível salvar.")
    else:
        st.info("Nenhuma pergunta para editar.")


def show_qrcode_generator():
    st.header("Gerador de QR Code")
    app_url = st.text_input("Cole a URL do aplicativo aqui:")
    if app_url:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(app_url)
        qr.make(fit=True)
        # CORREÇÃO AQUI: Invertemos as cores para o padrão universal (preto no branco)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        st.image(buf, caption="Escaneie para acessar o quiz!")


# --- FUNÇÕES DE TELA ---
def show_home():
    st.title("🚧"
             " Radar de Risco 🚧")
    st.write("Seu radar para perigos está calibrado? Ative seus sentidos e prove que nada escapa do seu olhar atento!")
    tab_player, tab_admin = st.tabs(["👤 Jogar Quiz", "🔑 Administrador"])
    with tab_player:
        st.text_input("Digite seu nome para começar:", key="player_name_input", placeholder="Seu nome aqui")
        st.button("Iniciar Quiz", on_click=start_quiz, use_container_width=True)
    with tab_admin:
        st.write("Use a senha para acessar o painel de administração.")
        admin_password = st.text_input("Senha", type="password", key="admin_password_input",
                                       placeholder="Digite a senha")
        if st.button("Login Admin", use_container_width=True):
            try:
                correct_password = st.secrets["admin_password"]
            except (FileNotFoundError, KeyError):
                correct_password = "admin"

            if admin_password == correct_password:
                st.session_state.is_admin = True
                st.session_state.screen = 'admin'
                st.success("Login bem-sucedido! Redirecionando...")
                time.sleep(1.5)
                st.rerun()
            elif admin_password:
                st.error("Senha incorreta.")


def show_quiz():
    q_index = st.session_state.current_question
    question_data = st.session_state.questions[q_index]
    correct_answer = str(question_data.get('resposta_correta', ''))
    if not st.session_state.answer_submitted and st.session_state.timer > 0:
        st_autorefresh(interval=1000, key=f"timer_{q_index}")
        st.session_state.timer -= 1
    elif st.session_state.timer <= 0 and not st.session_state.answer_submitted:
        st.session_state.total_time += QUESTION_TIMER
        st.session_state.answer_submitted = True
        st.session_state.feedback_message = f"Tempo esgotado! A resposta era: **{correct_answer}**"
        st.session_state.feedback_type = "error"
        st.rerun()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(f"Jogador: {st.session_state.player_name}")
    with col2:
        st.subheader(f"Pontos: {st.session_state.score}")
    st.markdown(f"<h1 style='text-align: center;'>⏳ {st.session_state.timer}</h1>", unsafe_allow_html=True)
    st.markdown(f"<div class='question-box'><h3>{question_data['pergunta']}</h3></div>", unsafe_allow_html=True)
    if st.session_state.feedback_message:
        (st.success if st.session_state.feedback_type == "success" else st.error)(st.session_state.feedback_message)
    options = str(question_data.get('opcoes', '')).split(';')
    shapes = ["🔺", "♦️", "🟡", "🟩"]
    cols = st.columns(2)
    for i, option in enumerate(options):
        if i < len(shapes):
            with cols[i % 2]:
                button_label = f"{shapes[i]} {option.strip()}"
                st.markdown('<div class="answer-btn">', unsafe_allow_html=True)
                if st.button(button_label, key=f"q{q_index}_opt{i}", disabled=st.session_state.answer_submitted,
                             use_container_width=True):
                    time_taken = QUESTION_TIMER - st.session_state.timer
                    st.session_state.total_time += time_taken
                    st.session_state.answer_submitted = True
                    if option.strip().lower() == correct_answer.strip().lower():
                        st.session_state.score += 10
                        st.session_state.feedback_message = f"Correto! {random.choice(CORRECT_MESSAGES)}"
                        st.session_state.feedback_type = "success"
                        st.balloons()
                    else:
                        st.session_state.feedback_message = f"Incorreto! A resposta era: **{correct_answer}**"
                        st.session_state.feedback_type = "error"
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.answer_submitted:
        if (q_index + 1) < len(st.session_state.questions):
            if st.button("Próxima Pergunta ➡️", use_container_width=True):
                st.session_state.current_question += 1
                st.session_state.answer_submitted = False
                st.session_state.timer = QUESTION_TIMER
                st.session_state.feedback_message = None
                st.rerun()
        else:
            if st.button("Finalizar e Ver Ranking 🏁", use_container_width=True):
                append_row_to_sheet(st.session_state.sheet_id, "Ranking",
                                    [st.session_state.player_name, st.session_state.score, st.session_state.total_time])
                st.session_state.screen = 'end'
                st.rerun()


def show_end_screen():
    st.balloons()
    st.title("🎉 Quiz Finalizado!")
    st.header(f"Parabéns, {st.session_state.player_name}! Sua pontuação final foi: **{st.session_state.score}**")
    st.subheader("Ranking Geral - Top 100")
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
        sorted_ranking['Tempo (s)'] = sorted_ranking['tempo_total'].apply(lambda t: f"{t:.2f}")
        display_ranking = sorted_ranking[['nome', 'pontuacao', 'Tempo (s)']]
        display_ranking.index += 1
        st.dataframe(display_ranking, use_container_width=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Baixar (CSV)", sorted_ranking.to_csv(index=False).encode('utf-8'), "ranking.csv",
                               "text/csv", use_container_width=True)
        with col2:
            st.download_button("📊 Baixar (Excel)", df_to_excel_bytes(sorted_ranking), "ranking.xlsx",
                               use_container_width=True)
    else:
        st.write("Ainda não há pontuações no ranking.")
    if st.button("Jogar Novamente", use_container_width=True):
        st.session_state.screen = 'home'
        st.session_state.player_name = ''
        st.session_state.current_question = 0
        st.session_state.score = 0
        st.session_state.total_time = 0.0
        st.rerun()


def show_admin_screen():
    st.title("🔑 Painel de Administração")
    st.markdown("---")
    if st.button("⬅️ Voltar para a Tela Inicial do Quiz"):
        st.session_state.screen = 'home'
        st.rerun()
    st.markdown("---")
    show_admin_panel()
    st.markdown("---")
    show_qrcode_generator()
    st.markdown("---")
    st.error("A ação de sair irá desconectar sua sessão de administrador.")
    if st.button("Sair do modo Admin"):
        st.session_state.is_admin = False
        st.session_state.screen = 'home'
        st.rerun()


# --- FUNÇÃO PRINCIPAL ---
def main():
    inject_dark_theme_styles()

    current_screen = st.session_state.get('screen', 'home')
    if current_screen == 'admin' and not st.session_state.get('is_admin', False):
        st.warning("Acesso negado. Por favor, faça o login como administrador.")
        st.session_state.screen = 'home'

    screen_functions = {
        'home': show_home,
        'quiz': show_quiz,
        'end': show_end_screen,
        'admin': show_admin_screen
    }
    screen_to_show = screen_functions.get(st.session_state.screen, show_home)
    if screen_to_show:
        screen_to_show()


if __name__ == "__main__":
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

    main()