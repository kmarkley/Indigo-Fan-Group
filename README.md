# Fan Group

Virtual device groups for speedcontrol (fan) devices.

## Devices

The plugin defines three Device types: Fan Group Full, Fan Group Simple, and Thermostat Assist.

### Speedcontrol Fan Group

#### Configuration

* **Status Logic**  
	* Average: the device's speed is the average of the selected fans.
	* Minimum: the device's speed is the lowest speed of the selected fans.
	* Maximum: the device's speed is the highest speed of the selected fans.
	* All Match: the device will only have a speed if ALL fans are the same.

* **Select Fans**  
Self explanatory.

#### Use

The device is a standard speedcontrol device.  You can set it's speed like any fan and all the controlled fans will be set to match.  It will reflect the status of controlled fans when they change according to the Status Logic set in the configuration.

### Relay Fan Group

#### Configuration

* **ON Level**  
The speed to set selected fans when the device turns ON.

* **Status Logic**  
	* Any ON: the device is on if any selected fan is on (regardless of speed).
	* Average: the device is on if the average of speeds is at least the ON Level.
	* Minimum: the device is on if the lowest speed is at least the ON Level.
	* Maximum: the device is on if the highest speed is at least the ON Level.
	* All Match: the device is only on if ALL speeds equal the ON Level.

* **Select Fans**  
Self explanatory.

#### Use

The device is a normal relay device.  When turned ON, all the controlled fans will be set to the ON Level defined in the configuration.  The device will show ON if the Status Logic conditions are met.

### Thermostat Assist Fan Group

#### Configuration

* **Thermostat**  
Choose a thermostat to control the fan group.

* **Temp Freq**  
The plugin can optionally query the thermostat periodically for temperature changes.  Only applies when the device is ON.

* **ON Level**  
The speed to set selected fans when the device turns ON.

* **ON Threshold**  
The minimum temperature differential required for the device to turn ON.

* **OFF Threshold**  
The maximum temperature differential before the device is turned OFF.

* **Override ON**  
If unchecked, the device will only turn on fans that are off at time of activation.

* **Override OFF**  
If unchecked, the device will only turn off fans that are at the ON Level.

* **Select Fans**  
Self explanatory.

#### Use

**Important: will only work with thermostats that report when heating and cooling equipment is active.**

Once configured, the device will operate automatically when the cooling or heating equipment is active.  If the difference between the ambient and setpoint temperatures becomes greater than the ON Threshold (typically as a result of the setpoint changing), the controlled fans will be set to the ON Level.  The controlled fans will remain on until the temperature difference becomes less than the OFF Threshold.  Unchecking the Override ON and/or Override OFF options will prevent the device from changing fan levels that were set manually or by some other process.
