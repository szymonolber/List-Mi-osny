import streamlit as st
import time
import uuid
import html
from game_logic import Game, Player, Card

# Page Config
st.set_page_config(
    page_title="List Miłosny",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .card-container {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border: 2px solid #ccc;
        text-align: center;
        height: 250px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .card-title {
        font-weight: bold;
        font-size: 1.2em;
        color: #333;
    }
    .card-desc {
        font-size: 0.9em;
        color: #555;
    }
    .opponent-box {
        background-color: #2c3e50;
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 5px;
    }
    .active-turn {
        border: 2px solid #f1c40f;
        box-shadow: 0 0 10px #f1c40f;
    }
    .log-box {
        height: 300px;
        overflow-y: scroll;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 10px;
        font-family: monospace;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

if 'nickname' not in st.session_state:
    st.session_state.nickname = ""

if 'lobby_id' not in st.session_state:
    st.session_state.lobby_id = None

# Global Game Manager (Cached)
class GameManager:
    def __init__(self):
        self.lobbies = {} # lobby_id -> Game

    def create_lobby(self):
        lobby_id = str(uuid.uuid4())[:6].upper()
        self.lobbies[lobby_id] = Game(lobby_id)
        return lobby_id

    def get_game(self, lobby_id):
        return self.lobbies.get(lobby_id)

@st.cache_resource
def get_manager():
    return GameManager()

manager = get_manager()

# --- Functions ---

def leave_game():
    game = manager.get_game(st.session_state.lobby_id)
    if game:
        game.remove_player(st.session_state.session_id)
    st.session_state.lobby_id = None
    st.rerun()

def play_card_action(card_index, target_sid, guess_val):
    game = manager.get_game(st.session_state.lobby_id)
    if not game: return
    
    success, msg = game.play_card(st.session_state.session_id, card_index, target_sid, guess_val)
    if success:
        st.success(msg)
        time.sleep(1) # Show success briefly
        st.rerun()
    else:
        st.error(msg)

# --- Screens ---

def login_screen():
    st.title("💌 List Miłosny")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Dołącz / Stwórz")
        nick = st.text_input("Twój Nick", value=st.session_state.nickname)
        
        if st.button("Stwórz Nowe Lobby"):
            if not nick:
                st.error("Podaj nick!")
            else:
                st.session_state.nickname = nick
                lobby_id = manager.create_lobby()
                game = manager.get_game(lobby_id)
                game.add_player(Player(nick, st.session_state.session_id))
                st.session_state.lobby_id = lobby_id
                st.rerun()
                
        st.divider()
        
        join_code = st.text_input("Kod Lobby")
        if st.button("Dołącz do Lobby"):
            if not nick or not join_code:
                st.error("Podaj nick i kod!")
            else:
                game = manager.get_game(join_code.upper())
                if not game:
                    st.error("Nie ma takiego lobby.")
                elif game.game_started and not game.game_over: 
                    # Allow rejoin? Complex. For now block.
                    st.error("Gra już trwa.")
                else:
                    st.session_state.nickname = nick
                    if game.add_player(Player(nick, st.session_state.session_id)):
                        st.session_state.lobby_id = join_code.upper()
                        st.rerun()
                    else:
                        st.error("Lobby pełne lub błąd.")

def lobby_screen(game):
    st.title(f"Lobby: {game.lobby_id}")
    
    st.write("### Gracze:")
    for p in game.players:
        is_me = (p.sid == st.session_state.session_id)
        role = " (Gospodarz)" if p.is_host else ""
        me_tag = " (Ty)" if is_me else ""
        st.write(f"- {p.name}{role}{me_tag}")

    my_player = game.get_player_by_sid(st.session_state.session_id)
    if not my_player:
        st.error("Zostałeś wyrzucony.")
        time.sleep(2)
        st.session_state.lobby_id = None
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Odśwież"):
            st.rerun()
        if st.button("Opuść Lobby"):
            leave_game()

    with col2:
        if my_player.is_host:
            if st.button("Rozpocznij Grę"):
                if len(game.players) < 2:
                    st.error("Potrzeba min. 2 graczy.")
                else:
                    game.start_game()
                    st.rerun()
        else:
            st.info("Oczekiwanie na gospodarza...")
            
    # Auto-refresh logic (poor man's websocket)
    time.sleep(2)
    st.rerun()

def render_card(card, index, my_player, game):
    with st.container():
        st.markdown(f"""
        <div class="card-container">
            <div class="card-title">{card.name} ({card.value})</div>
            <div style="font-size:3em;">🃏</div>
            <div class="card-desc">{card.description}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Interaction
        is_my_turn = (game.players[game.turn_index].sid == my_player.sid)
        if is_my_turn and not game.game_over:
            with st.expander("Zagraj"):
                # Target selection logic
                needs_target = card.value in [1, 2, 3, 5, 6]
                can_target_self = (card.value == 5)
                
                target_sid = None
                guess_val = None
                
                if needs_target:
                    targets = [p for p in game.players if not p.is_out and (p.sid != my_player.sid or can_target_self)]
                    # Filter protected
                    valid_targets = [p for p in targets if not (p.is_protected and p.sid != my_player.sid)]
                    
                    if not valid_targets and not can_target_self:
                        st.warning("Brak celów - karta zostanie odrzucona bez efektu.")
                    else:
                        # Allow selecting active players
                        # If all opponents protected, user usually selects "None" or effect fizzles. 
                        # Implementation: User selects from valid targets.
                        target_options = {p.sid: p.name for p in valid_targets}
                        if not target_options:
                             # Must target self if Prince
                             if card.value == 5:
                                 target_options = {my_player.sid: my_player.name}
                        
                        if target_options:
                            selected_sid = st.selectbox("Cel", options=list(target_options.keys()), format_func=lambda x: target_options[x], key=f"t_{index}")
                            target_sid = selected_sid
                
                if card.value == 1 and target_sid:
                    guess_val = st.selectbox("Zgadnij kartę", [2,3,4,5,6,7,8], format_func=lambda x: f"{Card.get_name(x)} ({x})", key=f"g_{index}")

                if st.button("Zatwierdź", key=f"btn_{index}"):
                    play_card_action(index, target_sid, guess_val)

def game_screen(game):
    # Check auto restart
    game.try_auto_restart()
    
    my_player = game.get_player_by_sid(st.session_state.session_id)
    if not my_player:
        st.error("Nie ma Cię w grze.")
        if st.button("Wróć"):
            st.session_state.lobby_id = None
            st.rerun()
        return

    # Top Bar
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.subheader(f"Lobby: {game.lobby_id} | Talia: {len(game.deck)}")
    turn_player = game.players[game.turn_index]
    c2.info(f"Tura: {turn_player.name}")
    if c3.button("Opuść"):
        leave_game()

    # Layout
    row1 = st.container()
    row2 = st.container()
    
    with row1:
        # Opponents
        st.write("### Przeciwnicy")
        cols = st.columns(len(game.players)-1 if len(game.players) > 1 else 1)
        col_idx = 0
        for p in game.players:
            if p.sid == my_player.sid: continue
            
            with cols[col_idx % len(cols)]:
                style_class = "opponent-box"
                status = "W grze"
                if p.sid == turn_player.sid: style_class += " active-turn"
                if p.is_out: status = "❌ Odpadł"
                elif p.is_protected: status = "🛡️ Chroniony"
                
                safe_name = html.escape(p.name)
                st.markdown(f"""
                <div class="{style_class}">
                    <b>{safe_name}</b><br>
                    Wynik: {p.score}<br>
                    Status: {status}
                </div>
                """, unsafe_allow_html=True)
            col_idx += 1

    st.divider()

    with row2:
        c_hand, c_logs = st.columns([2, 1])
        
        with c_hand:
            st.write(f"### Twoja Ręka (Wynik: {my_player.score})")
            if my_player.is_out:
                st.error("Odpadłeś z tej rundy.")
            else:
                if my_player.is_protected:
                    st.success("Jesteś chroniony do następnej tury.")
                
                # Show private message (Priest)
                if my_player.private_message:
                    st.warning(f"👁️ {my_player.private_message}")

                # Cards
                h_cols = st.columns(len(my_player.hand))
                for i, card in enumerate(my_player.hand):
                    with h_cols[i]:
                        render_card(card, i, my_player, game)
        
        with c_logs:
            st.write("### Logi")
            log_text = "<br>".join(game.logs[-15:])
            st.markdown(f"<div class='log-box'>{log_text}</div>", unsafe_allow_html=True)

    if game.game_over:
        st.balloons()
        st.success("Koniec rundy! Nowa rozpocznie się za chwilę...")
    
    # Refresh Loop
    time.sleep(2)
    st.rerun()

# --- Main App Logic ---

def main():
    if not st.session_state.lobby_id:
        login_screen()
    else:
        game = manager.get_game(st.session_state.lobby_id)
        if not game:
            st.error("Lobby wygasło.")
            st.session_state.lobby_id = None
            if st.button("Ok"): st.rerun()
        elif not game.game_started:
            lobby_screen(game)
        else:
            game_screen(game)

if __name__ == "__main__":
    main()
