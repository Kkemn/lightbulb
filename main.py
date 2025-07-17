from yeelight import Bulb, BulbException
from datetime import datetime, timedelta, time
from collections.abc import Callable
from typing import cast, Literal
import requests
from tkinter import *
from tkinter import Misc, ttk
import json
import os

BULB_IP = "192.168.0.18"
URL = "https://api.sunrisesunset.io/json?"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
LOCATION = "Bydgoszcz"
LATITUDE = "53.123482" # Bydgoszcz latitude
LONGITUDE = "18.008438" # Bydgoszcz longitude

def add_subtract_minutes(time: str, minutes: str) -> str:
    ''' Return time string in "%H:%M" format after adding or subtracting minutes to given time in the same format '''
    time_obj: datetime = datetime.strptime(time, "%H:%M")
    new_time: datetime = time_obj + timedelta(minutes=int(minutes))
        
    return new_time.strftime("%H:%M")

def get_target_datetime(target_time: str) -> datetime:
    ''' Return datetime object based on target time string in "%H:%M" format considering that if target time is earlier than current time it is scheduled for the next day. '''
    now: datetime = datetime.now()
    target: time = datetime.strptime(target_time, "%H:%M").time()
    target_datetime: datetime = datetime.combine(now.date(), target)
    if target < now.time(): # if target is less than current time it's probably after midnight, should be scheduled for the next day
        target_datetime = target_datetime + timedelta(days=1.0)
    return target_datetime

class HttpRequests:
    def __init__(self) -> None:
        self.sunset_url = URL
        self.geo_url = GEOCODING_URL
    
    def get_sunset(self, latitude: str, longitude: str) -> str:
        ''' Return sunset time in HH:MM format. '''
        payload: dict[str, str] = {'lat': latitude, 'lng': longitude, 'time_format': '24'}
        response: requests.Response = requests.get(url=self.sunset_url, params=payload)
        return response.json()['results']['sunset'][:5]

    def set_location(self, location: str) -> tuple[str, str, str, str] | str:
        ''' Return latitude, longitude, sunset time for given location, otherwise return location not found message. '''
        payload: dict[str, str | int] = {"name": location, "count": 1}
        response: requests.Response = requests.get(url=self.geo_url, params=payload)

        latitude: str = str(response.json()['results'][0]['latitude'])
        longitude: str = str(response.json()['results'][0]['longitude'])
        api_location: str = response.json()['results'][0]['name']
        sunset: str = self.get_sunset(latitude, longitude)
        return (latitude, longitude, api_location, sunset)
    
class LoopController:
    def __init__(self, tk_root: Misc, interval_ms: int, task: Callable[[], None]) -> None:
        '''
        Parameters:
        - tk_root: Tkinter widget to use ".after()" method on
        - interval_ms: Interval in miliseconds between task executions
        - task: A no-arg callable to execute every interval
        '''
        self.root: Misc = tk_root
        self.interval: int = interval_ms
        self.task: Callable[[], None] = task
        self._loop_id: str | None = None

    def _loop(self) -> None:
        ''' Run task every given interval. '''
        self.task()
        self._loop_id = self.root.after(self.interval, self._loop)
    
    def start(self) -> None:
        ''' Start the loop (only if not running). '''
        if self._loop_id is None:
            self._loop()
    
    def stop(self) -> None:
        ''' Stop the loop (if it is running). '''
        if self._loop_id is not None:
            self.root.after_cancel(self._loop_id)
            self._loop_id = None
    
    def is_running(self) -> bool:
        ''' Check if the loop is running. '''
        return self._loop_id is not None
    
class ConfigManager:
    def __init__(self, path = "config.json") -> None:
        self.path: str = path

    def save(self, config_data) -> None:
        with open(self.path, "w") as file:
            json.dump(config_data, file)

        print("Configuration saved.")

    def load(self) -> dict[str, str | int]:
        if os.path.exists(self.path):
            with open(self.path, "r") as file:
                return json.load(file)
        else:
            print("Config file not found. Loading defaults.")
            return {}
        
class BulbController:
    def __init__(self, ip: str) -> None:
        ''' Init the bulb with passed IP address. '''
        self.ip: str = ip
        self.bulb: Bulb = Bulb(self.ip)
        self.check_bulb()
        self.power_state: str = self.get_power_state()

    def toggle(self) -> None:
        ''' Toggle the bulb and return it's power state. '''
        self.bulb.toggle()
        self.power_state = self.get_power_state()

    def turn_on(self) -> None:
        ''' Turn the bulb on (if it's off). '''
        if self.power_state == "off":
            self.bulb.turn_on()
            self.power_state = "on"

    def turn_off(self) -> None:
        ''' Turn the bulb off (if it's on). '''
        if self.power_state == "on":
            self.bulb.turn_off()
            self.power_state = "off"

    def get_power_state(self) -> str:
        ''' Return bulb's power state. '''
        return self.bulb.get_properties()["power"]
    
    def check_bulb(self) -> None:
        ''' Check if the bulb is reachable. '''
        try:
            self.bulb.get_properties()
        except BulbException as e:
            raise ConnectionError(f"Failed to connect the bulb at {self.ip}.") from e

class App(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Yeelight Bulb Controller")

        self._init_external() 
        # self.config_data: dict[str, str | int] = self.config.load()     
        self._init_location_variables()  
        self._init_images()      
        self._init_state_variables()              
        self._bind_keys()        
        self.create_widgets()
            
    def create_widgets(self) -> None:
        # Create mainframe
        self.mainframe = ttk.Frame(self, padding="5")
        self.mainframe.grid(column=0, row=0, sticky="n s e w")

        # Bulb state image label  
        self.state_label = ttk.Label(self.mainframe, textvariable=self.bulb_state)
        self.state_label.grid(column=0, row=0, rowspan=3)
        self.set_bulb_state()

        # Toggle button
        ttk.Button(self.mainframe, text="Toggle", command=self.toggle_bulb).grid(column=1, row=1)

        # Time text label
        ttk.Label(self.mainframe, text="Time:").grid(column=3, row=0, sticky="s")
        ttk.Label(self.mainframe, textvariable=self.time).grid(column=4, row=0, sticky="w s")

        # Location text label
        ttk.Label(self.mainframe, text="Location:").grid(column=3, row=1)
        ttk.Label(self.mainframe, textvariable=self.location).grid(column=4, row=1, sticky="w")

        # Sunset time text label
        ttk.Label(self.mainframe, text="Sunset at location:").grid(column=3, row=2, sticky="n")
        ttk.Label(self.mainframe, textvariable=self.sunset).grid(column=4, row=2, sticky="w n")

        # Horizontal separator
        ttk.Separator(self.mainframe, orient="horizontal").grid(row=3, columnspan=5, sticky="e w", pady=10)

        # Auto-on at sunset checkbutton
        self.auto_on_check: ttk.Checkbutton = ttk.Checkbutton(self.mainframe, text="Auto-on at sunset", command=self.sunset_turn_on, variable=self.auto_on_var)
        self.auto_on_check.grid(column=0, row=4)

        # Auto-on time offset spinbox
        ttk.Label(self.mainframe, text="Set time offset:").grid(column=0, row=5)
        self.spnbox = ttk.Spinbox(self.mainframe, from_=-60.0, to=60.0, increment=10.0, textvariable=self.offset, command=self.sunset_turn_on, wrap=True, width=3)
        self.spnbox.state(["readonly"])
        if not self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["disabled"])
        self.spnbox.grid(column=0, row=6)
        ttk.Label(self.mainframe, text="minutes").grid(column=1, row=6, sticky='w')

        # Vertical separator
        ttk.Separator(self.mainframe, orient="vertical").grid(row=0, column=2, rowspan=7, padx=10, sticky="n s")

        # Auto-off checkbutton
        self.auto_off_check = ttk.Checkbutton(self.mainframe, text="Auto-off", command=self.auto_off, variable=self.auto_off_var)
        self.auto_off_check.grid(column=3, row=4)
 
        # Auto-off time combobox
        ttk.Label(self.mainframe, text="Set auto-off time:").grid(column=3, row=5)
        self.cmbbox = ttk.Combobox(self.mainframe, textvariable=self.off_time, width=5)
        self.cmbbox["values"] = [
                            str(h)+":0"+str(m)
                            if m < 10
                            else
                            str(h)+":"+str(m)
                            for h in range(24)
                            for m in range(0, 60, 10)
                            ]
        self.cmbbox.state(["readonly"])
        if not self.auto_off_check.instate(["selected"]):
            self.cmbbox.state(["disabled"])
        self.cmbbox.bind('<<ComboboxSelected>>', self.update_turn_on_time)
        self.cmbbox.grid(column=3, row=6, pady=10)

        # Horizontal separator
        ttk.Separator(self.mainframe, orient="horizontal").grid(row=7, columnspan=5, sticky="e w")

        # Location entry
        self.user_input_loc = StringVar()
        ttk.Label(self.mainframe, text="Set new location:").grid(column=0, row=8)
        self.loc_entry = ttk.Entry(self.mainframe, textvariable=self.user_input_loc, validate="key", validatecommand=self.vcmd)
        self.loc_entry.grid(column=0, row=9)
        ttk.Label(self.mainframe, font="TkSmallCaptionFont", foreground="red", textvariable=self.errmsg).grid(column=3, row=9, columnspan=2, sticky="w")
        self.loc_btn = ttk.Button(self.mainframe, text="Set", command=self.set_location)
        self.loc_btn.state(["disabled"])
        self.loc_btn.grid(column=1, row=9)

        # Horizontal separator
        ttk.Separator(self.mainframe, orient="horizontal").grid(row=11, columnspan=5, sticky="e w", pady=10)

        # Exit auto-off checkbutton
        self.ext_auto_off_check = ttk.Checkbutton(self.mainframe, text="Auto-off at exit", variable=self.exit_var)
        self.ext_auto_off_check.grid(column=0, row=12)

        # Horizontal separator
        ttk.Separator(self.mainframe, orient="horizontal").grid(row=13, columnspan=5, sticky="e w", pady=10)

        # Save configuration button
        ttk.Button(self.mainframe, text="Save config", command=self.save_config).grid(column=0, row=14)

        # Exit button
        ttk.Button(self.mainframe, text="Exit", command=self.exit).grid(column=4, row=14)
    
    def _init_location_variables(self) -> None:
        self.latitude: str = str(self.config_data.get("latitude", LATITUDE)) # add this to location_config dataclass
        self.longitude: str = str(self.config_data.get("longitude", LONGITUDE)) # add this to location_config dataclass
        self.location = StringVar(value=str(self.config_data.get("location", LOCATION))) # add this to location_config dataclass
        self.sunset = StringVar(value=self.http.get_sunset(self.latitude, self.longitude))

    def _init_state_variables(self) -> None:
        # Bulb state
        self.bulb_state = StringVar()

        # Time
        self.time = StringVar()
        self.time_update()
        
        # Sunset auto-on
        self.auto_on_var = IntVar(value=int(self.config_data.get("auto_on_var", 0))) # app_config dataclass maybe?
        self.offset = StringVar(value=str(self.config_data.get("offset", "0"))) # app_config dataclass maybe?

        # Auto-off
        self.auto_off_var = IntVar(value=int(self.config_data.get("auto_off_var", 0))) # app_config dataclass maybe?
        self.off_time = StringVar(value=str(self.config_data.get("off_time", "00:00"))) # app_config dataclass maybe?

        # Exit behavior
        self.exit_var = IntVar(value=int(self.config_data.get("exit_var", 0))) # app_config dataclass maybe?

        # Validation and errors
        self.vcmd: tuple[str, Literal['%P']] = (self.register(self.validate), "%P")
        self.errmsg = StringVar()
    
    def _init_external(self) -> None:
        # Configuration manager
        self.config = ConfigManager()
        self.config_data: dict[str, str | int] = self.config.load()
        
        # Bulb controller
        self.bulb = BulbController(str(self.config_data.get("bulb_ip", BULB_IP)))

        # Http requests handler
        self.http = HttpRequests()

        # Loops controller
        self.turn_on_loop: LoopController | None = None
        self.turn_off_loop: LoopController | None = None
    
    def _bind_keys(self) -> None:
        self.bind(sequence="<Escape>", func=self.exit)

    def _init_images(self) -> None:
        self.img_bulb_on = PhotoImage(file="bulb_on.gif")
        self.img_bulb_off = PhotoImage(file="bulb_off.gif")
    
    def toggle_bulb(self) -> None:
        self.bulb.toggle()
        self.set_bulb_state()
    
    def sunset_turn_on(self) -> None:
        ''' Start the turn on loop and calculate turn on time when auto-on at sunset is checked, stop the loop if auto-on at sunset gets unchecked. '''
        if not self.turn_on_loop:
            self.turn_on_loop = LoopController(self, 1000, self.turn_on_task)

        if self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["!disabled"])
            print("Sunset turn on enabled.")
            self.turn_on_time: str = add_subtract_minutes(self.sunset.get(), self.offset.get())
            self.turn_on_loop.start()
        else:
            self.spnbox.state(["disabled"])
            self.turn_on_loop.stop()
            print("Sunset turn on disabled.")
    
    def turn_on_task(self) -> None:
        ''' Turn on the bulb if current time matches scheduled time. '''
        if datetime.strptime(self.turn_on_time, "%H:%M").time() <= datetime.now().time():
            if self.bulb_state.get() == "off":
                self.bulb.turn_on()
                self.set_bulb_state()
                if self.turn_on_loop:
                    self.turn_on_loop.stop()
                    self.turn_on_loop = None
                print("Bulb turned on.")

    def time_update(self) -> None:
        self.time.set(datetime.now().strftime("%H:%M"))
        self.after(1000, self.time_update)
    
    def auto_off(self) -> None:
        if not self.turn_off_loop:
            self.turn_off_loop = LoopController(self, 1000, self.turn_off_task)

        self.turn_off_time: datetime = get_target_datetime(self.off_time.get())

        if self.auto_off_check.instate(["selected"]):
            self.cmbbox.state(["!disabled"])
            self.turn_off_loop.start()
            print("Auto turn-off enabled.")
        else:
            self.cmbbox.state(["disabled"])
            self.turn_off_loop.stop()
            print("Auto turn-off disabled.")
    
    def turn_off_task(self) -> None:
        if self.turn_off_time <= datetime.now():
            if self.bulb_state.get() == "on":
                self.bulb.turn_off()
                self.set_bulb_state()
                if self.turn_off_loop:
                    self.turn_off_loop.stop()
                    self.turn_off_loop = None
                print("Bulb turned off.")
    
    def exit(self, *args) -> None:
        if self.ext_auto_off_check.instate(["selected"]):
            self.bulb.turn_off()
        self.destroy()

    def set_bulb_state(self) -> None:
        self.bulb_state.set(self.bulb.power_state)
        if self.bulb_state.get() == "on":
            self.state_label["image"] = self.img_bulb_on
        else:
            self.state_label["image"] = self.img_bulb_off

    def set_location(self) -> None:
        try:
            location: str
            sunset: str
            self.latitude, self.longitude, location, sunset = self.http.set_location(self.user_input_loc.get())
            self.location.set(location)
            self.sunset.set(sunset)
        except KeyError:
            self.errmsg.set("Location not found.")
        
    def validate(self, new_entry: str) -> bool:
        self.errmsg.set("")
        valid: bool = new_entry.isalpha() or new_entry == ""
        self.loc_btn.state(["!disabled"]) if valid else self.loc_btn.state(["disabled"])
        if valid:
            return valid
        else:
            self.errmsg.set("Only letters allowed.")
            return valid
        
    def update_turn_on_time(self, event: Event) -> None:
        ''' Set new auto-off time after combobox value change. '''
        combobox: ttk.Combobox = cast(ttk.Combobox, event.widget)
        self.turn_off_time: datetime = get_target_datetime(combobox.get())
    
    def save_config(self) -> None:
        config_data: dict[str, str | int] = {
            "location": self.location.get(),
            "longitude": self.longitude, # do something with these, they're taken from constants
            "latitude": self.latitude, # do something with these, they're taken from constants
            "bulb_ip": BULB_IP, # add bulb_ip variable
            "auto_on_var": self.auto_on_var.get(),
            "offset": self.offset.get(),
            "auto_off_var": self.auto_off_var.get(),
            "off_time": self.off_time.get(),
            "exit_var": self.exit_var.get()
        }

        self.config.save(config_data)

        
if __name__ == '__main__':
    app = App()
    app.mainloop()