import machine
import time
import network
import socket
from machine import Pin, I2C, ADC, PWM
import onewire
import ds18x20
import ntptime  # For WiFi time sync

# Import custom libraries (you need to upload these to your Pico)
try:
    from ssd1306 import SSD1306_I2C
    from ds3231 import DS3231
except ImportError:
    print("Please install ssd1306.py and ds3231.py libraries")

# WiFi Configuration
SSID = "OPPO A58"  # Replace with your WiFi name
PASSWORD = "e96vpnt7"  # Replace with your WiFi password

# Water level thresholds (adjust these for your tank)
WATER_HIGH_THRESHOLD = 5   # If distance < 5cm, water level is HIGH
WATER_LOW_THRESHOLD = 20   # If distance > 20cm, water level is LOW

# Hardware Setup
# I2C for OLED and RTC
i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)

# OLED Display
try:
    oled = SSD1306_I2C(128, 64, i2c)
except:
    print("OLED not found!")
    oled = None

# RTC DS3231
try:
    rtc = DS3231(i2c)
except:
    print("RTC not found!")
    rtc = None

# Servo Motor
servo = PWM(Pin(15))
servo.freq(50)

# Turbidity Sensor (3-pin version)
turbidity_adc = ADC(Pin(26))

# DS18B20 Temperature Sensor
ds_pin = Pin(22)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))

# HC-SR04 Ultrasonic Sensor for Water Level
trig = Pin(18, Pin.OUT)
echo = Pin(19, Pin.IN)

# Push Button
button = Pin(14, Pin.IN, Pin.PULL_UP)

# Global Variables
feeding_mode = False
last_button_state = 1
button_pressed = False
servo_step = 0  # Track current servo position

def connect_wifi():
    """Connect to WiFi network and sync time"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
   
    if not wlan.isconnected():
        print('Connecting to WiFi...')
        wlan.connect(SSID, PASSWORD)
       
        # Wait for connection
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print('Connecting...')
   
    if wlan.isconnected():
        print('WiFi connected!')
        print('Network config:', wlan.ifconfig())
       
        # Sync time with internet
        try:
            print("Syncing time with internet...")
            ntptime.settime()  # Get time from NTP server
            print("Time synced successfully!")
           
            # Update RTC with internet time if RTC is available
            if rtc:
                current_time = time.localtime()
                # Convert to your timezone (adjust +6 for Bangladesh time)
                adjusted_time = time.localtime(time.time() + 6*3600)  # +6 hours for Bangladesh
                rtc.set_time(
                    adjusted_time[0],  # year
                    adjusted_time[1],  # month  
                    adjusted_time[2],  # day
                    adjusted_time[6] + 1,  # weekday (1=Monday)
                    adjusted_time[3],  # hour
                    adjusted_time[4],  # minute
                    adjusted_time[5]   # second
                )
                print("RTC updated with internet time")
        except Exception as e:
            print("Time sync failed:", e)
       
        return True
    else:
        print('WiFi connection failed!')
        return False

def create_web_server():
    """Create HTTP server for MIT App Inventor communication"""
    try:
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(1)
        s.settimeout(0.01)  # Non-blocking timeout
        print('Web server listening on', addr)
        return s
    except Exception as e:
        print("Failed to create web server:", e)
        return None

def handle_web_request(conn):
    """Handle incoming web requests from MIT App Inventor"""
    global feeding_mode
   
    try:
        conn.settimeout(2.0)  # 2 second timeout for individual requests
        request = conn.recv(1024).decode()
        print("Request received:", request.split('\n')[0])
       
        # Parse the request path
        if 'GET /status' in request:
            # Get all sensor readings
            temp = read_temperature()
            distance = measure_water_distance()
            water_status = get_water_status(distance)
            turbidity, voltage = read_turbidity()
            time_str = get_time_string()
           
            # Determine water clarity
            if voltage is not None:
                if voltage < 1.5:
                    water_clarity = "Very Dirty"
                elif voltage < 2.5:
                    water_clarity = "Dirty"
                else:
                    water_clarity = "Clear"
            else:
                water_clarity = "Error"
           
            # Format data for MIT App Inventor
            # Create simple JSON that can be easily parsed
            temp_str = str(temp) if temp is not None else "0.0"
            distance_str = str(distance) if distance is not None else "0.0"
           
            # Create JSON in the format expected by your MIT App blocks
            response_json = '{{"temperature":"{}","water_status":"{}","time":"{}","water_clarity":"{}","distance":"{}"}}'.format(
                temp_str, water_status, time_str, water_clarity, distance_str
            )
           
            print("Sending data:", response_json)  # Debug output
           
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
            response += response_json
           
        elif 'GET /feed' in request:
            # Start feeding
            feeding_mode = True
            print("Feeding activated via web request")
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
            response += '{"status":"feeding","message":"Feed started"}'
           
        elif 'GET /stop' in request:
            # Stop feeding
            feeding_mode = False
            servo.duty_u16(4920)  # Return to neutral position
            print("Feeding stopped via web request")
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
            response += '{"status":"stopped","message":"Feed stopped"}'
           
        else:
            # Default response with current status
            temp = read_temperature()
            distance = measure_water_distance()
            water_status = get_water_status(distance)
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
            response += """
            <html><head><title>Fish Feeder API</title></head><body>
            <h1>🐠 Automated Fish Feeder API</h1>
            <h2>Current Status:</h2>
            <ul>
                <li>Temperature: {}°C</li>
                <li>Water Level: {}cm ({})</li>
                <li>Time: {}</li>
                <li>Feeding: {}</li>
            </ul>
            <h2>Available Endpoints:</h2>
            <ul>
                <li><a href="/status">/status</a> - Get current system status (JSON)</li>
                <li><a href="/feed">/feed</a> - Start feeding fish</li>
                <li><a href="/stop">/stop</a> - Stop feeding</li>
            </ul>
            </body></html>
            """.format(
                temp if temp is not None else "Error",
                distance if distance is not None else "Error",
                water_status,
                get_time_string(),
                "Active" if feeding_mode else "Stopped"
            )
       
        conn.send(response.encode())
       
    except Exception as e:
        print("Web request error:", e)
        try:
            error_response = "HTTP/1.1 500 Internal Server Error\r\nContent-Type: application/json\r\n\r\n"
            error_response += '{{"error":"Internal server error","message":"{}"}}'.format(str(e))
            conn.send(error_response.encode())
        except:
            pass
   
    finally:
        try:
            conn.close()
        except:
            pass
def servo_feed_continuous():
    """Control servo to rotate through positions continuously"""
    global servo_step
   
    # Servo positions that work perfectly (from your test)
    positions = [
        (1640, "0 degrees"),
        (3280, "45 degrees"),
        (4920, "90 degrees"),
        (6560, "135 degrees"),
        (8200, "180 degrees")
    ]
   
    # Move to current position
    duty, angle = positions[servo_step]
    servo.duty_u16(duty)
    print(f"Servo moving to {angle}")
   
    # Move to next position for next cycle
    servo_step = (servo_step + 1) % len(positions)
   
    # Small delay between movements
    time.sleep(0.3)

def read_temperature():
    """Read temperature from DS18B20"""
    try:
        roms = ds_sensor.scan()
        if roms:
            ds_sensor.convert_temp()
            time.sleep_ms(750)  # Wait for conversion
            temp = ds_sensor.read_temp(roms[0])
            return round(temp, 1)
        else:
            return None
    except:
        return None

def read_turbidity():
    """Read turbidity sensor analog value"""
    try:
        # Read analog value (0-65535)
        analog_val = turbidity_adc.read_u16()
        # Convert to voltage (0-3.3V)
        voltage = analog_val * 3.3 / 65535
       
        # Convert voltage to turbidity percentage
        # Higher voltage typically means clearer water (less turbidity)
        # Adjust this formula based on your sensor specifications
        turbidity_percent = (voltage / 3.3) * 100
       
        return round(turbidity_percent, 1), voltage
    except:
        return None, None

def measure_water_distance():
    """Measure distance using HC-SR04 ultrasonic sensor"""
    try:
        # Ensure trigger is low
        trig.value(0)
        time.sleep_us(2)
       
        # Send 10us trigger pulse
        trig.value(1)
        time.sleep_us(10)
        trig.value(0)
       
        # Wait for echo to go high (start of pulse)
        timeout_start = time.ticks_us()
        while echo.value() == 0:
            if time.ticks_diff(time.ticks_us(), timeout_start) > 30000:
                return None  # Timeout after 30ms
       
        # Measure pulse duration
        pulse_start = time.ticks_us()
        while echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), pulse_start) > 30000:
                return None  # Timeout after 30ms
        pulse_end = time.ticks_us()
       
        # Calculate distance
        pulse_duration = time.ticks_diff(pulse_end, pulse_start)
        # Speed of sound = 343 m/s = 0.0343 cm/us
        # Distance = (pulse_duration * 0.0343) / 2 (divide by 2 for round trip)
        distance = (pulse_duration * 0.0343) / 2
       
        return round(distance, 1)
    except:
        return None

def get_water_status(distance):
    """Get water level status - simplified for MIT App Inventor"""
    if distance is None:
        return "ERROR"
    elif distance < WATER_HIGH_THRESHOLD:
        return "HIGH"
    elif distance > WATER_LOW_THRESHOLD:
        return "LOW"  
    else:
        return "OK"

def get_time_string():
    """Get formatted time from RTC or system time"""
    try:
        if rtc:
            dt = rtc.get_time()
            return "{:02d}:{:02d}:{:02d}".format(dt[4], dt[5], dt[6])
        else:
            # Fallback to system time (already synced with internet)
            t = time.localtime()
            return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
    except:
        # Use system time if RTC fails
        t = time.localtime()
        return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])

def get_date_string():
    """Get formatted date from RTC or system time"""
    try:
        if rtc:
            dt = rtc.get_time()
            return "{:02d}/{:02d}/{:04d}".format(dt[2], dt[1], dt[0])
        else:
            # Fallback to system time (already synced with internet)
            t = time.localtime()
            return "{:02d}/{:02d}/{:04d}".format(t[2], t[1], t[0])
    except:
        # Use system time if RTC fails
        t = time.localtime()
        return "{:02d}/{:02d}/{:04d}".format(t[2], t[1], t[0])

def display_normal_info():
    """Display normal sensor information including water level"""
    if oled:
        oled.fill(0)
       
        # Display time and date
        time_str = get_time_string()
        date_str = get_date_string()
        oled.text("Time: " + time_str, 0, 0)
        oled.text("Date: " + date_str, 0, 8)
       
        # Display temperature
        temp = read_temperature()
        if temp is not None:
            oled.text("Temp: {:.1f}C".format(temp), 0, 18)
        else:
            oled.text("Temp: Error", 0, 18)
       
        # Display water level status
        distance = measure_water_distance()
        water_status = get_water_status(distance)
       
        if distance is not None:
            oled.text("Water: {:.1f}cm".format(distance), 0, 28)
        else:
            oled.text("Water: Error", 0, 28)
       
        # Display water status with appropriate message
        if water_status == "HIGH":
            oled.text("Level: FULL", 0, 38)
        elif water_status == "LOW":
            oled.text("Level: ADD WATER!", 0, 38)
        elif water_status == "OK":
            oled.text("Level: NORMAL", 0, 38)
        else:
            oled.text("Level: ERROR", 0, 38)
       
        # Display turbidity on last line
        turbidity, voltage = read_turbidity()
        if turbidity is not None and voltage is not None:
            if voltage < 1.5:
                oled.text("Water: Very Dirty", 0, 48)
            elif voltage < 2.5:
                oled.text("Water: Dirty", 0, 48)
            else:
                oled.text("Water: Clear", 0, 48)
        else:
            oled.text("Clarity: Error", 0, 48)
       
        oled.text("Press for feeding", 0, 58)
        oled.show()

def display_feeding_info():
    """Display feeding information"""
    if oled:
        oled.fill(0)
        oled.text("FISH FEEDING", 20, 5)
        oled.text("ACTIVE!", 35, 18)
       
        # Show water level during feeding
        distance = measure_water_distance()
        water_status = get_water_status(distance)
       
        if distance is not None:
            oled.text("Water: {:.1f}cm".format(distance), 0, 30)
        else:
            oled.text("Water: Error", 0, 30)
           
        if water_status == "LOW":
            oled.text("WARNING: LOW WATER!", 0, 40)
        elif water_status == "HIGH":
            oled.text("Water Level: FULL", 0, 40)
        else:
            oled.text("Water Level: OK", 0, 40)
       
        oled.text("Servo Cycling...", 10, 50)
        oled.text("Press to STOP", 15, 58)
        oled.show()

def check_button():
    """Check button press with debouncing"""
    global last_button_state, button_pressed
   
    current_state = button.value()
   
    if last_button_state == 1 and current_state == 0:  # Button pressed
        button_pressed = True
        time.sleep(0.2)  # Debounce delay
   
    last_button_state = current_state
    return button_pressed

def setup_rtc():
    """Initialize RTC - will be auto-updated by WiFi time sync"""
    if rtc:
        try:
            # RTC will be automatically set by WiFi time sync
            print("RTC ready - will sync with internet time")
        except Exception as e:
            print("RTC setup failed:", e)
    else:
        print("RTC not found - using system time (synced with internet)")

def check_water_level_alerts():
    """Check water level and print alerts to console"""
    distance = measure_water_distance()
    water_status = get_water_status(distance)
   
    if water_status == "LOW":
        print(f"🟡 ALERT: Water level LOW! Distance: {distance}cm - Please add water to tank")
    elif water_status == "HIGH":
        print(f"🔴 ALERT: Water level HIGH! Distance: {distance}cm - Tank might overflow")
    elif water_status == "ERROR":
        print("❌ ALERT: Water level sensor error - Check HC-SR04 connections")

def main():
    """Main program loop"""
    global feeding_mode, button_pressed, servo_step
   
    print("🐠 Automated Fish Feeding System Starting...")
    print("📡 MIT App Inventor Compatible Version")
    print("=" * 50)
    print("Water Level Sensor Configuration:")
    print(f"  HIGH:   Distance < {WATER_HIGH_THRESHOLD}cm (sensor close to water)")
    print(f"  NORMAL: Distance {WATER_HIGH_THRESHOLD}-{WATER_LOW_THRESHOLD}cm (good water level)")
    print(f"  LOW:    Distance > {WATER_LOW_THRESHOLD}cm (need to add water)")
    print("=" * 50)
   
    # Initialize hardware
    setup_rtc()
   
    # Connect to WiFi
    wifi_connected = connect_wifi()
    if wifi_connected:
        print("✅ System ready for MIT App Inventor connection")
    else:
        print("❌ WiFi connection failed - check credentials")
        return
   
    try:
        web_server = create_web_server()
        if web_server:
            print("✅ Web server started successfully!")
            print("🌐 MIT App Inventor Test URLs:")
            wlan = network.WLAN(network.STA_IF)
            ip = wlan.ifconfig()[0]
            print(f"   📊 Status: http://{ip}/status")
            print(f"   🍽️  Feed:   http://{ip}/feed")
            print(f"   ⏹️  Stop:   http://{ip}/stop")
            print("=" * 50)
            print("📱 Update your MIT App Inventor PICO_IP to:", ip)
            print("=" * 50)
        else:
            print("❌ Web server failed to start")
            return
    except Exception as e:
        print("❌ Web server failed to start:", e)
        return
   
    # Initialize servo to neutral position (90 degrees)
    servo.duty_u16(4920)  # 90 degrees - working value
    servo_step = 2  # Start at 90 degrees position
   
    print("🚀 System initialized. Starting main loop...")
    print("🔧 Hardware connections verified:")
    print("   HC-SR04: Trig→GPIO18, Echo→GPIO19, VCC→VBUS(5V), GND→GND")
    print("   DS18B20: Data→GPIO22, VCC→3.3V, GND→GND")
    print("   Servo: Signal→GPIO15, VCC→VBUS(5V), GND→GND")
    print("=" * 50)
   
    alert_counter = 0  # Counter to reduce alert frequency
    status_counter = 0  # Counter for periodic status updates
   
    while True:
        try:
            # Handle web requests from MIT App Inventor
            if web_server:
                try:
                    conn, addr = web_server.accept()
                    print(f"📱 MIT App connection from {addr}")
                    handle_web_request(conn)
                except OSError:
                    pass  # No connection waiting, continue with normal operation
           
            # Check button press
            if check_button():
                button_pressed = False  # Reset flag
                feeding_mode = not feeding_mode  # Toggle mode
               
                if feeding_mode:
                    print("🍽️ FEEDING MODE ACTIVATED - Motor cycling through positions")
                    print("🔄 Servo sequence: 0° → 45° → 90° → 135° → 180° → repeat...")
                    display_feeding_info()
                    servo_step = 0  # Reset to start position
                else:
                    print("⏹️ NORMAL MODE - Motor stopped at neutral position")
                    # Stop motor in neutral position (90 degrees)
                    servo.duty_u16(4920)  # 90 degrees - working value
                    servo_step = 2  # Reset to 90 degree position
           
            # Display appropriate information and handle motor
            if feeding_mode:
                display_feeding_info()
                servo_feed_continuous()  # Keep motor running through positions
            else:
                display_normal_info()
           
            status_counter += 1
            if status_counter >= 100:  # Every 10 seconds (100 * 0.1s)
                temp = read_temperature()
                distance = measure_water_distance()
                water_status = get_water_status(distance)
                print(f"📊 Status Update - Temp: {temp}°C, Water: {distance}cm ({water_status}), Feeding: {feeding_mode}")
                status_counter = 0
           
            # Check water level alerts every 50 cycles (reduce console spam)
            alert_counter += 1
            if alert_counter >= 50:
                check_water_level_alerts()
                alert_counter = 0
           
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
           
        except KeyboardInterrupt:
            print("\n🛑 System stopped by user")
            print("🔧 Cleaning up...")
            if web_server:
                web_server.close()
            # Return servo to neutral position
            servo.duty_u16(4920)
            print("✅ Cleanup complete. Goodbye!")
            break
        except Exception as e:
            print("❌ System Error:", e)
            print("🔄 Continuing operation...")
            time.sleep(1)

# Run the main program
if __name__ == "__main__":
    main()