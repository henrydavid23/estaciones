from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

stations = {
    "Estación 1": [],
    "Estación 2": [],
    "Estación 3": []
}

def remove_vehicle_from_other_stations(plate, current_station):
    for station, vehicles in stations.items():
        if station != current_station:
            stations[station] = [v for v in vehicles if v['plate'] != plate]

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API de gestión de estaciones"})

@app.route('/stations', methods=['GET'])
def get_stations():
    return jsonify(stations)

@app.route('/add_vehicle', methods=['POST'])
def add_vehicle():
    try:
        data = request.get_json()
        station = data.get('station')
        plate = data.get('plate')

        if not station or not plate:
            return jsonify({"error": "Datos incompletos"}), 400

        if station not in stations:
            return jsonify({"error": "Estación no válida"}), 404

        remove_vehicle_from_other_stations(plate, station)

        existing = next((v for v in stations[station] if v['plate'] == plate), None)
        if existing:
            return jsonify({"error": "Vehículo ya existe"}), 400

        vehicle = {
            "plate": plate,
            "status": "parqueado",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
    emit('update', stations)

@socketio.on('request_update', namespace='/')
def handle_request_update():
    emit('update', stations)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
