from yeelight import Bulb
from datetime import datetime, timedelta
import requests
from tkinter import *
from tkinter import ttk
import json

BULB_IP = "192.168.0.18"
URL = "https://api.sunrisesunset.io/json?"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
LOCATION = "Bydgoszcz"
LATITUDE = "53.123482" # Bydgoszcz latitude
LONGITUDE = "18.008438" # Bydgoszcz longitude

def add_subtract_minutes(time: str, minutes: str) -> str:
        time_obj: datetime = datetime.strptime(time, "%H:%M")
        new_time: datetime = time_obj + timedelta(minutes=int(minutes))
        
        return new_time.strftime("%H:%M")

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
    
class App(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Yeelight Bulb Manager")
        config_data: dict[str, str | int] = self.load_config()
        self.bulb: Bulb = Bulb(config_data.get("bulb_ip", BULB_IP))
        self.latitude: str = str(config_data.get("latitude", LATITUDE))
        self.longitude: str = str(config_data.get("longitude", LONGITUDE))
        self.location = StringVar(value=str(config_data.get("location", LOCATION)))
        self.auto_on_var = IntVar(value=int(config_data.get("auto_on_var", 0)))
        self.offset = StringVar(value=str(config_data.get("offset", "0")))
        self.auto_off_var = IntVar(value=int(config_data.get("auto_off_var", 0)))
        self.off_time = StringVar(value=str(config_data.get("off_time", "00:00")))
        self.exit_var = IntVar(value=int(config_data.get("exit_var", 0)))

        self.http = HttpRequests()
        self.vcmd = (self.register(self.validate), "%P")
        self.errmsg = StringVar()
        self.create_widgets()
        self.bind(sequence="<Escape>", func=self.exit)
    
    def create_widgets(self) -> None:
        # Create mainframe
        self.mainframe = ttk.Frame(self, padding="5")
        self.mainframe.grid(column=0, row=0, sticky="n s e w")

        # Bulb state image label
        self.bulb_state = StringVar()
        self.img_bulb_on = PhotoImage(file="bulb_on.gif")
        self.img_bulb_off = PhotoImage(file="bulb_off.gif")
        self.state_label = ttk.Label(self.mainframe, textvariable=self.bulb_state)
        self.state_label.grid(column=0, row=0, rowspan=3)
        self.set_bulb_state()

        # Toggle button
        ttk.Button(self.mainframe, text="Toggle", command=self.toggle_bulb).grid(column=1, row=1)

        # Time text label
        self.time = StringVar()
        self.time_update()
        ttk.Label(self.mainframe, text="Time:").grid(column=3, row=0, sticky="s")
        ttk.Label(self.mainframe, textvariable=self.time).grid(column=4, row=0, sticky="w s")

        # Location text label
        ttk.Label(self.mainframe, text="Location:").grid(column=3, row=1)
        ttk.Label(self.mainframe, textvariable=self.location).grid(column=4, row=1, sticky="w")

        # Sunset time text label
        self.sunset = StringVar(value=self.http.get_sunset(self.latitude, self.longitude))
        ttk.Label(self.mainframe, text="Sunset at location:").grid(column=3, row=2, sticky="n")
        ttk.Label(self.mainframe, textvariable=self.sunset).grid(column=4, row=2, sticky="w n")

        # Horizontal separator
        ttk.Separator(self.mainframe, orient="horizontal").grid(row=3, columnspan=5, sticky="e w", pady=10)

        # Auto-on at sunset checkbutton
        self.auto_on_check: ttk.Checkbutton = ttk.Checkbutton(self.mainframe, text="Auto-on at sunset", command=self.sunset_turn_on, variable=self.auto_on_var)
        self.auto_on_check.grid(column=0, row=4)

        # Auto-on time offset spinbox
        ttk.Label(self.mainframe, text="Set time offset:").grid(column=0, row=5)
        self.spnbox = ttk.Spinbox(self.mainframe, from_=-60.0, to=60.0, increment=10.0, textvariable=self.offset, command=self.calculate_turn_on_time, wrap=True, width=3)
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

    def toggle_bulb(self) -> None:
        self.bulb.toggle()
        self.set_bulb_state()
    
    def sunset_turn_on(self) -> None:
        if self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["!disabled"])
            print("Sunset turn on enabled.")
            self.calculate_turn_on_time()
            self.sunset_turn_on_loop()
        else:
            self.spnbox.state(["disabled"])
            print("Sunset turn on disabled.")
    
    def sunset_turn_on_loop(self) -> None:
        if self.time_turn_on == self.time.get():
            if self.bulb_state.get() == "off":
                self.bulb.turn_on()
                self.set_bulb_state()
                print("Bulb turned on.")
        if self.auto_on_check.instate(["selected"]):
            self.after(1000, self.sunset_turn_on_loop)
    
    def calculate_turn_on_time(self) -> None:
        self.time_turn_on: str = add_subtract_minutes(self.sunset.get(), self.offset.get())

    def time_update(self) -> None:
        self.time.set(datetime.now().strftime("%H:%M"))
        self.after(1000, self.time_update)
    
    def auto_off(self) -> None:
        if self.auto_off_check.instate(["selected"]):
            self.cmbbox.state(["!disabled"])
            print("Auto turn-off enabled.")
            self.auto_off_loop()
        else:
            self.cmbbox.state(["disabled"])
            print("Auto turn-off disabled.")
    
    def auto_off_loop(self) -> None:
        if self.off_time.get() == self.time.get():
                if self.bulb_state.get() == "on":
                    self.bulb.turn_off()
                    self.set_bulb_state()
                    print("Bulb turned off.")
        if self.auto_off_check.instate(["selected"]):
            self.after(1000, self.auto_off_loop)
    
    def exit(self, *args) -> None:
        if self.ext_auto_off_check.instate(["selected"]):
            self.bulb.turn_off()
        self.destroy()

    def set_bulb_state(self) -> None:
        self.bulb_state.set(self.bulb.get_properties()["power"])
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
        valid = new_entry.isalpha() or new_entry == ""
        self.loc_btn.state(["!disabled"]) if valid else self.loc_btn.state(["disabled"])
        if valid:
            return valid
        else:
            self.errmsg.set("Only letters allowed.")
            return valid
    
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

        with open("config.json", "w") as file:
            json.dump(config_data, file)

        print("Configuration saved.")

    def load_config(self) -> dict[str, str | int]:
        try:
            with open("config.json", "r") as file:
                config_data: dict[str, str | int] = json.load(file)
            return config_data
        except FileNotFoundError:
            print("Config file not found. Loading defaults.")
            return {}
        
if __name__ == '__main__':
    app = App()
    app.mainloop()