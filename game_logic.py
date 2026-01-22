import random
import threading
import time
from enum import IntEnum

class CardValue(IntEnum):
    STRAZNICZKA = 1
    KAPLAN = 2
    BARON = 3
    POKOJOWKA = 4
    KSIAZE = 5
    KROL = 6
    HRABINA = 7
    KSIEZNICZKA = 8

class Card:
    def __init__(self, value):
        self.value = value
        self.name = self.get_name(value)
        self.description = self.get_description(value)

    @staticmethod
    def get_name(value):
        names = {
            1: "Strażniczka",
            2: "Kapłan",
            3: "Baron",
            4: "Pokojówka",
            5: "Książę",
            6: "Król",
            7: "Hrabina",
            8: "Księżniczka"
        }
        return names.get(value, "Nieznana")

    @staticmethod
    def get_description(value):
        descriptions = {
            1: "Zgadnij kartę innego gracza (nie Strażniczka).",
            2: "Podglądnij rękę innego gracza.",
            3: "Porównaj ręce z innym graczem; niższa odpada.",
            4: "Ignoruj wszystkie efekty do twojej następnej tury.",
            5: "Wybierz gracza, aby odrzucił rękę.",
            6: "Wymień się ręką z innym graczem.",
            7: "Musi być odrzucona jeśli masz Króla lub Księcia.",
            8: "Jeśli odrzucisz tę kartę, odpadasz."
        }
        return descriptions.get(value, "")
    
    def __repr__(self):
        return f"{self.name} ({self.value})"

class Player:
    def __init__(self, name, sid, is_host=False):
        self.name = name
        self.sid = sid # Streamlit Session ID or UUID
        self.is_host = is_host
        self.hand = []
        self.discarded = []
        self.is_out = False
        self.is_protected = False
        self.score = 0
        self.private_message = None # For Priest or other private info

    def draw(self, card):
        self.hand.append(card)

    def discard(self, card_index):
        if 0 <= card_index < len(self.hand):
            return self.hand.pop(card_index)
        return None

    def reset_round(self):
        self.hand = []
        self.discarded = []
        self.is_out = False
        self.is_protected = False
        self.private_message = None

class Game:
    def __init__(self, lobby_id):
        self.lobby_id = lobby_id
        self.players = []
        self.deck = []
        self.turn_index = 0
        self.game_started = False
        self.game_over = False
        self.logs = []
        self.removed_card = None 
        self.lock = threading.Lock()
        self.last_activity = time.time()
        self.round_end_time = None

    def add_player(self, player):
        with self.lock:
            if not self.game_started and len(self.players) < 4:
                # First player is host
                if not self.players:
                    player.is_host = True
                self.players.append(player)
                return True
            return False

    def remove_player(self, sid):
        with self.lock:
            player_index = -1
            for i, p in enumerate(self.players):
                if p.sid == sid:
                    player_index = i
                    break
            
            if player_index == -1:
                return False

            removed_player = self.players.pop(player_index)
            self.log(f"Gracz {removed_player.name} opuścił grę.")

            # If game is running, we need to handle this
            if self.game_started and not self.game_over:
                # If it was their turn, move to next
                if self.turn_index == player_index:
                    # We need to adjust turn_index because list shrank
                    # Actually, if we pop, the next player falls into this index.
                    # So we don't need to increment, just validate.
                    if self.turn_index >= len(self.players):
                        self.turn_index = 0
                    
                    # Force next turn logic (e.g. if they left mid-turn)
                    # We might need to start a new turn for the new current player
                    if self.players:
                         # It's messy to restart turn logic here, 
                         # simplest is to just ensure index is valid and maybe give them a card if they need one?
                         # Or just let 'next_turn' handle it if we call it.
                         # But `next_turn` draws a card.
                         
                         # Best approach: Just mark them is_out instead of removing?
                         # User asked: "reszta graczy moze kontynuowac"
                         # Removing is cleaner for "Next Round".
                         pass
                
                elif self.turn_index > player_index:
                    self.turn_index -= 1
                
                # Check win condition immediately
                self.check_round_end()
                
                # If game continues and it was their turn, the new player at turn_index needs to start turn
                # The next player is now at self.turn_index (since list shifted)
                if self.players:
                    # Draw a card for the new active player if they don't have 2 (standard turn start)
                    current_player = self.players[self.turn_index]
                    current_player.is_protected = False
                    current_player.private_message = None
                    if self.deck:
                         current_player.draw(self.deck.pop(0))
                    elif self.removed_card and not self.deck:
                         # Edge case: empty deck
                         self.end_round()
            
            # If host left, assign new host
            if removed_player.is_host and self.players:
                self.players[0].is_host = True
                self.log(f"{self.players[0].name} jest nowym gospodarzem.")

            if not self.players:
                # Game empty, will be cleaned up by manager
                pass
            
            return True

    def get_player_by_sid(self, sid):
        for p in self.players:
            if p.sid == sid:
                return p
        return None

    def log(self, message):
        self.logs.append(message)
        if len(self.logs) > 50:
            self.logs.pop(0)

    def start_game(self):
        with self.lock:
            if len(self.players) < 2:
                return False
            self.game_started = True
            self.start_round()
            return True

    def start_round(self):
        # 5x1, 2x2, 2x3, 2x4, 2x5, 1x6, 1x7, 1x8
        counts = {1: 5, 2: 2, 3: 2, 4: 2, 5: 2, 6: 1, 7: 1, 8: 1}
        self.deck = []
        for val, count in counts.items():
            for _ in range(count):
                self.deck.append(Card(val))
        
        random.shuffle(self.deck)
        
        for p in self.players:
            p.reset_round()

        if self.deck:
            self.removed_card = self.deck.pop(0)

        for p in self.players:
            if self.deck:
                p.draw(self.deck.pop(0))

        # Start with winner of last round if applicable? 
        # For simplicity, we keep turn_index or randomize if 0.
        # Ensure turn_index is valid
        if self.turn_index >= len(self.players):
            self.turn_index = 0
            
        self.players[self.turn_index].draw(self.deck.pop(0))
        self.log(f"Rozpoczęto nową rundę. Tura: {self.players[self.turn_index].name}")
        self.game_over = False
        self.round_end_time = None

    def next_turn(self):
        if self.check_round_end():
            return

        original_index = self.turn_index
        while True:
            self.turn_index = (self.turn_index + 1) % len(self.players)
            if not self.players[self.turn_index].is_out:
                break
            if self.turn_index == original_index:
                break
        
        current_player = self.players[self.turn_index]
        current_player.is_protected = False
        current_player.private_message = None # Clear old messages
        
        if self.deck:
            card = self.deck.pop(0)
            current_player.draw(card)
        else:
            self.end_round() # Should be caught by check_round_end but strictly speaking deck empty triggers end

    def play_card(self, player_sid, card_index, target_sid=None, guess_value=None):
        with self.lock:
            player = self.get_player_by_sid(player_sid)
            if not player or player != self.players[self.turn_index]:
                return False, "To nie twoja tura."

            if card_index < 0 or card_index >= len(player.hand):
                return False, "Nieprawidłowa karta."

            card = player.hand[card_index]
            
            # Countess Check
            has_countess = any(c.value == 7 for c in player.hand)
            has_royal = any(c.value in [5, 6] for c in player.hand)
            if has_countess and has_royal:
                if card.value != 7:
                    return False, "Musisz zagrać Hrabinę (7)."

            target = None
            if target_sid:
                target = self.get_player_by_sid(target_sid)
                # Validation logic is handled mostly by UI, but double check
                if not target or target.is_out or (target.is_protected and target != player):
                     pass # Effect might be nullified

            played_card = player.discard(card_index)
            player.discarded.append(played_card)
            self.log(f"{player.name} zagrywa {played_card.name}.")

            effect_msg = self.execute_effect(player, played_card, target, guess_value)
            if effect_msg:
                self.log(effect_msg)

            if not self.check_round_end():
                 self.next_turn()
            
            return True, "Zagrano kartę."

    def execute_effect(self, player, card, target, guess_value):
        if card.value == 1: # Guard
            if not target: return None
            if target.is_protected: return f"{target.name} jest chroniony."
            if not guess_value: return None
            
            if target.hand and target.hand[0].value == guess_value:
                target.is_out = True
                target.discarded.extend(target.hand)
                target.hand = []
                return f"{player.name} zgadł! {target.name} ma {Card.get_name(guess_value)} i odpada!"
            else:
                return f"{player.name} nie zgadł. {target.name} nie ma {Card.get_name(guess_value)}."

        elif card.value == 2: # Priest
            if not target: return None
            if target.is_protected: return f"{target.name} jest chroniony."
            
            if target.hand:
                seen_card = target.hand[0]
                player.private_message = f"Podglądasz rękę {target.name}: {seen_card.name} ({seen_card.value})"
                return f"{player.name} podgląda rękę {target.name}."
            return "Błąd: Cel nie ma kart."

        elif card.value == 3: # Baron
            if not target: return None
            if target.is_protected: return f"{target.name} jest chroniony."
            
            p_val = player.hand[0].value
            t_val = target.hand[0].value
            
            if p_val > t_val:
                target.is_out = True
                target.discarded.extend(target.hand)
                target.hand = []
                return f"Baron: {player.name} wygrywa z {target.name}. {target.name} miał {Card.get_name(t_val)} i odpada."
            elif t_val > p_val:
                player.is_out = True
                player.discarded.extend(player.hand)
                player.hand = []
                return f"Baron: {target.name} wygrywa z {player.name}. {player.name} miał {Card.get_name(p_val)} i odpada."
            else:
                return f"Baron: Remis. Nikt nie odpada."

        elif card.value == 4: # Handmaid
            player.is_protected = True
            return f"{player.name} jest chroniony."

        elif card.value == 5: # Prince
            if not target: target = player
            if target.is_protected and target != player: return f"{target.name} jest chroniony."

            discarded = target.hand.pop(0) if target.hand else None
            if discarded:
                target.discarded.append(discarded)
                msg = f"{target.name} odrzuca {discarded.name}."
                if discarded.value == 8: # Princess
                    target.is_out = True
                    msg += f" {target.name} odpada!"
                    return msg
                
                if self.deck:
                    target.draw(self.deck.pop(0))
                elif self.removed_card:
                    target.draw(self.removed_card)
                    self.removed_card = None
                return msg

        elif card.value == 6: # King
            if not target: return None
            if target.is_protected: return f"{target.name} jest chroniony."
            player.hand, target.hand = target.hand, player.hand
            return f"{player.name} wymienia się ręką z {target.name}."

        elif card.value == 8: # Princess
            player.is_out = True
            player.discarded.extend(player.hand)
            player.hand = []
            return f"{player.name} odrzuca Księżniczkę i odpada!"

        return None

    def check_round_end(self):
        active_players = [p for p in self.players if not p.is_out]
        
        round_ended = False
        winners = []

        if len(active_players) <= 1:
            round_ended = True
            if active_players:
                winners = active_players
        elif not self.deck:
            round_ended = True
            # Compare hands
            max_val = -1
            for p in active_players:
                if p.hand:
                    if p.hand[0].value > max_val:
                        max_val = p.hand[0].value
                        winners = [p]
                    elif p.hand[0].value == max_val:
                        winners.append(p)
            
            if len(winners) > 1:
                # Discard sum tiebreaker
                max_discard = -1
                final_winners = []
                for w in winners:
                    d_sum = sum(c.value for c in w.discarded)
                    if d_sum > max_discard:
                        max_discard = d_sum
                        final_winners = [w]
                    elif d_sum == max_discard:
                        final_winners.append(w)
                winners = final_winners

        if round_ended:
            self.game_over = True
            self.round_end_time = time.time()
            for w in winners:
                w.score += 1
            winner_names = ", ".join([w.name for w in winners]) if winners else "Nikt"
            self.log(f"KONIEC RUNDY. Zwycięzcy: {winner_names}")
            return True
        
        return False
    
    def try_auto_restart(self):
        # Called periodically by Streamlit app
        with self.lock:
            if self.game_over and self.round_end_time:
                # Restart after 5 seconds
                if time.time() - self.round_end_time > 5:
                    self.start_round()

