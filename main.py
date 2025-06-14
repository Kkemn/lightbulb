from yeelight import Bulb
from datetime import datetime
import requests
from tkinter import *
from tkinter import ttk

BULB_IP = "192.168.0.15"
URL = "https://api.sunrisesunset.io/json?"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
LOCATION = "Bydgoszcz"
LATITUDE = "53.123482" # Bydgoszcz latitude
LONGITUDE = "18.008438" # Bydgoszcz longitude

class Application(Tk):
    def __init__(self):
        super().__init__()
        self.bulb = Bulb(BULB_IP)
        self.title("Yeelight Bulb Manager")
        # self.location = LOCATION
        self.latitude = LATITUDE
        self.longitude = LONGITUDE
        self.vcmd = (self.register(self.validate), "%P")
        self.errmsg = StringVar()
        self.create_widgets()
        self.bind(sequence="<Escape>", func=self.exit)
    
    def create_widgets(self):
        # Create mainframe
        self.mainframe = ttk.Frame(self, padding="5")
        self.mainframe.grid(column=0, row=0, sticky="n s e w")

        # Bulb state text label
        self.bulb_state = StringVar()
        self.img_bulb_on = PhotoImage(file="bulb_on.gif")
        self.img_bulb_off = PhotoImage(file="bulb_off.gif")
        self.state_label = ttk.Label(self.mainframe, textvariable=self.bulb_state)
        self.state_label.grid(column=0, row=0)
        self.set_bulb_state()

        # Toggle button
        ttk.Button(self.mainframe, text="Toggle", command=self.toggle_bulb).grid(column=1, row=0)

        # Time text label
        self.time = StringVar()
        self.time_update()
        ttk.Label(self.mainframe, text="Time:").grid(column=0, row=1)
        ttk.Label(self.mainframe, textvariable=self.time).grid(column=1, row=1)

        # Location text label
        self.location = StringVar()
        self.location.set(LOCATION)
        ttk.Label(self.mainframe, text="Location:").grid(column=0, row=2)
        ttk.Label(self.mainframe, textvariable=self.location).grid(column=1, row=2)

        # Sunset time text label
        self.sunset = StringVar()
        self.get_sunset()
        ttk.Label(self.mainframe, text="Sunset at location:").grid(column=0, row=3)
        ttk.Label(self.mainframe, textvariable=self.sunset).grid(column=1, row=3)

        # Auto-on at sunset checkbutton
        self.auto_on_check: ttk.Checkbutton = ttk.Checkbutton(self.mainframe, text="Auto-on at sunset", command=self.sunset_turn_on)
        self.auto_on_check.grid(column=0, row=4)

        # Auto-on time offset spinbox
        ttk.Label(self.mainframe, text="Set time offset:").grid(column=0, row=5)
        self.offset = StringVar()
        self.offset.set("0")
        self.spnbox = ttk.Spinbox(self.mainframe, from_=-60.0, to=60.0, increment=10.0, textvariable=self.offset, command=self.calculate_turn_on_time, wrap=True, width=3)
        self.spnbox.state(["readonly"])
        if not self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["disabled"])
        self.spnbox.grid(column=1, row=5)
        ttk.Label(self.mainframe, text="minutes").grid(column=2, row=5, sticky='w')

        # Auto-off checkbutton
        self.auto_off_check = ttk.Checkbutton(self.mainframe, text="Auto-off", command=self.auto_off)
        self.auto_off_check.grid(column=0, row=7)

        # Auto-off time combobox
        ttk.Label(self.mainframe, text="Set auto-off time:").grid(column=0, row=8)
        self.off_time = StringVar()
        self.off_time.set("00:00")
        self.cmbbox = ttk.Combobox(self.mainframe, textvariable=self.off_time, width=5)
        self.cmbbox["values"] = [
                            str(h)+":0"+str(m)
                            if m < 10
                            else
                            str(h)+":"+str(m)
                            for h in range(24)
                            for m in range(60)
                            ]
        self.cmbbox.state(["readonly"])
        if not self.auto_off_check.instate(["selected"]):
            self.cmbbox.state(["disabled"])
        self.cmbbox.grid(column=1, row=8)

        # Exit auto-off checkbutton
        self.ext_auto_off_check = ttk.Checkbutton(self.mainframe, text="Auto-off at exit")
        self.ext_auto_off_check.grid(column=0, row=9)

        # Location entry
        self.user_input_loc = StringVar()
        ttk.Label(self.mainframe, text="Set new location:").grid(column=2, row=2)
        self.loc_entry = ttk.Entry(self.mainframe, textvariable=self.user_input_loc, validate="key", validatecommand=self.vcmd)
        self.loc_entry.grid(column=2, row=3)
        ttk.Label(self.mainframe, font="TkSmallCaptionFont", foreground="red", textvariable=self.errmsg).grid(column=2, row=4)
        self.loc_btn = ttk.Button(self.mainframe, text="Set", command=self.set_location)
        self.loc_btn.state(["disabled"])
        self.loc_btn.grid(column=3, row=4)

        # Exit button
        ttk.Button(self.mainframe, text="Exit", command=self.exit).grid(column=3, row=10)

    def toggle_bulb(self):
        self.bulb.toggle()
        self.set_bulb_state()
    
    def get_sunset(self):
        payload: dict[str, str] = {'lat': self.latitude, 'lng': self.longitude, 'time_format': '24'}
        response: requests.Response = requests.get(url=URL, params=payload)
        self.sunset.set(response.json()['results']['sunset'][:5])
    
    def sunset_turn_on(self):
        if self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["!disabled"])
            print("Sunset turn on enabled.")
            self.calculate_turn_on_time()
            self.sunset_turn_on_loop()
        else:
            self.spnbox.state(["disabled"])
            print("Sunset turn on disabled.")
    
    def sunset_turn_on_loop(self):
        if self.time_turn_on == self.time.get():
            if self.bulb_state.get() == "off":
                self.bulb.turn_on()
                self.set_bulb_state()
                print("Bulb turned on.")
        if self.auto_on_check.instate(["selected"]):
            self.after(1000, self.sunset_turn_on_loop)
    
    def calculate_turn_on_time(self):
        sset: str = self.sunset.get()
        ofst = int(self.offset.get())
        if int(sset[3:]) < abs(int(ofst)):
            hours: int = int(sset[:2]) - 1
            minutes: int = 60 + int(sset[3:]) + int(ofst)
            while minutes > 60:
                hours += 1
                minutes -= 60
        else:
            hours = int(sset[:2])
            minutes: int = int(sset[3:]) + int(ofst)
            while minutes > 60:
                hours += 1
                minutes -= 60
        self.time_turn_on: str = str(hours)+":"+(str(minutes) if minutes >= 10 else "0"+str(minutes))

    def time_update(self):
        self.time.set(datetime.now().strftime("%H:%M"))
        self.after(1000, self.time_update)
    
    def auto_off(self):
        if self.auto_off_check.instate(["selected"]):
            self.cmbbox.state(["!disabled"])
            print("Auto turn-off enabled.")
            self.auto_off_loop()
        else:
            self.cmbbox.state(["disabled"])
            print("Auto turn-off disabled.")
    
    def auto_off_loop(self):
        if self.off_time.get() == self.time.get():
                if self.bulb_state.get() == "on":
                    self.bulb.turn_off()
                    self.set_bulb_state()
                    print("Bulb turned off.")
        if self.auto_off_check.instate(["selected"]):
            self.after(1000, self.auto_off_loop)
    
    def exit(self, *args):
        if self.ext_auto_off_check.instate(["selected"]):
            self.bulb.turn_off()
        self.destroy()

    def set_bulb_state(self):
        self.bulb_state.set(self.bulb.get_properties()["power"])
        if self.bulb_state.get() == "on":
            self.state_label["image"] = self.img_bulb_on
        else:
            self.state_label["image"] = self.img_bulb_off

    def set_location(self):
        payload = {"name": self.user_input_loc.get(), "count": 1}
        response = requests.get(url=GEOCODING_URL, params=payload)
        print(response.status_code)
        if response.status_code == 200:
            self.latitude: str = str(response.json()['results'][0]['latitude'])
            self.longitude: str = str(response.json()['results'][0]['longitude'])
            self.location.set(response.json()['results'][0]['name'])
            self.get_sunset()
        elif response.status_code == 400:
            print("HTTP response 400")
            # wrong request - invalid location
            pass
        else:
            # wrong request - somethin else went wrong
            pass
  
    def validate(self, new_entry: str) -> bool:
        self.errmsg.set("")
        valid = new_entry.isalpha() or new_entry == ""
        self.loc_btn.state(["!disabled"]) if valid else self.loc_btn.state(["disabled"])
        if valid:
            return valid
        else:
            self.errmsg.set("Only letters allowed.")
            return valid
    

if __name__ == '__main__':
    app = Application()
    app.mainloop()