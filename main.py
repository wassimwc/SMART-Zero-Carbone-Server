from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from influxdb import InfluxDBClient
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from contextlib import asynccontextmanager
import fuzzy_logic as fz
import asyncio
import logging
import os

buffer = defaultdict(dict)
received_batches = defaultdict(dict)
EE_consumptions = defaultdict(dict)
command = defaultdict(dict)
act_event = asyncio.Event()
sen_event = asyncio.Event()
sen_event.set()
regulator_task = None
aggregate_task = None
time_delay = 3
sys_to_command = {
  "heater_sys" : "heater_pwm",
  "air_cond_sys" : "air_cond_pwm",
  "voc_ventilation_sys" : "vent_pwm1",
  "co2_ventilation_sys" : "vent_pwm2",
  "hum_dehum_sys" : "dehum_pwm"
}
origins = []


# InfluxDB connection details
INFLUXDB_HOST = "localhost"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "smart_zero_carbone"
INFLUXDB_USERNAME = "admin"  # Replace with your actual username
INFLUXDB_PASSWORD = os.getenv("INFLUXDB_PASSWORD")

# Initialize InfluxDB Client
client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USERNAME, password=INFLUXDB_PASSWORD)
client.switch_database(INFLUXDB_DATABASE)



@asynccontextmanager
async def lifespan(app: FastAPI):
  query = f'SELECT LAST(EE_consumption), company, location FROM sensor_data GROUP BY company, location'
  gen = client.query(query).get_points()
  for value in gen:
      company, location = value['company'], value['location']
      EE_consumptions[company, location] = value.get('EE_consumption', 0)
      command[company, location] = {'heater_pwm' : 0, 'air_cond_pwm' : 0, "vent_pwm1" : 0, "vent_pwm2" : 0, 'dehum_pwm' : 0, 'pump_pwm' : 0}
  asyncio.create_task(main())
  yield


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your frontend origin
    allow_credentials=True,
    allow_methods=["*"],    # Allow all HTTP methods
    allow_headers=["*"],    # Allow all headers
)

async def main():
  global regulator_task, aggregate_task
  while True:
    await asyncio.sleep(time_delay)
    aggregate_task = asyncio.create_task(aggregate_sensors_data())
    regulator_task = asyncio.create_task(regulator())
    asyncio.create_task(handle_db_queries())
    act_event.set()
    sen_event.set()


async def aggregate_sensors_data():
  buffer.clear()
  for (company, location), new_data in received_batches.items():
    buffer[company, location].update(new_data)
    avg_power = new_data.get("power", 0)
    old_EE_consumption = EE_consumptions[company, location]
    EE_consumptions[company, location] = old_EE_consumption + avg_power/(1000*3600)
    buffer[company, location]['EE_consumption'] = EE_consumptions[company, location]
  received_batches.clear()

async def handle_db_queries():
    await aggregate_task
    json_body = []
    try:
        for company, location in buffer.keys():
            data_element = {
                "measurement": "sensor_data",
                "tags": {
                    "company": company,
                    "location": location
                },
                "fields": buffer[company, location]
            }
            json_body.append(data_element)
            
        # Write all data points at once
        client.write_points(json_body)
        

    except Exception as e:
        logging.error(f"Error writing data to InfluxDB: {e}")
        raise HTTPException(status_code=500, detail=f"Error writing data to InfluxDB: {e}")

async def regulator():
    await aggregate_task
    for company, location in buffer.keys():
        for sys_name, sys in fz.systems.items():
            cond = fz.env[sys_name]
            value = buffer[company, location].get(cond)
            if value :
                sys.input[cond] = value
                sys.compute()
                command_name = sys_to_command[sys_name]
                command[company, location][command_name] = sys.output["pwm"]



def calculate_power_factor(voltage_rms, current_rms, avg_power):
	if any(voltage_rms, current_rms, avg_power is not None):
		power_factor = avg_power/(voltage_rms*current_rms)
		return power_factor
	return None
actuators_active_connections = []

@app.websocket("/pwm_commands")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()  # Accept the WebSocket connection
    info = await websocket.receive_json()
    actuators_active_connections.append(websocket)  # Add to active connections

    try:
        while True:
              await act_event.wait()
              await regulator_task
              pwm = str(command[info["company"], info["location"]].get(info["system_type"]))
              await websocket.send_text(pwm)
              act_event.clear()
    except WebSocketDisconnect:
        if websocket in actuators_active_connections:
            actuators_active_connections.remove(websocket)
            print("Client disconnected")


sensors_active_connections = []
    
@app.websocket("/sensors_data")
async def receive_sensors_data(websocket : WebSocket):

    await websocket.accept()  # Accept the WebSocket connection
    info = await websocket.receive_json()
    sensors_active_connections.append(websocket)  # Add to active connections
    try:
        while True:
            await sen_event.wait()
            await websocket.send_text("send_data")
            data = await websocket.receive_json()
            company = info["company"]
            location = info["location"]
            voltage_rms = data.pop("voltage_rms", None)
            current_rms = data.pop("current_rms", None)
            avg_power = data.get("avg_power", None)
            power_factor = data.pop("power_factor", None) or calculate_power_factor(voltage_rms, current_rms, avg_power)
            if power_factor:
                data["power_factor"] = power_factor
            received_batches[(company, location)] = data
            sen_event.clear()
    except WebSocketDisconnect:
        if websocket in sensors_active_connections:
            sensors_active_connections.remove(websocket)
            print("Client disconnected")

@app.get("/search_company/")
async def get_data(company_name : str):
    # InfluxQL query to fetch data
    query = f'SELECT * FROM "sensor_data" WHERE "company" = \'{company_name}\' ORDER BY time DESC LIMIT 10'

    try:
        # Execute the query and get the result
        result = client.query(query)
        return list(result.get_points()) # Return the result as a list of data points
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying InfluxDB: {e}")
