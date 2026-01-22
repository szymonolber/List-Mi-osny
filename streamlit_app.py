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
    /* Dark Theme Background */
    .stApp {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    
    /* Card Container */
    .card-container {
        background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%);
        padding: 10px;
        border-radius: 12px;
        border: 4px solid #fff;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        text-align: center;
        height: 280px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        color: #333;
        transition: transform 0.2s;
    }
    .card-container:hover {
        transform: translateY(-5px);
    }
    .card-value {
        font-size: 1.5em;
        font-weight: bold;
        align-self: flex-start;
        border: 2px solid #333;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        line-height: 35px;
        display: inline-block;
    }
    .card-title {
        font-weight: bold;
        font-size: 1.1em;
        margin: 5px 0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .card-icon {
        font-size: 3.5em;
    }
    .card-desc {
        font-size: 0.85em;
        line-height: 1.2;
        background: rgba(255,255,255,0.8);
        padding: 5px;
        border-radius: 5px;
    }

    /* Opponent Box */
    .opponent-box {
        background-color: #2d2d2d;
        color: #ecf0f1;
        padding: 15px;
        border-radius: 8px;
        margin: 5px;
        border: 1px solid #444;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .active-turn {
        border: 2px solid #f1c40f;
        box-shadow: 0 0 15px rgba(241, 196, 15, 0.4);
    }
    .protected {
        border: 2px solid #3498db;
    }
    .eliminated {
        opacity: 0.5;
        text-decoration: line-through;
    }

    /* Table / Action Area */
    .table-area {
        background-color: #252525;
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
        border: 2px dashed #444;
        text-align: center;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    .action-text {
        font-size: 1.2em;
        color: #f1c40f;
        margin-top: 10px;
    }

    /* Logs */
    .log-box {
        height: 400px;
        overflow-y: auto;
        background-color: #111;
        border: 1px solid #333;
        padding: 10px;
        font-family: 'Consolas', monospace;
        font-size: 0.85em;
        color: #bbb;
        border-radius: 5px;
    }
    .log-entry {
        border-bottom: 1px solid #222;
        padding: 4px 0;
    }

    /* Buttons */
    .stButton > button {
        background-color: #e74c3c;
        color: white;
        border: none;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #c0392b;
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
    
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("### Witaj w grze!")
        nick = st.text_input("Twój Nick", value=st.session_state.nickname)
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Stwórz Nowe Lobby", use_container_width=True):
                if not nick:
                    st.error("Podaj nick!")
                else:
                    st.session_state.nickname = nick
                    lobby_id = manager.create_lobby()
                    game = manager.get_game(lobby_id)
                    game.add_player(Player(nick, st.session_state.session_id))
                    st.session_state.lobby_id = lobby_id
                    st.rerun()
        
        with col_b:
            join_code = st.text_input("Kod Lobby (jeśli dołączasz)")
            if st.button("Dołącz", use_container_width=True):
                if not nick or not join_code:
                    st.error("Podaj nick i kod!")
                else:
                    game = manager.get_game(join_code.upper())
                    if not game:
                        st.error("Nie ma takiego lobby.")
                    elif game.game_started and not game.game_over: 
                         # Check if rejoining? Simplified: Block.
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
    st.markdown("---")
    
    st.write("### Gracze w lobby:")
    cols = st.columns(4)
    for i, p in enumerate(game.players):
        with cols[i]:
            role = "👑 Gospodarz" if p.is_host else "Gracz"
            me_tag = "(Ty)" if p.sid == st.session_state.session_id else ""
            st.info(f"{p.name} {me_tag}\n\n{role}")

    my_player = game.get_player_by_sid(st.session_state.session_id)
    if not my_player:
        st.error("Zostałeś wyrzucony.")
        time.sleep(2)
        st.session_state.lobby_id = None
        st.rerun()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Odśwież"):
            st.rerun()
        if st.button("Opuść Lobby"):
            leave_game()

    with col2:
        if my_player.is_host:
            if st.button("Rozpocznij Grę", type="primary"):
                if len(game.players) < 2:
                    st.error("Potrzeba min. 2 graczy.")
                else:
                    game.start_game()
                    st.rerun()
        else:
            st.warning("Oczekiwanie na gospodarza...")
            
    time.sleep(2)
    st.rerun()

def render_card_visual(card):
    # Colors based on value
    colors = {
        1: "#3498db", 2: "#2ecc71", 3: "#795548", 4: "#f1c40f",
        5: "#e67e22", 6: "#f39c12", 7: "#e74c3c", 8: "#9b59b6"
    }
    color = colors.get(card.value, "#95a5a6")
    
    return f"""
    <div class="card-container" style="border-color: {color};">
        <div class="card-value" style="border-color: {color}; color: {color};">{card.value}</div>
        <div class="card-title" style="color: {color};">{card.name}</div>
        <div class="card-icon">🃏</div>
        <div class="card-desc">{card.description}</div>
    </div>
    """

def render_card_interactive(card, index, my_player, game):
    st.markdown(render_card_visual(card), unsafe_allow_html=True)
    
    # Interaction
    is_my_turn = (game.players[game.turn_index].sid == my_player.sid)
    if is_my_turn and not game.game_over:
        # Spacing
        st.write("")
        with st.popover(f"Zagraj {card.name}"):
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
                    st.warning("Brak celów - karta bez efektu.")
                else:
                    target_options = {p.sid: p.name for p in valid_targets}
                    if not target_options and can_target_self:
                             target_options = {my_player.sid: my_player.name}
                    
                    if target_options:
                        selected_sid = st.selectbox("Wybierz cel:", options=list(target_options.keys()), format_func=lambda x: target_options[x], key=f"t_{index}")
                        target_sid = selected_sid
            
            if card.value == 1 and target_sid:
                guess_val = st.selectbox("Zgadnij kartę:", [2,3,4,5,6,7,8], format_func=lambda x: f"{Card.get_name(x)} ({x})", key=f"g_{index}")

            if st.button("Potwierdź", key=f"btn_{index}", type="primary"):
                play_card_action(index, target_sid, guess_val)

def game_screen(game):
    game.try_auto_restart()
    my_player = game.get_player_by_sid(st.session_state.session_id)
    if not my_player:
        st.error("Nie ma Cię w grze.")
        if st.button("Wróć"):
            st.session_state.lobby_id = None
            st.rerun()
        return

    # Top Bar
    c1, c2, c3 = st.columns([2, 2, 1])
    c1.subheader(f"🏠 Lobby: {game.lobby_id}")
    c2.subheader(f"📚 Talia: {len(game.deck)}")
    if c3.button("🚪 Opuść"):
        leave_game()

    # Main Layout: 3 Columns (Left: Opponents, Center: Table, Right: Logs)
    col_opp, col_table, col_logs = st.columns([1, 2, 1])

    turn_player = game.players[game.turn_index]

    with col_opp:
        st.write("### 👥 Przeciwnicy")
        for p in game.players:
            if p.sid == my_player.sid: continue
            
            style_class = "opponent-box"
            status_text = "🟢 W grze"
            
            if p.sid == turn_player.sid: 
                style_class += " active-turn"
                status_text = "⚠️ JEGO TURA"
            
            if p.is_out: 
                style_class += " eliminated"
                status_text = "💀 Odpadł"
            elif p.is_protected: 
                style_class += " protected"
                status_text += " | 🛡️ Chroniony"
            
            safe_name = html.escape(p.name)
            st.markdown(f"""
            <div class="{style_class}">
                <div style="font-size: 1.2em; font-weight: bold;">{safe_name}</div>
                <div>Punkty: {p.score}</div>
                <div style="font-size: 0.9em; margin-top: 5px;">{status_text}</div>
            </div>
            """, unsafe_allow_html=True)

    with col_table:
        st.markdown("### 🎲 Stół (Ostatnia akcja)")
        st.markdown('<div class="table-area">', unsafe_allow_html=True)
        
        if game.last_action:
            action = game.last_action
            card_obj = Card(action['card_value'])
            
            # Show the card played visually
            st.markdown(render_card_visual(card_obj), unsafe_allow_html=True)
            
            safe_p = html.escape(action['player_name'])
            safe_desc = html.escape(action['description'])
            st.markdown(f"""
            <div class="action-text">
                <b>{safe_p}</b> zagrał kartę <b>{action['card_name']}</b><br>
                <i style="color: #ccc; font-size: 0.8em;">{safe_desc}</i>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color: #777;'>Oczekiwanie na ruch...</div>", unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Turn Indicator
        if turn_player.sid == my_player.sid:
            st.success("🔔 TWOJA KOLEJ!")
        else:
            st.info(f"Czekaj... Tura gracza: {turn_player.name}")

    with col_logs:
        st.write("### 📜 Logi")
        log_content = "".join([f"<div class='log-entry'>{l}</div>" for l in reversed(game.logs[-20:])])
        st.markdown(f"<div class='log-box'>{log_content}</div>", unsafe_allow_html=True)

    st.divider()

    # Player Area (Bottom)
    st.write(f"### 🃏 Twoja Ręka (Punkty: {my_player.score})")
    
    if my_player.is_out:
        st.error("❌ Odpadłeś z tej rundy. Czekaj na następną.")
    else:
        if my_player.is_protected:
            st.info("🛡️ Jesteś chroniony przed efektami kart do następnej tury.")
        
        if my_player.private_message:
            st.warning(f"👁️ {my_player.private_message}")
        
        # Cards Layout
        cols = st.columns(len(my_player.hand))
        for i, card in enumerate(my_player.hand):
            with cols[i]:
                render_card_interactive(card, i, my_player, game)

    if game.game_over:
        st.balloons()
        st.success("🏆 Koniec rundy! Nowa gra rozpocznie się automatycznie...")

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
