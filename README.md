In this project we used: 
Hardware:
Raspberry Pi Pico W (1x)
SG90 Servo Motor (1x)
0.96" OLED Display (I2C - SSD1306) (1x)
Breadboard (1x)
Jumper wires (Male-to-Male, at least 15 wires)
USB cable (Micro USB to USB-A)


Software:
Thonny IDE (on computer)
MicroPython firmware for Pico W
MIT App Inventor (web browser)
MIT AI2 Companion app (on phone)

Raspberry Pi Pico W - Fish Feeder System Pinout
I2C Components (Shared Bus)

SCL (Clock): GPIO 5
SDA (Data): GPIO 4
Frequency: 400kHz

Connected I2C Devices:

SSD1306 OLED Display (128x64)

VCC → 3.3V
GND → GND
SCL → GPIO 5
SDA → GPIO 4


DS3231 Real-Time Clock (RTC)

VCC → 3.3V
GND → GND
SCL → GPIO 5
SDA → GPIO 4



Servo Motor

Signal/Control: GPIO 15
VCC: VBUS (5V)
GND: GND
PWM Frequency: 50Hz

Turbidity Sensor (3-pin Analog)

Analog Output: GPIO 26 (ADC0)
VCC: 3.3V
GND: GND

DS18B20 Temperature Sensor (1-Wire)

Data: GPIO 22
VCC: 3.3V
GND: GND
Note: Requires 4.7kΩ pull-up resistor between Data and VCC

HC-SR04 Ultrasonic Distance Sensor

Trigger: GPIO 18 (Output)
Echo: GPIO 19 (Input)
VCC: VBUS (5V)
GND: GND

Push Button

Input: GPIO 14
Configuration: Pull-up enabled (internal)
Connection: Button between GPIO 14 and GND

Power Connections Summary
3.3V Rail:

OLED Display VCC
DS3231 RTC VCC
Turbidity Sensor VCC
DS18B20 Temperature Sensor VCC

5V Rail (VBUS):

Servo Motor VCC
HC-SR04 Ultrasonic Sensor VCC

Ground (GND):

All component GND pins
Push button (other terminal)

MIT APP Inventor codes:
<img width="752" height="836" alt="image" src="https://github.com/user-attachments/assets/aefdd4fb-059b-40f9-a7ea-b4a9c5610858" />
<img width="937" height="802" alt="image" src="https://github.com/user-attachments/assets/6b562adf-dce1-45e5-99d8-03fe3f7cc462" />
<img width="1036" height="807" alt="image" src="https://github.com/user-attachments/assets/15c6ab35-49e8-4519-b31e-f6751c1f8b3a" />


