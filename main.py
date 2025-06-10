from yeelight import Bulb
from datetime import datetime
import requests
from tkinter import *
from tkinter import ttk

BULB_IP = "192.168.0.15"
URL = "https://api.sunrisesunset.io/json?"
LOCATION = "Bydgoszcz"
LATITUDE = "53.123482" # Bydgoszcz latitude
LONGITUDE = "18.008438" # Bydgoszcz longitude

class Application(Tk):
    def __init__(self):
        super().__init__()
        self.bulb = Bulb(BULB_IP)
        self.title("Yeelight Bulb Manager")
        self.create_widgets()
    
    def create_widgets(self):
        # Create mainframe
        self.mainframe = ttk.Frame(self, padding="5")
        self.mainframe.grid(column=0, row=0, sticky="n s e w")

        # Bulb state text label
        self.bulb_state = StringVar()
        self.bulb_state.set(self.bulb.get_properties()["power"])
        ttk.Label(self.mainframe, textvariable=self.bulb_state).grid(column=0, row=0)

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
        self.auto_on_check: ttk.Checkbutton = ttk.Checkbutton(self.mainframe, text="Auto-On at sunset", command=self.sunset_turn_on)
        self.auto_on_check.grid(column=0, row=4)

        # Time offset widget
        ttk.Label(self.mainframe, text="Set time offset:").grid(column=0, row=5)
        self.offset = StringVar()
        self.offset.set("0")
        self.spnbox = ttk.Spinbox(self.mainframe, from_=-60.0, to=60.0, increment=10.0, textvariable=self.offset, command=self.calculate_turn_on_time, wrap=True, width=3)
        self.spnbox.state(["readonly"])
        if not self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["disabled"])
        self.spnbox.grid(column=0, row=6, sticky='e')
        ttk.Label(self.mainframe, text="minutes").grid(column=1, row=6, sticky='w')


    def toggle_bulb(self):
        self.bulb.toggle()
        self.bulb_state.set(self.bulb.get_properties()["power"])
    
    def get_sunset(self):
        payload: dict[str, str] = {'lat': LATITUDE, 'lng': LONGITUDE, 'time_format': '24'}
        response: requests.Response = requests.get(url=URL, params=payload)
        self.sunset.set(response.json()['results']['sunset'][:5]) #, response.json()['results']['date']
    
    def sunset_turn_on(self):
        if self.auto_on_check.instate(["selected"]):
            self.spnbox.state(["!disabled"])
            print("Sunset turn on enabled.")
            self.calculate_turn_on_time()
            self.sunset_turn_on_loop()
            # if self.sunset.get() == self.time.get():
            #     if self.bulb_state.get() == "off":
            #         self.bulb.turn_on()
            #         self.bulb_state.set(self.bulb.get_properties()["power"])
            # self.after(1000, self.sunset_turn_on)
        else:
            print("Sunset turn on disabled.")
    
    def sunset_turn_on_loop(self):
        if self.time_turn_on == self.time.get():
            if self.bulb_state.get() == "off":
                self.bulb.turn_on()
                self.bulb_state.set(self.bulb.get_properties()["power"])
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

if __name__ == '__main__':
    app = Application()
    app.mainloop()