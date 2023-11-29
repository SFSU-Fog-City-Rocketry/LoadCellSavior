import os
import sys
import glob
import time
import serial
import signal
import logging
from rich import print
from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True)]
)
log = logging.getLogger("rich")

OUTPUT_DIR = "./OutputData"
BAUD = 9600
PORT = "COM4"
VERBOSE = False
arduino = None
csv_text = "Time_Ms,LoadCellReading_Grams\n"
ms_at_start = 0
ms_since_start = 0

def startup():
    global VERBOSE, OUTPUT_DIR, BAUD, PORT, arduino, ms_at_start, ms_since_start

    print("[bold white]LoadCellSavior by Ethan Hanlon[/bold white]")
    print("[bold yellow](c) 2023 Fog City Rocketry[/bold yellow] at [bold purple]San Francisco State University[/bold purple]")
    args = sys.argv
    if "-h" in args or "--help" in args:
        print("""
python3 lcs.py \[--help/-h] \[--output/-o <output directory>] \[--baud/-b <baud>] \[--port/-p <comm port>] \[--verbose/-v] \[--os/-o <windows/mac/linux>]
              
Logs incoming serial data from the load cell to a CSV file along with time info.
Time is stored in milliseconds and is counted from the moment this program establishes a connection to the load cell.
              
[bold green]--help / -h[/bold green]: Displays this help message and exits.
[bold green]--output / -o <output dir>[/bold green]: Specifies a folder to output the data from. Defaults to ./OutputData.
[bold green]--baud / -b <baud rate>[/bold green]: Sets a baud rate for the connection. Defaults to 9600.
[bold green]--port / -p <port>[/bold green]: Comms port to use. Defaults to COM4 in Windows mode and /dev/ttyUSB0 in Linux mode.
[bold green]--verbose / -v[/bold green]: Enables verbose logging.
[bold green]--os <windows/mac/linux>[/bold green]: Sets the operating system. Defaults to Windows.
""")
        sys.exit(0)
    
    # Verbose
    if "--verbose" in args or "-v" in args:
        VERBOSE = True
        log.info("Verbose logging enabled.")
    
    # Output Directory
    if "--output" in args or "-o" in args:
        INDEX = sys.argv.index("--output") if "--output" in sys.argv else sys.argv.index("-o")
        if (INDEX == (len(sys.argv)) + 1):
            log.fatal("Input Error: Output parameter specified, but no output directory specified!")
            sys.exit(1)

        OUTPUT_DIR = sys.argv[INDEX + 1]
        try:
            open(OUTPUT_DIR)
        except FileNotFoundError:
            log.fatal("Input Error: Output parameter points to directory that does not exist!")
            sys.exit(1)
        if VERBOSE: log.info(f"Output directory set to {OUTPUT_DIR}")
    
    # Baud
    if "--baud" in args or "-b" in args:
        INDEX = sys.argv.index("--baud") if "--baud" in sys.argv else sys.argv.index("-b")
        if (INDEX == (len(sys.argv)) + 1):
            log.fatal("Input Error: Baud parameter specified, but no output directory specified!")
            sys.exit(1)

        BAUD = sys.argv[INDEX + 1]

        try:
            BAUD = int(BAUD)
        except ValueError:
            log.fatal("Input Error: Baud rate is invalid. Must be an integer.")
        
        if VERBOSE: log.info(f"Baud set to {BAUD}")
    # Port
    if "--port" in args or "-p" in args:
        INDEX = sys.argv.index("--port") if "--port" in sys.argv else sys.argv.index("-p")
        if (INDEX == (len(sys.argv)) + 1):
            log.fatal("Input Error: Port parameter specified, but no port is specified")
            sys.exit(1)

        PORT = sys.argv[INDEX + 1]
        if VERBOSE: log.info(f"Port set to {PORT}")
    
    # OS
    if "--os" in args:
        INDEX = sys.argv.index("--os") if "--os" in sys.argv else sys.argv.index("-o")
        if (INDEX == (len(sys.argv)) + 1):
            log.fatal("Input Error: OS parameter specified, but no OS is specified")
            sys.exit(1)

        OS = sys.argv[INDEX + 1]

        if OS.lower() not in ["windows", "mac", "linux"]:
            log.fatal("Input Error: OS parameter is invalid. Must be one of windows, mac, or linux.")
            sys.exit(1)
        if VERBOSE: log.info(f"OS set to {OS}")

        # The main thing this does is set the default port
        # If the user specifies a port, this will do nothing
        if "--port" in args or "-p" in args:
            log.info("Port specified, ignoring OS parameter.")
        else:
            match OS.lower():
                case "windows":
                    PORT = "COM4"
                case "mac":
                    PORT = "/dev/ttyUSB0"
                case "linux":
                    PORT = "/dev/ttyUSB0"
    
    try:
        arduino = serial.Serial(PORT, BAUD)
    except serial.SerialException:
        log.fatal(f"Serial Exception: Could not connect to {PORT} at {BAUD} baud.")
        log.fatal("Check your connections and try again.")
        sys.exit(1)
    
    log.info(f"Connected to {PORT} at {BAUD} baud.")
    ms_at_start = int(time.time() * 1000)
    ms_since_start = 0
    while True:
        loop()

def loop():
    global csv_text, ms_since_start, arduino
    if arduino is None or not arduino.is_open:
        log.fatal("Serial connection closed unexpectedly.")
        sys.exit(1)
    
    # Read the serial data
    data = arduino.readline().decode("utf-8").strip()
    # If the data is empty, ignore it
    if data == "":
        return
    # If the data is not a number, ignore it
    try:
        data = int(data)
    except ValueError:
        return
    
    # Increment the time
    ms_since_start = int(time.time() * 1000) - ms_at_start
    # Add the data to the csv text
    csv_text += f"{ms_since_start},{data}\n"
    # Print the data if debug prints are enabled
    if VERBOSE: print(f"{ms_since_start} ms: {data} grams")

sigint_count = 0
def handle_sigint():
    if (sigint_count > 0):
        log.fatal("SIGINT received twice, exiting.")
        sys.exit(1)

    sigint_count += 1
    log.info("SIGINT received. Closing serial connection, saving data, and exiting.")
    log.info("Press CTRL+C again to force exit.")

    # Close serial connection
    arduino.close()

    # Save data
    # The data is stored in the csv_text variable
    # It's going to be named "LoadCellData_*.csv" where * is replaced with the highest number in the OutputData folder plus one
    # Get a list of all the files in the output folder
    files = glob.glob(f"{OUTPUT_DIR}/*.csv")
    # Extract the numbers from these filenames
    numbers = [int(os.path.splitext(os.path.basename(file))[0].split('_')[1]) for file in files]
    # Get the highest number
    highest = max(numbers)
    # Create the new filename
    filename = f"LoadCellData_{highest + 1}.csv"
    # Write the data to the file
    with open(f"{OUTPUT_DIR}/{filename}", "w") as f:
        f.write(csv_text)
    log.info(f"Saved data to {OUTPUT_DIR}/{filename}")
    log.info("Exiting.")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)
    
if __name__ == "__main__":
    startup()
