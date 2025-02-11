from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret!')
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='gevent') 

# Base de datos simulada
stations = {
    "Estación 1": [],
    "Estación 2": [],
    "Estación 3": []
}

def remove_vehicle_from_other_stations(plate, current_station):
    """Elimina el vehículo de todas las estaciones excepto la actual."""
    for station, vehicles in stations.items():
        if station != current_station:
            stations[station] = [v for v in vehicles if v['plate'] != plate]

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API de gestión de estaciones"})

@app.route('/stations', methods=['GET'])
def get_stations():
    """Devuelve las estaciones con sus vehículos."""
    return jsonify(stations)

@app.route('/add_vehicle', methods=['POST'])
def add_vehicle():
    """Agrega un vehículo a una estación."""
    data = request.get_json()
    station = data.get('station')
    plate = data.get('plate')

    if not station or not plate:
        return jsonify({"error": "Datos incompletos"}), 400

    # Validar matrícula (1 a 60, siempre mostrar como tres dígitos)
    try:
        plate_num = int(plate)
        if plate_num < 1 or plate_num > 60:
            return jsonify({"error": "La matrícula debe estar entre 1 y 60"}), 400
        plate = f"{plate_num:03d}"  # Convertir a formato de 3 dígitos
    except ValueError:
        return jsonify({"error": "La matrícula debe ser un número válido"}), 400

    # Eliminar el vehículo de otras estaciones
    remove_vehicle_from_other_stations(plate, station)

    # Verificar si el vehículo ya está en la estación actual
    for vehicle in stations[station]:
        if vehicle['plate'] == plate:
            return jsonify({"error": "El vehículo ya está registrado en esta estación"}), 400

    # Agregar el vehículo a la estación actual con estado "Parqueado"
    vehicle = {
        "plate": plate,
        "status": "Parqueado",  # Estado inicial
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    stations[station].append(vehicle)

    # Emitir actualización en tiempo real
    socketio.emit('update', stations, broadcast=True)
    return jsonify(vehicle), 201

@app.route('/vehicle/<station>/<plate>', methods=['PUT'])
def update_vehicle(station, plate):
    """Cambia el estado de un vehículo."""
    if station not in stations:
        return jsonify({"error": "Estación no encontrada"}), 404

    for vehicle in stations[station]:
        if vehicle['plate'] == plate:
            # Cambiar estado en ciclo: Parqueado -> Normal -> Colado -> Anotado -> Mantenimiento
            if vehicle['status'] == "Parqueado":
                vehicle['status'] = "Normal"
            elif vehicle['status'] == "Normal":
                vehicle['status'] = "Colado"
            elif vehicle['status'] == "Colado":
                vehicle['status'] = "Anotado"
            elif vehicle['status'] == "Anotado":
                vehicle['status'] = "Mantenimiento"
            else:
                vehicle['status'] = "Parqueado"

            vehicle['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Emitir actualización en tiempo real
            socketio.emit('update', stations, broadcast=True)
            return jsonify(vehicle)

    return jsonify({"error": "Vehículo no encontrado"}), 404

@app.route('/transfer', methods=['POST'])
def transfer_vehicle():
    """Transfiere un vehículo de una estación a otra (solo si no está en estado "Parqueado")."""
    data = request.get_json()
    origin = data.get('origin')
    destination = data.get('destination')
    plate = data.get('plate')

    if not origin or not destination or not plate:
        return jsonify({"error": "Datos incompletos"}), 400

    if origin not in stations or destination not in stations:
        return jsonify({"error": "Estación no válida"}), 404

    # Buscar y transferir el vehículo
    for vehicle in stations[origin]:
        if vehicle['plate'] == plate:
            if vehicle['status'] == "Parqueado":
                return jsonify({"error": "El vehículo no puede transferirse porque está en estado 'Parqueado'"}), 400

            # Conservar la hora del último estado
            last_timestamp = vehicle['timestamp']
            stations[origin].remove(vehicle)
            vehicle['status'] = "Parqueado"  # Restaurar estado al transferir
            vehicle['timestamp'] = last_timestamp  # Conservar la hora del último estado
            stations[destination].append(vehicle)

            # Emitir actualización en tiempo real
            socketio.emit('update', stations, broadcast=True)
            return jsonify(vehicle)

    return jsonify({"error": "Vehículo no encontrado en la estación de origen"}), 404

@socketio.on('connect')
def handle_connect():
    """Envía el estado inicial de las estaciones al conectarse un cliente."""
    emit('update', stations)

@socketio.on('disconnect')
def handle_disconnect():
    """Maneja la desconexión de un cliente."""
    print('Cliente desconectado')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
