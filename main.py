from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from influxdb import InfluxDBClient
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional


app = FastAPI()

origins = [
	"http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://192.168.1.12:5500"  # Optional: if accessing from another local IP
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows your frontend origin
    allow_credentials=True,
    allow_methods=["*"],    # Allow all HTTP methods
    allow_headers=["*"],    # Allow all headers
)

# InfluxDB connection details
INFLUXDB_HOST = "localhost"
INFLUXDB_PORT = 8086
INFLUXDB_DATABASE = "smart_zero_carbone"
INFLUXDB_USERNAME = "admin"  # Replace with your actual username
INFLUXDB_PASSWORD = "develop15."  # Replace with your actual password

# Initialize InfluxDB Client
client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USERNAME, password=INFLUXDB_PASSWORD)
client.switch_database(INFLUXDB_DATABASE)


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

def calculate_power_factor(voltage_rms, current_rms, avg_power):
	if(voltage_rms and current_rms and avg_power):
		power_factor = avg_power/(voltage_rms*current_rms)
		return power_factor
	return None

@app.post("/set_company_data/")
async def write_data(data: SensorData):
	print(data)
    
    # Write the data to InfluxDB
	try:
		query = f'SELECT * FROM "sensor_data" WHERE "company" = \'{data.company}\' AND "location" = \'{data.location}\' ORDER BY time DESC LIMIT 1'
		result = list(client.query(query).get_points())
		energy_consumption = 0
		if result:
			energy_consumption = result[0].get('EE_consumption', 0)  # Default to 0 if 'EE_consumption' doesn't exist
		energy_consumption += data.avg_power/3600000 #kWh
		print(energy_consumption)
		json_body = [
			{
				"measurement": "sensor_data",
				"tags": {
					"company": data.company,
					"location": data.location
				},
				"fields": {
					"temperature": data.temperature,
					"humidity": data.humidity,
					"co2": data.co2,
					"o2" : data.o2,
					"voc": data.voc,
					"renewable_EE" : data.renewable_EE,
					"EE_consumption" : energy_consumption,
					"power" : data.avg_power/1000,
					"power_factor" : calculate_power_factor(data.voltage_rms, data.current_rms, data.avg_power)
				}
			}
		]
		print(json_body)
		client.write_points(json_body)
		return {"message": "Data successfully written to InfluxDB."}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error writing data to InfluxDB: {e}")

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
