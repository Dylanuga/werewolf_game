from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string
from game_logic import GameLogic, execute_werewolf_action, ROLE_NAMES

# Crear la aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'

# Inicializar SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Almacenar información de salas y jugadores
rooms = {}  # room_code: {'players': [player_data], 'game_state': 'waiting', 'game': GameLogic}
players = {}  # socket_id: {'username': str, 'room_code': str}

def generate_room_code():
    """Genera un código de sala de 4 letras"""
    return ''.join(random.choices(string.ascii_uppercase, k=4))

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/debug')
def debug():
    """Página de debug"""
    return render_template('debug.html')

@socketio.on('connect')
def handle_connect():
    """Cuando un usuario se conecta"""
    print(f'Usuario conectado: {request.sid}')
    emit('status', {'msg': 'Conectado al servidor!'})

@socketio.on('disconnect')
def handle_disconnect():
    """Cuando un usuario se desconecta"""
    print(f'Usuario desconectado: {request.sid}')
    
    # Si el jugador estaba en una sala, removerlo
    if request.sid in players:
        player_data = players[request.sid]
        room_code = player_data['room_code']
        
        # Remover jugador de la sala
        if room_code in rooms:
            rooms[room_code]['players'] = [
                p for p in rooms[room_code]['players'] 
                if p['socket_id'] != request.sid
            ]
            
            # Si la sala quedó vacía, eliminarla
            if not rooms[room_code]['players']:
                del rooms[room_code]
            else:
                # Notificar a otros jugadores de la sala
                socketio.emit('room_updated', {
                    'players': rooms[room_code]['players'],
                    'room_code': room_code
                }, room=room_code)
        
        # Remover jugador del registro
        del players[request.sid]

@socketio.on('create_room')
def handle_create_room(data):
    """Crear una nueva sala"""
    username = data['username'].strip()
    
    if not username or len(username) > 20:
        emit('error', {'msg': 'Nombre inválido'})
        return
    
    # Generar código único
    room_code = generate_room_code()
    while room_code in rooms:
        room_code = generate_room_code()
    
    # Crear datos del jugador
    player_data = {
        'socket_id': request.sid,
        'username': username,
        'is_host': True
    }
    
    # Crear sala
    rooms[room_code] = {
        'players': [player_data],
        'game_state': 'waiting',
        'host_id': request.sid
    }
    
    # Registrar jugador
    players[request.sid] = {
        'username': username,
        'room_code': room_code
    }
    
    # Unir al jugador a la sala de Socket.IO
    join_room(room_code)
    
    print(f'{username} creó la sala {room_code}')
    
    emit('room_created', {
        'room_code': room_code,
        'username': username,
        'is_host': True
    })
    
    emit('room_updated', {
        'players': rooms[room_code]['players'],
        'room_code': room_code
    })

@socketio.on('join_room')
def handle_join_room(data):
    """Unirse a una sala existente"""
    username = data['username'].strip()
    room_code = data['room_code'].strip().upper()
    
    if not username or len(username) > 20:
        emit('error', {'msg': 'Nombre inválido'})
        return
    
    if not room_code or room_code not in rooms:
        emit('error', {'msg': 'Sala no encontrada'})
        return
    
    # Verificar que el nombre no esté en uso en esta sala
    existing_names = [p['username'].lower() for p in rooms[room_code]['players']]
    if username.lower() in existing_names:
        emit('error', {'msg': 'Ese nombre ya está en uso en esta sala'})
        return
    
    # Verificar límite de jugadores (máximo 10 para One Night Werewolf)
    if len(rooms[room_code]['players']) >= 10:
        emit('error', {'msg': 'La sala está llena'})
        return
    
    # Crear datos del jugador
    player_data = {
        'socket_id': request.sid,
        'username': username,
        'is_host': False
    }
    
    # Agregar jugador a la sala
    rooms[room_code]['players'].append(player_data)
    
    # Registrar jugador
    players[request.sid] = {
        'username': username,
        'room_code': room_code
    }
    
    # Unir al jugador a la sala de Socket.IO
    join_room(room_code)
    
    print(f'{username} se unió a la sala {room_code}')
    
    emit('room_joined', {
        'room_code': room_code,
        'username': username,
        'is_host': False
    })
    
    # Notificar a todos en la sala
    socketio.emit('room_updated', {
        'players': rooms[room_code]['players'],
        'room_code': room_code
    }, room=room_code)

@socketio.on('start_game')
def handle_start_game():
    """Iniciar el juego (solo el host puede hacerlo)"""
    if request.sid not in players:
        emit('error', {'msg': 'No estás en una sala'})
        return
    
    room_code = players[request.sid]['room_code']
    
    # Verificar que sea el host
    if rooms[room_code]['host_id'] != request.sid:
        emit('error', {'msg': 'Solo el host puede iniciar el juego'})
        return
    
    # Verificar mínimo de jugadores (3 para testing, ideal 5+)
    if len(rooms[room_code]['players']) < 3:
        emit('error', {'msg': 'Necesitas al menos 3 jugadores para empezar'})
        return
    
    # Crear instancia del juego
    game = GameLogic(rooms[room_code]['players'].copy(), room_code)
    game_setup = game.setup_game()
    
    # Guardar el juego en la sala
    rooms[room_code]['game'] = game
    rooms[room_code]['game_state'] = 'preparation'  # Cambiar a preparación
    
    # Notificar a todos que el juego comenzó (sin roles aún)
    socketio.emit('game_started', {
        'msg': '🌙 ¡El juego comenzó! Es de noche...',
        'phase_order': game_setup['phase_order']
    }, room=room_code)
    
    # Fase inicial: "Cerrad los ojos todos" (SIN enviar roles aún)
    socketio.emit('narrator_message', {
        'message': '🌙 Cerrad los ojos todos...',
        'phase': 'eyes_closed'
    }, room=room_code)
    
    # Después de 5 segundos: asignar roles y comenzar fases nocturnas
    import threading
    timer = threading.Timer(5.0, lambda: start_role_assignment_and_night(room_code))
    timer.start()
    
    print(f'Juego iniciado en sala {room_code} con {len(game.players)} jugadores')

def start_role_assignment_and_night(room_code: str):
    """Asigna roles después de la preparación y comienza la noche"""
    if room_code not in rooms or 'game' not in rooms[room_code]:
        print(f"DEBUG: Sala {room_code} no encontrada en start_role_assignment_and_night")
        return
        
    game = rooms[room_code]['game']
    print(f"DEBUG: Iniciando asignación de roles en sala {room_code}")
    
    # AHORA sí enviar roles secretos a cada jugador
    for player in game.players:
        role_name = ROLE_NAMES.get(player['original_role'], player['original_role'])
        print(f"DEBUG: Enviando rol {player['original_role']} ({role_name}) a {player['username']} (socket: {player['socket_id']})")
        
        # Verificar si el socket_id existe en la lista de jugadores conectados
        socket_exists = False
        for socket_id, player_data in players.items():
            if socket_id == player['socket_id']:
                socket_exists = True
                break
        
        if socket_exists:
            socketio.emit('your_role', {
                'role': player['original_role'],
                'role_name': role_name,
                'description': f'Tu rol secreto es: {role_name}'
            }, to=player['socket_id'])  # Cambiar 'room' por 'to'
            print(f"DEBUG: ✅ Rol enviado a {player['username']}")
        else:
            print(f"DEBUG: ❌ Socket {player['socket_id']} no existe para {player['username']}")
    
    rooms[room_code]['game_state'] = 'night'
    print(f"DEBUG: Estado cambiado a 'night' para sala {room_code}")
    
    # Comenzar la primera fase nocturna
    if game.phase_order:
        print(f"DEBUG: Iniciando fases nocturnas. Orden: {game.phase_order}")
        start_next_night_phase(room_code)
    else:
        print(f"DEBUG: No hay fases nocturnas programadas")

def start_next_night_phase(room_code: str):
    """Inicia la siguiente fase nocturna"""
    if room_code not in rooms or 'game' not in rooms[room_code]:
        return
        
    game = rooms[room_code]['game']
    
    if not game.phase_order:
        # No hay más fases, terminar la noche
        end_night_phase(room_code)
        return
    
    # Obtener la siguiente fase
    current_phase = game.phase_order.pop(0)
    phase_info = game.start_night_phase(current_phase)
    
    print(f'Iniciando fase: {current_phase} en sala {room_code}')
    
    # Notificar a todos sobre la fase actual
    socketio.emit('night_phase_started', {
        'phase': phase_info['phase'],
        'role_name': phase_info['role_name'],
        'description': phase_info['description']
    }, room=room_code)
    
    # SPECIAL CASE: Lobos se ven automáticamente
    if current_phase == 'werewolf':
        print(f"DEBUG: Procesando fase de lobos en sala {room_code}")
        
        # Pequeño delay para asegurar que los clientes estén listos
        import threading
        
        def send_werewolf_info():
            # Enviar información automática a cada lobo
            for player_info in phase_info['players_can_act']:
                print(f"DEBUG: Procesando lobo: {player_info['username']}")
                result = execute_werewolf_action(game, player_info['socket_id'], {})
                print(f"DEBUG: Resultado para {player_info['username']}: {result}")
                
                # Si es lobo solitario, permitir elegir carta del centro
                if result['is_lone_wolf']:
                    socketio.emit('your_turn', {
                        'phase': current_phase,
                        'role_name': phase_info['role_name'],
                        'can_act': True,
                        'action_type': 'choose_center_card',
                        'werewolf_info': {
                            'other_werewolves': result['other_werewolves'],
                            'is_lone_wolf': True,
                            'message': 'Eres el único lobo. Puedes elegir UNA carta del centro para ver.'
                        }
                    }, to=player_info['socket_id'])  # Cambiar 'room' por 'to'
                    print(f"DEBUG: {player_info['username']} es lobo solitario")
                else:
                    # Para múltiples lobos, enviar la información directamente
                    other_wolves_names = [w['username'] for w in result['other_werewolves']]
                    message = f"El otro lobo es: {', '.join(other_wolves_names)}" if len(other_wolves_names) == 1 else f"Los otros lobos son: {', '.join(other_wolves_names)}"
                    
                    socketio.emit('werewolf_multiple_info', {
                        'other_werewolves': result['other_werewolves'],
                        'is_lone_wolf': False,
                        'message': message
                    }, to=player_info['socket_id'])  # Cambiar 'room' por 'to'
                    
                    print(f"DEBUG: {player_info['username']} tiene otros lobos: {other_wolves_names}")
            
            # Si no hay lobos solitarios, verificar si la fase está completa
            werewolves = game.get_players_with_role('werewolf')
            if len(werewolves) > 1:
                print(f"DEBUG: Múltiples lobos ({len(werewolves)}), avanzando automáticamente")
                # Todos los lobos ya "actuaron" automáticamente, continuar
                timer2 = threading.Timer(4.0, lambda: start_next_night_phase(room_code))
                timer2.start()
        
        # Enviar la info después de 1 segundo
        timer = threading.Timer(1.0, send_werewolf_info)
        timer.start()
    else:
        # Para otros roles, notificar normalmente
        for player_info in phase_info['players_can_act']:
            socketio.emit('your_turn', {
                'phase': current_phase,
                'role_name': phase_info['role_name'],
                'can_act': True
            }, to=player_info['socket_id'])  # Cambiar 'room' por 'to'

def end_night_phase(room_code: str):
    """Termina la fase nocturna e inicia la discusión"""
    if room_code not in rooms or 'game' not in rooms[room_code]:
        return
        
    rooms[room_code]['game_state'] = 'discussion'
    
    socketio.emit('night_ended', {
        'msg': '☀️ ¡Amaneció! Es hora de discutir...',
        'phase': 'discussion'
    }, room=room_code)
    
    print(f'Fase nocturna terminada en sala {room_code}')

@socketio.on('night_action')
def handle_night_action(data):
    """Manejar acciones nocturnas de los jugadores"""
    if request.sid not in players:
        emit('error', {'msg': 'No estás en una sala'})
        return
        
    room_code = players[request.sid]['room_code']
    
    if (room_code not in rooms or 
        'game' not in rooms[room_code] or 
        rooms[room_code]['game_state'] != 'night'):
        emit('error', {'msg': 'No es el momento de actuar'})
        return
    
    game = rooms[room_code]['game']
    action_type = data.get('action_type')
    
    # Ejecutar acción según el tipo
    result = None
    if action_type == 'werewolf':
        result = execute_werewolf_action(game, request.sid, data)
    
    if result and result.get('success'):
        emit('action_result', result)
        
        # Si el lobo solitario eligió una carta del centro, avanzar después de 3 segundos
        if (action_type == 'werewolf' and 
            result.get('center_card') and 
            result.get('is_lone_wolf')):
            print(f"DEBUG: Lobo solitario eligió carta del centro, avanzando en 3 segundos")
            import threading
            timer = threading.Timer(3.0, lambda: start_next_night_phase(room_code))
            timer.start()
        else:
            # Para otros casos, verificar si todos completaron la fase
            check_phase_completion(room_code)
    else:
        emit('error', {'msg': result.get('error', 'Acción inválida')})

def check_phase_completion(room_code: str):
    """Verifica si todos los jugadores de la fase actual completaron sus acciones"""
    if room_code not in rooms or 'game' not in rooms[room_code]:
        return
        
    game = rooms[room_code]['game']
    current_phase = game.current_phase
    
    # Verificar si todos los jugadores que podían actuar ya actuaron
    players_in_phase = [p for p in game.players if p['original_role'] == current_phase]
    all_acted = all(p['has_acted'] for p in players_in_phase)
    
    if all_acted:
        # Continuar con la siguiente fase después de un delay
        socketio.emit('phase_completed', {
            'phase': current_phase,
            'msg': f'Todos los {current_phase} terminaron. Continuando...'
        }, room=room_code)
        
        # Usar un timer para dar tiempo a que se procese
        import threading
        timer = threading.Timer(2.0, lambda: start_next_night_phase(room_code))
        timer.start()

if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)