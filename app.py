from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, 
                  cors_allowed_origins="*",
                  async_mode='gevent')
stations = {
    "Estación 1": [],
    "Estación 2": [],
    "Estación 3": []
}

def remove_vehicle_from_other_stations(plate, current_station):
    for station, vehicles in stations.items():
        if station != current_station:
            stations[station] = [v for v in vehicles if v['plate'] != plate]


@app.route('/stations', methods=['GET'])
def get_stations():
    return jsonify(stations)

@app.route('/add_vehicle', methods=['POST'])
def add_vehicle():
    try:
        data = request.get_json()
        station = data.get('station')
        plate = data.get('plate')

        # Nueva validación para matrículas negativas
        is_negative = plate.startswith('-')
        plate_num = plate.lstrip('-')
        # Validar formato numérico
        if not plate_num.isdigit():
            return jsonify({"error": "Formato de matrícula inválido"}), 400
            
        plate_num = int(plate_num)
        if not (1 <= plate_num <= 60):
            return jsonify({"error": "Matrícula fuera de rango"}), 400

        formatted_plate = f"{plate_num:03d}"

        # Validar si el vehículo existe en otro estado no transferible
        for s in stations.values():
            for v in s:
                if any(v['plate'] == plate for v in stations[station]):
                    return jsonify({"error": "Matrícula ya existe en esta estación"}), 400
                if v['plate'] == plate and v['status'] in ['parqueado', 'anotado', 'mantenimiento']:
                    return jsonify({"error": "No se puede transferir en este estado"}), 400
                

        if not station or not plate:
            return jsonify({"error": "Datos incompletos"}), 400

        if station not in stations:
            return jsonify({"error": "Estación no válida"}), 404
        
        # Buscar vehículo existente en cualquier estación
        existing_vehicle = None
        penalty_seconds = 0
        for s_name, s_vehicles in stations.items():
            for v in s_vehicles:
                if v['plate'] == formatted_plate:
                    existing_vehicle = v
                    # Solo aplicar penalización si NO es transferencia negativa
                    if not is_negative and v['status'] in ['normal', 'colado']:
                        tiempo_transcurrido = (datetime.utcnow() - datetime.strptime(v['timestamp'], '%Y-%m-%d %H:%M:%S')).total_seconds()
                        if tiempo_transcurrido > 300:
                            penalty_seconds = tiempo_transcurrido - 300
                    break
            
        # Eliminar de otras estaciones
        remove_vehicle_from_other_stations(plate, station)

        if existing_vehicle:
            # Aplicar penalización al timestamp original
            new_time = datetime.strptime(existing_vehicle['timestamp'], '%Y-%m-%d %H:%M:%S') + timedelta(seconds=penalty_seconds)
            vehicle = {
                "plate": plate,
                "status": "parqueado",
                "timestamp": new_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            vehicle = {
                "plate": plate,
                "status": "parqueado",
                "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            }

        stations[station].append(vehicle)
        socketio.emit('update', stations, namespace='/')
        return jsonify(vehicle), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/vehicle/<station>/<plate>', methods=['PUT'])
def update_vehicle(station, plate):
    try:
        data = request.get_json()
        new_status = data.get('status', '').lower()

        valid_statuses = ["parqueado", "normal", "colado", "anotado", "mantenimiento"]
        if new_status not in valid_statuses:
            return jsonify({"error": "Estado inválido"}), 400

        if station not in stations:
            return jsonify({"error": "Estación no encontrada"}), 404

        for vehicle in stations[station]:
            if vehicle['plate'] == plate:
                vehicle['status'] = new_status
                if new_status not in ["parqueado", "anotado", "mantenimiento"]:
                    vehicle['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                socketio.emit('update', stations, namespace='/')
                return jsonify(vehicle), 200

        return jsonify({"error": "Vehículo no encontrado"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['DELETE'])
def reset_daily_data():
    try:
        for station in stations:
            stations[station] = []
        socketio.emit('update', stations, namespace='/')
        return jsonify({"message": "Datos reiniciados"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@socketio.on('connect', namespace='/')
def handle_connect():
    try:
        emit('update', stations, namespace='/')
    except Exception as e:
        print(f"Error en connect: {str(e)}")


@socketio.on('request_update', namespace='/')
def handle_request_update():
    try:
        emit('update', stations, namespace='/', broadcast=True)
    except Exception as e:
        print(f"Error en request_update: {str(e)}")

if __name__ == '__main__':
    socketio.run(app, 
               host='0.0.0.0', 
               port=10000,
               allow_unsafe_werkzeug=True)