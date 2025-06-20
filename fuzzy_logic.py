import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import matplotlib.pyplot as plt

# 1. Define fuzzy input variables
temp = ctrl.Antecedent(np.arange(-20, 61, 1), 'temperature')
hum = ctrl.Antecedent(np.arange(0, 101, 1), 'humidity')
voc = ctrl.Antecedent(np.arange(0, 2001), 'voc')
co2 = ctrl.Antecedent(np.arange(0, 6000), 'co2')


# 2. Define fuzzy output variable
pwm = ctrl.Consequent(np.arange(0, 101, 1), 'pwm')

# 3. Define membership functions for inputs
temp['very_cold'] = fuzz.trimf(temp.universe, [-20, -20, -5])
temp['cold'] = fuzz.trimf(temp.universe, [-10, 0, 10])
temp['cool'] = fuzz.trimf(temp.universe, [5, 15, 25])
temp['mild'] = fuzz.trimf(temp.universe, [20, 25, 30])
temp['warm'] = fuzz.trimf(temp.universe, [28, 35, 42])
temp['hot'] = fuzz.trimf(temp.universe, [40, 50, 60])



hum['very_dry'] = fuzz.trapmf(hum.universe, [0, 0, 10, 20])
hum['dry'] = fuzz.trimf(hum.universe, [10, 25, 40])
hum['comfortable'] = fuzz.trimf(hum.universe, [30, 50, 70])
hum['humid'] = fuzz.trimf(hum.universe, [60, 75, 90])
hum['very_humid'] = fuzz.trapmf(hum.universe, [85, 95, 100, 100])

voc['excellent'] = fuzz.trapmf(voc.universe, [0, 0, 100, 200])
voc['good'] = fuzz.trimf(voc.universe, [150, 300, 450])
voc['moderate'] = fuzz.trimf(voc.universe, [400, 550, 700])
voc['poor'] = fuzz.trimf(voc.universe, [650, 800, 900])
voc['hazardous'] = fuzz.trapmf(voc.universe, [850, 950, 2000, 2000])

co2['excellent'] = fuzz.trapmf(co2.universe, [0, 0, 300, 500])
co2['good'] = fuzz.trimf(co2.universe, [400, 600, 800])
co2['moderate'] = fuzz.trimf(co2.universe, [700, 1000, 1300])
co2['poor'] = fuzz.trimf(co2.universe, [1200, 1450, 1700])
co2['hazardous'] = fuzz.trapmf(co2.universe, [1600, 1800, 2000, 2000])

# 4. Define membership functions for output
pwm['off'] = fuzz.trimf(pwm.universe, [0, 0, 5])
pwm['very_low'] = fuzz.trimf(pwm.universe, [3, 10, 20])
pwm['low'] = fuzz.trimf(pwm.universe, [15, 25, 35])
pwm['medium'] = fuzz.trimf(pwm.universe, [30, 50, 70])
pwm['high'] = fuzz.trimf(pwm.universe, [60, 75, 90])
pwm['very_high'] = fuzz.trimf(pwm.universe, [85, 100, 100])




# 5. Define fuzzy rules
voc_ventilation_rules = [
    ctrl.Rule(voc['hazardous'], pwm['very_high']),
    ctrl.Rule(voc['poor'], pwm['high']),
    ctrl.Rule(voc['moderate'], pwm['medium']),
    ctrl.Rule(voc['good'], pwm['low']),
    ctrl.Rule(voc['excellent'], pwm['off'])
]

co2_ventilation_rules = [
    ctrl.Rule(co2['hazardous'], pwm['very_high']),
    ctrl.Rule(co2['poor'], pwm['high']),
    ctrl.Rule(co2['moderate'], pwm['medium']),
    ctrl.Rule(co2['good'], pwm['low']),
    ctrl.Rule(co2['excellent'], pwm['off'])
]
#hello this is a change 
temp_heater_rules = [
    ctrl.Rule(temp['very_cold'], pwm['very_high']),
    ctrl.Rule(temp['cold'], pwm['high']),
    ctrl.Rule(temp['cool'], pwm['medium']),
    ctrl.Rule(temp['mild'], pwm['very_low']),
    ctrl.Rule(temp['warm'], pwm['off']),
    ctrl.Rule(temp['hot'], pwm['off'])
]

temp_air_cond_rules = [
    ctrl.Rule(temp['very_cold'], pwm['off']),
    ctrl.Rule(temp['cold'], pwm['off']),
    ctrl.Rule(temp['cool'], pwm['very_low']),
    ctrl.Rule(temp['mild'], pwm['low']),
    ctrl.Rule(temp['warm'], pwm['high']),
    ctrl.Rule(temp['hot'], pwm['very_high'])
]

hum_dehum_rules = [
    ctrl.Rule(hum['very_dry'], pwm['off']),
    ctrl.Rule(hum['dry'], pwm['off']),
    ctrl.Rule(hum['comfortable'], pwm['low']),
    ctrl.Rule(hum['humid'], pwm['high']),
    ctrl.Rule(hum['very_humid'], pwm['very_high'])
]




# 6. Control system
heater_ctrl = ctrl.ControlSystem(temp_heater_rules)
air_cond_ctrl = ctrl.ControlSystem(temp_air_cond_rules)
voc_ventilation_ctrl = ctrl.ControlSystem(voc_ventilation_rules)
co2_ventilation_ctrl = ctrl.ControlSystem(co2_ventilation_rules)
hum_dehum_ctrl = ctrl.ControlSystem(hum_dehum_rules)


heater_sys = ctrl.ControlSystemSimulation(heater_ctrl)
air_cond_sys = ctrl.ControlSystemSimulation(air_cond_ctrl)
voc_ventilation_sys = ctrl.ControlSystemSimulation(voc_ventilation_ctrl)
co2_ventilation_sys = ctrl.ControlSystemSimulation(co2_ventilation_ctrl)
hum_dehum_sys = ctrl.ControlSystemSimulation(hum_dehum_ctrl)
systems = {
  "heater_sys" : heater_sys,
  "air_cond_sys" : air_cond_sys,
  "voc_ventilation_sys" : voc_ventilation_sys,
  "co2_ventilation_sys" : co2_ventilation_sys,
  "hum_dehum_sys" : hum_dehum_sys
}
env = {
  "heater_sys" : "temperature",
  "air_cond_sys" : "temperature",
  "voc_ventilation_sys" : "voc",
  "co2_ventilation_sys" : "co2",
  "hum_dehum_sys" : "humidity"
}
print(heater_sys.__dict__)