from yeelight import Bulb, BulbException
from datetime import datetime, timedelta, time
from collections.abc import Callable
from typing import cast, Literal
from dataclasses import dataclass, asdict
import requests
import tkinter as tk
from tkinter import Misc, ttk, messagebox
import json
import os 
import re

BULB_IP = "192.168.0.18"
URL = "https://api.sunrisesunset.io/json?"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

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

@dataclass
class LocationConfig:
    ''' Class for keeping location dependent attributes. Defaults are set here. '''
    location: str = "Bydgoszcz"
    longitude: str = "18.008438"
    latitude: str = "53.123482"

@dataclass
class AppSettings:
    ''' Class for keeping tkinter App settings. Defaults are set here. '''
    auto_on_var: int = 0
    offset: str = "0"
    auto_off_var: int = 0
    off_time: str = "00:00"
    exit_var: int = 0

@dataclass
class NetworkSettings:
    ''' Class for keeping bulb IP address. '''
    # Wrapped in dataclass for possibility of having multiple bulbs in the future.
    ip: str | None = None

class HttpRequests:
    def __init__(self) -> None:
        self.sunset_url = URL
        self.geo_url = GEOCODING_URL
    
    def get_sunset(self, latitude: str, longitude: str) -> str:
        ''' Return sunset time in HH:MM format. '''
        payload: dict[str, str] = {'lat': latitude, 'lng': longitude, 'time_format': '24'}
        response: requests.Response = requests.get(url=self.sunset_url, params=payload)
        return response.json()['results']['sunset'][:5]

    def set_location(self, location: str) -> tuple[str, ...] | str:
        ''' Return latitude, longitude, sunset time for given location, otherwise raise KeyError exception. '''
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

    def _start_loop(self) -> None:
        ''' Start the loop by scheduling running the task after interval. '''
        self._loop_id = self.root.after(self.interval, self._run_task)

    def _run_task(self) -> None:
        ''' Run task every given interval. '''
        self.task()
        if self._loop_id:
            self._loop_id = self.root.after(self.interval, self._run_task)
    
    def start(self) -> None:
        ''' Start the loop (only if not running). '''
        if self._loop_id is None:
            self._start_loop()
    
    def stop(self) -> None:
        ''' Stop the loop (if it is running). '''
        if self._loop_id is not None:
            self.root.after_cancel(self._loop_id)
            self._loop_id = None
    
    def is_running(self) -> bool:
        ''' Check if the loop is running. '''
        return self._loop_id is not None
    
class ConfigManager:
    ''' Keep configuration attributes. Handle saving and loading configuration from file. '''
    def __init__(self, path = "config.json") -> None:
        self._path: str = path
        self.loc_config = LocationConfig()
        self.app_settings = AppSettings()
        self.network_settings = NetworkSettings()

    def save(self) -> None:
        ''' Save configuration attributes to a json file. '''
        data: dict[str, dict[str, str | int | None]] = {"location_config": asdict(self.loc_config), "app_settings": asdict(self.app_settings), "network_settings": asdict(self.network_settings)}
        with open(self._path, "w") as file:
            json.dump(data, file, indent=4)

    def load(self) -> None:
        ''' Load configuration attributes from a json file if it exists, otherwise set to defaults. '''
        if os.path.exists(self._path):
            with open(self._path, "r") as file:
                data: dict[str, dict[str, str | int | None]] = json.load(file)
            self.loc_config = LocationConfig(**data["location_config"]) # type: ignore # there is no way of int being assigned to str
            self.app_settings = AppSettings(**data["app_settings"]) # type: ignore # there is no way of int being assigned to str
            self.network_settings = NetworkSettings(**data["network_settings"]) # type: ignore # there is no way of int being assigned to str or None
        else:
            print("Config file not found. Configuration set to default.")
        
class BulbController:
    def __init__(self, ip: str | None, state_change_callback_recver: Callable[[str], None] | None = None) -> None:
        ''' Init the bulb with passed IP address. '''
        self.ip: str | None = ip
        self.state_change_callback_recver: Callable[[str], None] | None = state_change_callback_recver
        if self.ip:
            self.bulb: Bulb = Bulb(self.ip)
            self._check_bulb()
            self.power_state: str = self.get_power_state()
            self._notify()

    def _notify(self) -> None:
        ''' Notify the callback listener with bulb's power state. '''
        if self.state_change_callback_recver:
            self.state_change_callback_recver(self.power_state)

    def toggle(self) -> None:
        ''' Toggle the bulb and return it's power state. '''
        if self.ip:
            self.bulb.toggle()
            self.power_state = self.get_power_state()
            self._notify()
        else:
            print("Bulb not connected.")

    def turn_on(self) -> None:
        ''' Turn the bulb on (if it's off). '''
        if self.ip:
            if self.power_state == "off":
                self.bulb.turn_on()
                self.power_state = "on"
                self._notify()
        else:
            print("Bulb not connected.")

    def turn_off(self) -> None:
        ''' Turn the bulb off (if it's on). '''
        if self.ip:
            if self.power_state == "on":
                self.bulb.turn_off()
                self.power_state = "off"
                self._notify()
        else:
            print("Bulb not connected.")

    def get_power_state(self) -> str:
        ''' Return bulb's power state. If no bulb connected, always return "off" state. '''
        if self.ip:
            return self.bulb.get_properties()["power"]
        else:
            print("Bulb not connected.")
            return "off"
    
    def _check_bulb(self) -> None:
        ''' Check if the bulb is reachable. '''
        try:
            self.bulb.get_properties()
        except BulbException as e:
            raise ConnectionError(f"Failed to connect the bulb at {self.ip}.") from e

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Yeelight Bulb Controller")

        self._init_external()   
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
        self.set_bulb_state(self.bulb.get_power_state())

        # Toggle button
        ttk.Button(self.mainframe, text="Toggle", command=self.toggle_bulb).grid(column=1, row=1)

        # Time text label
        ttk.Label(self.mainframe, text="Time:").grid(column=3, row=0, sticky="s")
        ttk.Label(self.mainframe, textvariable=self.time).grid(column=4, row=0, sticky="s")

        # Location text label
        ttk.Label(self.mainframe, text="Location:").grid(column=3, row=1)
        ttk.Label(self.mainframe, textvariable=self.location).grid(column=4, row=1)

        # Sunset time text label
        ttk.Label(self.mainframe, text="Sunset at location:").grid(column=3, row=2, sticky="n")
        ttk.Label(self.mainframe, textvariable=self.sunset).grid(column=4, row=2, sticky="n")

        # Horizontal separator
        ttk.Separator(self.mainframe, orient="horizontal").grid(row=3, columnspan=5, sticky="e w", pady=10)

        # Vertical separator
        ttk.Separator(self.mainframe, orient="vertical").grid(row=0, column=2, rowspan=3, padx=10, sticky="n s")

        # Exit button
        ttk.Button(self.mainframe, text="Exit", command=self.exit).grid(column=0, row=4, sticky="w")

        # Settings button
        ttk.Button(self.mainframe, text="Settings", command=self.open_settings_window).grid(column=4, row=4)

        # Dialog window
        if self.config.network_settings.ip is None:
            messagebox.showerror(title="IP missing", message="Missing IP address. Please enter a valid IP in settings.")
    
    def _init_location_variables(self) -> None:
        self.latitude: str = self.config.loc_config.latitude
        self.longitude: str = self.config.loc_config.longitude
        self.location = tk.StringVar(value=self.config.loc_config.location)
        self.sunset = tk.StringVar(value=self.http.get_sunset(self.latitude, self.longitude))

    def _init_state_variables(self) -> None:
        # Bulb state
        self.bulb_state = tk.StringVar()
        self.ip_label = tk.StringVar(value=self.config.network_settings.ip)

        # Time
        self.time = tk.StringVar()
        self.time_update()
        
        # Sunset auto-on
        self.auto_on_var = tk.IntVar(value=self.config.app_settings.auto_on_var)
        self.offset = tk.StringVar(value=self.config.app_settings.offset)
        if self.auto_on_var.get() == 1:
            self.sunset_turn_on()

        # Auto-off
        self.auto_off_var = tk.IntVar(value=self.config.app_settings.auto_off_var)
        self.off_time = tk.StringVar(value=self.config.app_settings.off_time)
        if self.auto_off_var.get() == 1:
            self.auto_off()

        # Exit behavior
        self.exit_var = tk.IntVar(value=self.config.app_settings.exit_var)

        # Validation and errors
        self.loc_vcmd: tuple[str, Literal['%P']] = (self.register(self.loc_validate), "%P")
        self.loc_errmsg = tk.StringVar()

        self.ip_vcmd: tuple[str, Literal['%P']] = (self.register(self.ip_validate), "%P")
        self.ip_errmsg = tk.StringVar()
    
    def _init_external(self) -> None:
        # Configuration manager
        self.config = ConfigManager()
        self.config.load()
        
        # Bulb controller
        self.bulb = BulbController(self.config.network_settings.ip, self.set_bulb_state)

        # Http requests handler
        self.http = HttpRequests()

        # Loops controller
        self.turn_on_loop: LoopController | None = None
        self.turn_off_loop: LoopController | None = None
    
    def _bind_keys(self) -> None:
        self.bind(sequence="<Escape>", func=self.exit)

    def _init_images(self) -> None:
        self.img_bulb_on = tk.PhotoImage(file="bulb_on.gif")
        self.img_bulb_off = tk.PhotoImage(file="bulb_off.gif")

    def open_settings_window(self) -> None:
        self.settings_window = tk.Toplevel(self)
        self.settings_window.title("Settings")
        self.settings_window.grab_set() # This method routes all events for this application to this widget, so the focus will be on this window.

        # IP address text label
        ttk.Label(self.settings_window, text="Bulb IP address:").grid(column=0, row=0, padx=5, pady=3, sticky="w")    
        ttk.Label(self.settings_window, textvariable=self.ip_label).grid(column=1, row=0, padx=5, pady=3)

        # IP address entry
        self.user_input_ip = tk.StringVar()
        ttk.Label(self.settings_window, text="Set IP addr:").grid(column=0, row=1, padx=5, pady=3, sticky="w")
        self.ip_entry = ttk.Entry(self.settings_window, textvariable=self.user_input_ip)
        self.ip_entry.grid(column=1, row=1)
        self.ip_btn = ttk.Button(self.settings_window, text="Set", command=self.ip_validate)
        self.ip_btn.grid(column=2, row=1, padx=5)

        # Auto-on at sunset checkbutton
        self.auto_on_check: ttk.Checkbutton = ttk.Checkbutton(self.settings_window, text="Auto-on at sunset", command=self.handle_sunset_turn_on_widgets, variable=self.auto_on_var)
        self.auto_on_check.grid(column=0, row=2, padx=5, pady=3, sticky="w")

        # Auto-on time offset spinbox
        ttk.Label(self.settings_window, text="Set time offset:").grid(column=0, row=3, padx=5, pady=3, sticky="w")
        self.spnbox = ttk.Spinbox(self.settings_window, from_=-60.0, to=60.0, increment=10.0, textvariable=self.offset, command=self.sunset_turn_on, wrap=True, width=3)
        self.spnbox.state(["readonly"])
        if not self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["disabled"])
        self.spnbox.grid(column=1, row=3, padx=5, pady=3, sticky="w")
        ttk.Label(self.settings_window, text="minutes").grid(column=1, row=3)

        # Auto-off checkbutton
        self.auto_off_check = ttk.Checkbutton(self.settings_window, text="Auto-off", command=self.handle_auto_off_widgets, variable=self.auto_off_var)
        self.auto_off_check.grid(column=0, row=4, padx=5, pady=3, sticky="w")
 
        # Auto-off time combobox
        ttk.Label(self.settings_window, text="Set auto-off time:").grid(column=0, row=5, padx=5, pady=3, sticky="w")
        self.cmbbox = ttk.Combobox(self.settings_window, textvariable=self.off_time, width=5)
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
        self.cmbbox.bind('<<ComboboxSelected>>', self.update_turn_off_time)
        self.cmbbox.grid(column=1, row=5, sticky="w")

        # Location entry
        self.user_input_loc = tk.StringVar()
        ttk.Label(self.settings_window, text="Set new location:").grid(column=0, row=6, padx=5, pady=3, sticky="w")
        self.loc_entry = ttk.Entry(self.settings_window, textvariable=self.user_input_loc, validate="key", validatecommand=self.loc_vcmd)
        self.loc_entry.grid(column=1, row=6)
        ttk.Label(self.settings_window, font="TkSmallCaptionFont", foreground="red", textvariable=self.loc_errmsg).grid(column=1, row=7, sticky="w")
        self.loc_btn = ttk.Button(self.settings_window, text="Set", command=self.set_location, state="disabled")
        self.loc_btn.grid(column=2, row=6, padx=5)

        # Exit auto-off checkbutton
        self.exit_auto_off_check = ttk.Checkbutton(self.settings_window, text="Auto-off at exit", variable=self.exit_var)
        self.exit_auto_off_check.grid(column=0, row=7, padx=5, pady=3, sticky="w")

        # Save configuration button
        ttk.Button(self.settings_window, text="Save config", command=self.save_config).grid(column=2, row=8, padx=5, pady=3)

        # Close settings window button
        ttk.Button(self.settings_window, text="Close", command=self.settings_window.destroy).grid(column=0, row=8, padx=5, pady=3)
    
    def toggle_bulb(self) -> None:
        # This method is needed because self.bulb instance can change during runtime.
        self.bulb.toggle()

    def handle_sunset_turn_on_widgets(self) -> None:
        ''' Change state of spinbox according to sunset turn on checkbox state. Call sunset_turn_on() on every change. '''
        if self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["!disabled"])
            print("Sunset turn on enabled.")
            self.sunset_turn_on()
        else:
            self.spnbox.state(["disabled"])
            print("Sunset turn on disabled.")
            self.sunset_turn_on()

    def sunset_turn_on(self) -> None:
        ''' Start the turn on loop and calculate turn on time if auto_on_var is true (int 1), stop the loop if auto_on_var is false (int 0). '''
        if not self.turn_on_loop:
            self.turn_on_loop = LoopController(self, 1000, self.turn_on_task)

        if self.auto_on_var.get() == 1:
            self.turn_on_time: str = add_subtract_minutes(self.sunset.get(), self.offset.get())
            self.turn_on_loop.start()
        else:
            self.turn_on_loop.stop()
    
    def turn_on_task(self) -> None:
        ''' Turn on the bulb if current time matches scheduled time. '''
        if datetime.strptime(self.turn_on_time, "%H:%M").time() <= datetime.now().time():
            self.bulb.turn_on()
            if self.turn_on_loop:
                self.turn_on_loop.stop()
                self.turn_on_loop = None
            print("Bulb turned on.")

    def time_update(self) -> None:
        self.time.set(datetime.now().strftime("%H:%M"))
        self.after(1000, self.time_update)
    
    def handle_auto_off_widgets(self) -> None:
        ''' Change state of combobox according to auto-off checkbox state. Call auto_off() on every change. '''
        if self.auto_off_check.instate(["selected"]):
            self.cmbbox.state(["!disabled"])
            self.auto_off()
        else:
            self.cmbbox.state(["disabled"])
            self.auto_off()

    def auto_off(self) -> None:
        ''' Start the turn off loop and get datetime object corresponding to set turn off time if auto_off_var is true (int 1), stop the loop if auto_off_var is false (int 0). '''
        if not self.turn_off_loop:
            self.turn_off_loop = LoopController(self, 1000, self.turn_off_task)

        if self.auto_off_var.get() == 1:
            self.turn_off_time: datetime = get_target_datetime(self.off_time.get())
            self.turn_off_loop.start()
        else:
            self.turn_off_loop.stop()
    
    def turn_off_task(self) -> None:
        ''' Turn off the bulb if current time matches scheduled time. '''
        if self.turn_off_time <= datetime.now():
            self.bulb.turn_off()
            if self.turn_off_loop:
                self.turn_off_loop.stop()
                self.turn_off_loop = None
            print("Bulb turned off.")
    
    def exit(self, *args) -> None:
        if self.exit_var.get():
            self.bulb.turn_off()
        self.destroy()

    def set_bulb_state(self, state: str) -> None:
        self.bulb_state.set(state)
        self.state_label["image"] = self.img_bulb_on if state == "on" else self.img_bulb_off

    def set_location(self) -> None:
        try:
            location: str
            sunset: str
            self.latitude, self.longitude, location, sunset = self.http.set_location(self.user_input_loc.get())
            self.location.set(location)
            self.sunset.set(sunset)
        except KeyError:
            self.loc_errmsg.set("Location not found.")

    def set_ip(self) -> None:
        self.config.network_settings.ip = self.user_input_ip.get()
        self.bulb = BulbController(self.config.network_settings.ip, self.set_bulb_state)
        self.ip_label.set(self.config.network_settings.ip)
        self.ip_entry.delete(0, "end")
        
    def loc_validate(self, new_entry: str) -> bool:
        self.loc_errmsg.set("")
        valid: bool = new_entry.isalpha() or new_entry == ""
        self.loc_btn.state(["!disabled"]) if valid else self.loc_btn.state(["disabled"])
        if valid:
            return valid
        else:
            self.loc_errmsg.set("Only letters allowed.")
            return valid
    
    def ip_validate(self) -> None:
        valid: re.Match[str] | None = re.fullmatch(r"(\b25[0-5]|\b2[0-4][0-9]|\b[01]?[0-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}", self.user_input_ip.get())
        if valid:
            self.set_ip()
        else:
            messagebox.showerror("Invalid IP", "Enter valid IP address.")
        
    def update_turn_off_time(self, event: tk.Event) -> None:
        ''' Set new auto-off time after combobox value change. '''
        combobox: ttk.Combobox = cast(ttk.Combobox, event.widget)
        self.turn_off_time: datetime = get_target_datetime(combobox.get())
    
    def save_config(self) -> None:
        ''' Set configuration attributes at current state and save to file. '''
        self.config.loc_config.location = self.location.get()
        self.config.loc_config.latitude = self.latitude
        self.config.loc_config.longitude = self.longitude

        self.config.app_settings.auto_off_var = self.auto_off_var.get()
        self.config.app_settings.auto_on_var = self.auto_on_var.get()
        self.config.app_settings.exit_var = self.exit_var.get()
        self.config.app_settings.off_time = self.off_time.get()
        self.config.app_settings.offset = self.offset.get()

        self.config.save()
        
if __name__ == '__main__':
    app = App()
    app.mainloop()