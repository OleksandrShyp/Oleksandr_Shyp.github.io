from threading import Lock
from flask import Flask, render_template, session, request     #Knižnica web
from flask_socketio import SocketIO, emit, disconnect          #Knižnica pre prácu so socketmi
import time                                                    #Knižnica pre nastavenie času
import serial                                                  #Knižnica pre seriovu komunikaciu
import re
import json                                                    #Knižnica pre pracu s JSON
from flask_sqlalchemy import SQLAlchemy                        #Knižnica pre pracu s databazou SQLite 
from datetime import datetime                                  #Knižnica pre nastavenie čas a datum

async_mode = None

app = Flask(__name__)                                           #Aplikacia Flask 
app.config['SECRET_KEY'] = 'secret!'                             #Nastavujeme tajný kľúč aplikácie Flask
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///newflask.db'  #URI  pre databázu, ktorú bude aplikácia používať  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)                                            # Vytvárame inštanciu SQLAlchemy a priraďujeme ju k aplikácii Flask

class JoystickData(db.Model):                       #Definujeme model JoystickData pre databázovú tabuľku, ktorá bude obsahovať ID, počítadlo, údaje z joysticku (ux, uy, x, y) a datum
    id = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer, nullable=False)
    ux = db.Column(db.Integer, nullable=False)
    uy = db.Column(db.Integer, nullable=False)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

socketio = SocketIO(app, async_mode=async_mode)                                  #Inicializujeme SocketIO
thread = None
thread_lock = Lock()
arduino_serial = serial.Serial()                                                 # Inicializujeme sériovú komunikáciu pre Arduino
arduino_serial.port = 'COM3'                                                     # Port 3 Arduino
arduino_serial.baudrate = 9600                                                   # Rychlost 9600 baudov
generating = False                                                               # Počiatočnú hodnotu pre generovanie údajov na False
interval_value = 1000                                                            # Interval posielanie dat  

def stop_generation_timer():                                                     # unkcia na zastavenie generovanie udajov
    global generating
    generating = False

def background_thread():                                                         # Funkcia, ktora čita udaje zo serioveho portu
    count = 0                                                                    
    time.sleep(1)
    while True:
        try:
            if generating:                                                       # Ak sa generovanie údajov spustí, údaje sa prečítajú, spracujú a uložia do databázy a súboru
                if not arduino_serial.is_open:
                    arduino_serial.open()
                data = arduino_serial.readline().decode('utf-8').strip()
                print(f"Raw data received: {data}")
                match = re.search(r'UX = (\d+), UY = (\d+), y = (\d+), x = (\d+)', data)  # Čitam konkrene hodnoty joystika x y, a riadok a stlpec bodky na displeji
                if match:
                    ux = int(match.group(1))
                    uy = int(match.group(2))
                    x = int(match.group(3))
                    y = int(match.group(4))
                    count += 1
                    with app.app_context():                                                                                      #zapis do databazy
                        joystick_data = JoystickData(count=count, ux=ux, uy=uy, x=x, y=y)                             
                        db.session.add(joystick_data)
                        db.session.commit()                                                                                      
                    socketio.emit('my_response', {'data': {'count': count, 'ux': ux, 'uy': uy, 'y': x, 'x': y}}, namespace='/test')       
                    with open("file.txt", "a") as file:                                                                            #zapis do suboru   
                       file.write(f"Count: {str(count).rjust(5)}, Y-Joystick: {str(uy).rjust(5)}, X-Joystick: {str(ux).rjust(5)}, Riadok: {str(x).rjust(5)}, Stlpec: {str(y).rjust(5)}\n")
                else:
                    print(f"No match found in data: {data}")                             # V prípade chyby pri čítaní sériového portu alebo iných chýb sa tieto chyby ohlásia                            
            time.sleep(interval_value / 1000.0)  
        except serial.SerialException as e:
            print("Serial port error:", e)
            arduino_serial.close()
        except Exception as e:
            print("Error:", e)

def clear_database():                                                                    # Definujeme funkciu na vyčistenie databázy, ktorá odstráni všetky tabuľky a znovu ich vytvorí.
    with app.app_context():
        db.drop_all()
        db.create_all()

def clear_file():                                                                         # Definujeme funkciu na vyčistenie súboru
    with open("file.txt", "w") as file:
        file.write("")

@app.route('/')                                                                            #Pri načítaní stránky vyčistí databázu a súbor
def index():
    clear_db()  
    clear_file()  
    return render_template('index.html', async_mode=socketio.async_mode)

@app.route('/clear_db')                                                                     # Vyčistenie stavu databázy
def clear_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
    return "Database cleared!", 200

@socketio.on('set_interval', namespace='/test')                                             # Interval generovania údajov
def set_interval(message):
    global interval_value
    interval_value = int(message['interval'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response', {'data': {'message': f'Interval nastavený na {interval_value} ms'}, 'count': session['receive_count']})

@app.route('/gauge', methods=['GET', 'POST'])                                               # Gauge.html
def gauge():
    return render_template('gauge.html', async_mode=socketio.async_mode)


@app.route('/graphlive', methods=['GET', 'POST'])                                            # Graphlive.html
def graphlive():
    return render_template('graphlive.html', async_mode=socketio.async_mode)

@socketio.on('my_event', namespace='/test')                                                    # my_event prijíma správu, zvyšuje počítadlo v session a odošle spätnú väzbu klientov                               
def test_message(message):   
    session['receive_count'] = session.get('receive_count', 0) + 1 
    emit('my_response', {'data': message['value'], 'count': session['receive_count']})

@socketio.on('disconnect_request', namespace='/test')                                           #  Slúži na to, aby klient mohol požiadať server o odpojenie
def disconnect_request():
    try:
        session['receive_count'] = session.get('receive_count', 0) + 1
        emit('my_response', {'data': 'Disconnected!', 'count': session['receive_count']})
        print(f"Client {request.sid} requested disconnection.")
        disconnect()
    except Exception as e:
        print(f"Error during disconnect request: {e}")

@socketio.on('connect', namespace='/test')                                                                  # Pripojenie clienta
def test_connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=background_thread)

@socketio.on('disconnect', namespace='/test')                                                               # Odpojenia clienta, vypíše do konzoly správu, že klient bol odpojený,
def test_disconnect():
    print(f'Client disconnected: {request.sid}')

@socketio.on('start_generation', namespace='/test')                                                         # Start generovanie údajov
def start_generation():
    global generating
    generating = True

@socketio.on('stop_generation', namespace='/test')                                                           # Zastavenie generovanie údajov
def stop_generation():
    global generating
    generating = False

if __name__ == '__main__':                                                                                   # Spustenie aplikacie
    clear_database()  
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
