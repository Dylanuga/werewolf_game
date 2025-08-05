from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string

# Crear la aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'

# Inicializar SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Almacenar información de salas y jugadores
rooms = {}  # room_code: {'players': [player_data], 'game_state': 'waiting'}
players = {}  # socket_id: {'username': str, 'room_code': str}

def generate_room_code():
    """Genera un código de sala de 4 letras"""
    return ''.join(random.choices(string.ascii_uppercase, k=4))

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

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
    
    rooms[room_code]['game_state'] = 'starting'
    
    # Notificar a todos en la sala
    socketio.emit('game_starting', {
        'msg': '¡El juego está comenzando!'
    }, room=room_code)
    
    print(f'Juego iniciado en sala {room_code}')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)