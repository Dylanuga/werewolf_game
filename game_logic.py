import random

# Mapeo de roles en inglés a español (variable global)
ROLE_NAMES = {
    'werewolf': 'Werewolf',
    'seer': 'Pitonisa',
    'robber': 'Ladrón',
    'troublemaker': 'Alborotadora',
    'drunk': 'Borracho',
    'insomniac': 'Insomne',
    'tanner': 'Curtidor',
    'villager': 'Aldeano'
}

class GameLogic:
    def __init__(self, players, room_code):
        self.players = players
        self.room_code = room_code
        self.center_cards = []
        self.game_state = 'setup'
        self.current_phase = None
        self.phase_order = []
        
    def setup_game(self):
        """Configura el juego: asigna roles"""
        num_players = len(self.players)
        
        # Roles simples para testing
        if num_players == 2:
            available_roles = ['werewolf', 'werewolf', 'seer', 'villager', 'villager']
        elif num_players == 3:
            available_roles = ['werewolf', 'werewolf', 'seer', 'robber', 'villager', 'villager']
        else:
            # Para 4+ jugadores
            available_roles = ['werewolf', 'werewolf', 'seer', 'robber', 'troublemaker', 'drunk', 'villager', 'villager']
        
        random.shuffle(available_roles)
        
        # Asignar roles a jugadores
        for i, player in enumerate(self.players):
            player['original_role'] = available_roles[i]
            player['current_role'] = available_roles[i]
            player['has_acted'] = False
            
        # 3 cartas al centro
        self.center_cards = available_roles[num_players:num_players+3]
        
        # Orden de fases
        self.phase_order = ['werewolf', 'seer', 'robber', 'troublemaker', 'drunk', 'insomniac']
        
        self.game_state = 'night'
        
        return {
            'players': self.players,
            'center_cards': len(self.center_cards),
            'game_state': self.game_state,
            'phase_order': self.phase_order
        }
    
    def start_night_phase(self, phase):
        """Inicia una fase nocturna"""
        self.current_phase = phase
        
        # Encontrar jugadores que pueden actuar
        players_can_act = []
        for player in self.players:
            if player['original_role'] == phase and not player['has_acted']:
                players_can_act.append({
                    'socket_id': player['socket_id'],
                    'username': player['username']
                })
        
        return {
            'phase': phase,
            'role_name': ROLE_NAMES.get(phase, phase.title()),
            'description': f'Es el turno de {ROLE_NAMES.get(phase, phase)}',
            'players_can_act': players_can_act
        }
    
    def get_player_by_socket_id(self, socket_id):
        """Obtiene un jugador por su socket_id"""
        for player in self.players:
            if player['socket_id'] == socket_id:
                return player
        return None
    
    def can_player_act_in_phase(self, socket_id, phase):
        """Verifica si un jugador puede actuar"""
        player = self.get_player_by_socket_id(socket_id)
        if not player:
            return False
        return (player['original_role'] == phase and 
                not player['has_acted'] and 
                self.current_phase == phase)
    
    def get_players_with_role(self, role):
        """Obtiene jugadores con un rol específico"""
        return [p for p in self.players if p['current_role'] == role]

class TestGameLogic(GameLogic):
    """Versión de GameLogic para testing con roles predefinidos"""
    
    def setup_test_game(self):
        """Configura el juego de testing: NO mezcla roles, usa los predefinidos"""
        # No mezclar roles, ya están asignados
        
        # Simular 3 cartas al centro (roles ficticios)
        self.center_cards = ['villager', 'villager', 'troublemaker']
        
        # Orden de fases
        self.phase_order = ['werewolf', 'seer', 'robber', 'troublemaker', 'drunk', 'insomniac']
        
        self.game_state = 'night'
        
        print(f"DEBUG: Setup de testing completado:")
        for player in self.players:
            print(f"DEBUG: - {player['username']}: {player['original_role']}")
        
        return {
            'players': self.players,
            'center_cards': len(self.center_cards),
            'game_state': self.game_state,
            'phase_order': self.phase_order
        }

def execute_werewolf_action(game, socket_id, action_data):
    """Acción de los lobos - AUTOMÁTICA al empezar la fase"""
    player = game.get_player_by_socket_id(socket_id)
    if not player:
        return {'success': False, 'error': 'Jugador no encontrado'}
        
    print(f"DEBUG: Player {player['username']}: original_role={player['original_role']}, current_role={player['current_role']}, has_acted={player['has_acted']}, current_phase={game.current_phase}")
    
    if not game.can_player_act_in_phase(socket_id, 'werewolf'):
        return {'success': False, 'error': 'No puedes actuar ahora'}
    
    # Obtener todos los lobos
    werewolves = game.get_players_with_role('werewolf')
    other_werewolves = []
    
    # Encontrar otros lobos (excluyendo al jugador actual)
    for wolf in werewolves:
        if wolf['socket_id'] != socket_id:
            other_werewolves.append({
                'username': wolf['username'],
                'socket_id': wolf['socket_id']
            })
    
    center_card = None
    is_lone_wolf = len(werewolves) == 1
    
    # Si eligió ver una carta del centro (solo lobos solitarios)
    if is_lone_wolf and 'center_index' in action_data:
        center_index = action_data['center_index']
        if 0 <= center_index < len(game.center_cards):
            center_card = {
                'index': center_index,
                'role': ROLE_NAMES.get(game.center_cards[center_index], game.center_cards[center_index])
            }
            # Marcar como actuado después de ver la carta del centro
            player['has_acted'] = True
    elif not is_lone_wolf:
        # Si hay múltiples lobos, se marcan como actuados automáticamente
        player['has_acted'] = True
    # Si es lobo solitario pero no eligió carta, NO marcar como actuado aún
    
    return {
        'success': True,
        'other_werewolves': other_werewolves,
        'center_card': center_card,
        'is_lone_wolf': is_lone_wolf,
        'auto_reveal': not is_lone_wolf
    }