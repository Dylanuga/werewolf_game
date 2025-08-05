from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit
from game_logic import GameLogic, execute_werewolf_action
import random

app = Flask(__name__)
socketio = SocketIO(app)

rooms = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']

    join_room(room)

    if room not in rooms:
        rooms[room] = {
            'players': [],
            'game': None
        }

    rooms[room]['players'].append({
        'username': username,
        'socket_id': request.sid,
        'original_role': None,
        'current_role': None,
        'has_acted': False
    })

    emit('room_joined', {'room': room, 'username': username}, room=room)
    emit('room_updated', {'players': [p['username'] for p in rooms[room]['players']]}, room=room)

@socketio.on('start_game')
def handle_start_game(data):
    room = data['room']
    if room not in rooms:
        return

    players = rooms[room]['players']
    game = GameLogic(players, room)
    result = game.setup_game()

    rooms[room]['game'] = game

    print(f"Juego iniciado en sala {room} con {len(players)} jugadores")
    print(f"DEBUG: Iniciando asignación de roles en sala {room}")

    # Enviar el rol individual a cada jugador
    for player in players:
        role_name = player['original_role']
        print(f"DEBUG: Enviando rol {role_name} ({game.ROLE_NAMES.get(role_name, role_name)}) a {player['username']} (socket: {player['socket_id']})")
        socketio.emit('your_role', {
            'role': role_name,
            'role_name': game.ROLE_NAMES.get(role_name, role_name)
        }, room=player['socket_id'])
        print(f"DEBUG: ✅ Rol enviado a {player['username']}")

    socketio.emit('game_started', {}, room=room)

    game.game_state = 'night'
    print(f"DEBUG: Estado cambiado a 'night' para sala {room}")
    start_next_night_phase(room)

def start_next_night_phase(room):
    game = rooms[room]['game']
    if not game.phase_order:
        print("DEBUG: Todas las fases completadas.")
        return

    next_phase = game.phase_order.pop(0)
    game.current_phase = next_phase
    print(f"Iniciando fase: {next_phase} en sala {room}")

    if next_phase == 'werewolf':
        print(f"DEBUG: Procesando fase de lobos en sala {room}")
        for player in game.players:
            if player['original_role'] == 'werewolf':
                print(f"DEBUG: Procesando lobo: {player['username']}")
                result = execute_werewolf_action(game, player['socket_id'], {})
                print(f"DEBUG: Resultado para {player['username']}: {result}")

                if result['is_lone_wolf'] and not result['auto_reveal']:
                    # Si es lobo solitario y puede ver una carta del centro, enviarle esa info
                    socketio.emit('night_phase_started', {
                        'phase': next_phase,
                        'description': f"Eres el único lobo. Puedes ver una carta del centro.",
                        'players_can_act': [{'socket_id': player['socket_id'], 'username': player['username']}],
                        'is_lone_wolf': True,
                        'center_card': None
                    }, room=player['socket_id'])
                else:
                    # Mostrarle al jugador los otros lobos (o nada si solo hay uno)
                    socketio.emit('night_phase_started', {
                        'phase': next_phase,
                        'description': "Fase de lobos",
                        'players_can_act': [{'socket_id': player['socket_id'], 'username': player['username']}],
                        'is_lone_wolf': False,
                        'other_werewolves': result['other_werewolves'],
                        'center_card': result['center_card']
                    }, room=player['socket_id'])

        return

    # Para otras fases
    data = game.start_night_phase(next_phase)
    socketio.emit('night_phase_started', data, room=room)

@socketio.on('role_action')
def handle_role_action(data):
    room = data['room']
    socket_id = request.sid
    phase = data['phase']
    action_data = data.get('action_data', {})

    game = rooms[room]['game']

    print(f"DEBUG: Acción recibida en fase {phase} de {socket_id}: {action_data}")

    if phase == 'werewolf':
        result = execute_werewolf_action(game, socket_id, action_data)
        emit('action_result', result, room=socket_id)

    # En versiones siguientes, añadir lógica para seer, robber, etc.

if __name__ == '__main__':
    socketio.run(app, debug=True)
