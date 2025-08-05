import random

# Mapeo de roles en inglés a español
ROLE_NAMES = {
    'werewolf': 'Lobo',
    'seer': 'Vidente',
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
        self.ROLE_NAMES = ROLE_NAMES
        
    def setup_game(self):
        """Configura el juego: asigna roles aleatoriamente"""
        num_players = len(self.players)

        # Roles por número de jugadores
        if num_players == 2:
            available_roles = ['werewolf', 'werewolf', 'seer', 'villager', 'villager']
        elif num_players == 3:
            available_roles = ['werewolf', 'werewolf', 'seer', 'robber', 'villager', 'villager']
        else:
            available_roles = ['werewolf', 'werewolf', 'seer', 'robber', 'troublemaker', 'drunk', 'villager', 'villager']

        random.shuffle(available_roles)

        # Asignar roles a jugadores
        for i, player in enumerate(self.players):
            player['original_role'] = available_roles[i]
            player['current_role'] = available_roles[i]
            player['has_acted'] = False

        # Cartas al centro
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

        players_can_act = [
            {'socket_id': p['socket_id'], 'username': p['username']}
            for p in self.players
            if p['original_role'] == phase and not p['has_acted']
        ]

        return {
            'phase': phase,
            'role_name': self.ROLE_NAMES.get(phase, phase.title()),
            'description': f'Es el turno de {self.ROLE_NAMES.get(phase, phase)}',
            'players_can_act': players_can_act
        }

    def get_player_by_socket_id(self, socket_id):
        """Busca un jugador por su socket ID"""
        return next((p for p in self.players if p['socket_id'] == socket_id), None)

    def can_player_act_in_phase(self, socket_id, phase):
        """Verifica si el jugador puede actuar en la fase actual"""
        player = self.get_player_by_socket_id(socket_id)
        return (
            player and
            player['original_role'] == phase and
            not player['has_acted'] and
            self.current_phase == phase
        )

    def get_players_with_role(self, role):
        """Devuelve jugadores con un rol específico (actual)"""
        return [p for p in self.players if p['current_role'] == role]


# Función específica para la acción de los lobos
def execute_werewolf_action(game, socket_id, action_data):
    player = game.get_player_by_socket_id(socket_id)
    if not player:
        return {'success': False, 'error': 'Jugador no encontrado'}

    print(f"DEBUG: Player {player['username']} actúa como lobo")

    if not game.can_player_act_in_phase(socket_id, 'werewolf'):
        return {'success': False, 'error': 'No puedes actuar ahora'}

    werewolves = game.get_players_with_role('werewolf')
    other_werewolves = [
        {'username': w['username'], 'socket_id': w['socket_id']}
        for w in werewolves if w['socket_id'] != socket_id
    ]

    center_card = None
    is_lone_wolf = len(werewolves) == 1

    if is_lone_wolf and 'center_index' in action_data:
        index = action_data['center_index']
        if 0 <= index < len(game.center_cards):
            center_card = {
                'index': index,
                'role': game.ROLE_NAMES.get(game.center_cards[index], game.center_cards[index])
            }
            player['has_acted'] = True
    elif not is_lone_wolf:
        player['has_acted'] = True

    return {
        'success': True,
        'other_werewolves': other_werewolves,
        'center_card': center_card,
        'is_lone_wolf': is_lone_wolf,
        'auto_reveal': not is_lone_wolf
    }
