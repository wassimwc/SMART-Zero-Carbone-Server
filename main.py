from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from influxdb import InfluxDBClient
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from collections import defaultdict
from contextlib import asynccontextmanager
import fuzzy_logic as fz
import asyncio
import logging
import os
import math


@asynccontextmanager
async def lifespan(app: FastAPI):
  query = f'SELECT EE_consumption, company, location FROM "sensor_data"'
  gen = client.query(query).get_points()
  for value in gen:
      company, location = value['company'], value['location']
      EE_consumptions[company, location] = value.get('EE_consumption', 0)
      command[company, location] = {'heater_pwm' : 0, 'air_cond_pwm' : 0, "vent_pwm" : 0, 'dehum_pwm' : 0, 'pump_pwm' : 0}
  asyncio.create_task(main())
  yield


app = FastAPI(lifespan=lifespan)

# InfluxDB connection details
INFLUXDB_HOST = "localhost"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "smart_zero_carbone"
INFLUXDB_USERNAME = "admin"  # Replace with your actual username
INFLUXDB_PASSWORD = os.getenv("INFLUXDB_PASSWORD")

# Initialize InfluxDB Client
client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USERNAME, password=INFLUXDB_PASSWORD)
client.switch_database(INFLUXDB_DATABASE)

origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://192.168.1.12:5500"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your frontend origin
    allow_credentials=True,
    allow_methods=["*"],    # Allow all HTTP methods
    allow_headers=["*"],    # Allow all headers
)

buffer = defaultdict(dict)
received_batches = defaultdict(dict)
EE_consumptions = defaultdict(dict)
command = defaultdict(dict)
act_event = asyncio.Event()
sen_event = asyncio.Event()
sen_event.set()
regulator_task = None
time_delay = 3


async def aggregate_sensors_data():
  buffer.clear()
  for (company, location), new_data in received_batches.items():
    buffer[company, location].update(new_data)
    avg_power = new_data.get("power", 0)
    old_EE_consumption = EE_consumptions[company, location].get("EE_consumption", 0)
    EE_consumptions[company, location] = old_EE_consumption + avg_power/(1000*3600)
    buffer[company, location]['EE_consumption'] = EE_consumptions[company, location]
  received_batches.clear()

async def handle_db_queries():
    json_body = []
    try:
        for company, location in buffer.keys():
            data_element = {
                "measurement": "sensor_data",
                "tags": {
                    "company": company,
                    "location": location
                },
                "fields": {
                    "temperature": buffer[company, location].get("temperature", float('nan')),
                    "humidity": buffer[company, location].get("humidity", float('nan')),
                    "co2": buffer[company, location].get("co2", float('nan')),
                    "o2": buffer[company, location].get("o2", float('nan')),
                    "voc": buffer[company, location].get("voc", float('nan')),
                    "renewable_EE": buffer[company, location].get("renewable_EE", float('nan')),
                    "EE_consumption": buffer[company, location].get('EE_consumption', float('nan')),
                    "power": buffer[company, location].get("power", float('nan')),
                    "power_factor": buffer[company, location].get("power_factor", float('nan')),
                    "soil_moisure": buffer[company, location].get("soil_moisure", float('nan')) 
                }
            }
            json_body.append(data_element)
            
            # Check for missing data (NaN)
            if any(math.isnan(value) for value in data_element['fields'].values()):
                missing_fields = [key for key, value in data_element['fields'].items() if math.isnan(value)]
                logging.warning(f"Missing data for company '{company}' at location '{location}': {missing_fields}")
                
        
        # Write all data points at once
        client.write_points(json_body)
        
    
    except Exception as e:
        logging.error(f"Error writing data to InfluxDB: {e}")
        raise HTTPException(status_code=500, detail=f"Error writing data to InfluxDB: {e}")
sys_to_command = {
  "heater_sys" : "heater_pwm",
  "air_cond_sys" : "air_cond_pwm",
  "voc_ventilation_sys" : "vent_pwm",
  "co2_ventilation_sys" : "vent_pwm",
  "hum_dehum_sys" : "dehum_pwm"
}
async def regulator():
    for company, location in buffer.keys():
        for sys_name, sys in fz.systems.items():
            cond = fz.env[sys_name]
            value = buffer[company, location].get(cond)
            if value :
                sys.input[cond] = value
                sys.compute()
        command[company, location]['heater_pwm'] = fz.heater_sys.output['pwm']
        command[company, location]['air_cond_pwm'] = fz.air_cond_sys.output['pwm']
        command[company, location]['vent_pwm'] = max(fz.voc_ventilation_sys.output.get('pwm', 0), fz.co2_ventilation_sys.output.get('pwm', 0))
        command[company, location]['dehum_pwm'] = fz.hum_dehum_sys.output['pwm']


async def main():
  global regulator_task
  while True:
    await asyncio.sleep(time_delay)
    asyncio.create_task(aggregate_sensors_data())
    regulator_task = asyncio.create_task(regulator())
    asyncio.create_task(handle_db_queries())
    act_event.set()
    sen_event.set()


class SensorData(BaseModel):
    company: str 
    location: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    co2: Optional[int] = None
    o2: Optional[int] = None
    voc: Optional[int] = None
    voltage_rms: Optional[float] = None
    current_rms: Optional[float] = None
    avg_power : Optional[float] = None
    renewable_EE : Optional[float] = None
    soil_moisure : Optional[float] = None

def calculate_power_factor(voltage_rms, current_rms, avg_power):
	if(voltage_rms and current_rms and (avg_power is not None)):
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

@app.get("/search_company/")
async def get_data(company_name : str):
    # InfluxQL query to fetch data
    query = f'SELECT * FROM "sensor_data" WHERE "company" = \'{company_name}\' ORDER BY time DESC'

    try:
        # Execute the query and get the result
        result = client.query(query)
        return list(result.get_points()) # Return the result as a list of data points
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying InfluxDB: {e}")

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
            power_factor = calculate_power_factor(
                data.get("voltage_rms"), data.get("current_rms"), data.get("avg_power")
            )

            batch = {
                "temperature": data.get("temperature"),
                "voc": data.get("voc"),
                "co2": data.get("co2"),
                "humidity": data.get("humidity"),
                "renewable_EE": data.get("renewable_EE"),
                "EE_consumption": 0,
                "power": data.get("avg_power"),
                "o2": data.get("o2"),
                "power_factor": power_factor,
                "soil_moisure": data.get("soil_moisure")
            }

            received_batches[(company, location)] = batch
            sen_event.clear()
    except WebSocketDisconnect:
        if websocket in sensors_active_connections:
            sensors_active_connections.remove(websocket)
            print("Client disconnected")
