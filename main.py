#!/usr/bin/env python3
import os
import signal
import sys
import platform
import subprocess
import importlib.util       # Lib loader as import utility, thanks python

# ANSI escape codes for text colors
BLACK = "\033[30m"   
RED = "\033[31m"     
GREEN = "\033[32m"   
YELLOW = "\033[33m"
BLUE = "\033[34m"    
MAGENTA = "\033[35m"
CYAN = "\033[36m"    
WHITE = "\033[37m"   
RESET = "\033[0m"

# List of required libraries (excluding tkinter as it's part of the std library)
required_libraries = {
    "pip": "pip",
    "logging": "logging",
    "argparse": "argparse",
    "threading": "threading",
    "queue": "queue",
    "tkinter": "tkinter",
    "requests": "requests",
    "Pillow": "PIL",
    "bs4": "bs4",
    "selenium": "selenium",
    "webdriver_manager": "webdriver_manager"
}


def check_sys():
	if platform.system() == "Windows":
		return f"{BLUE}Windows{RESET}"
	elif platform.system() == "Linux":
		return f"{GREEN}Linux{RESET}"
	else:
		 raise EnvironmentError("Unsupported operating system.")

def get_default_browser():
    """Return the default browser based on the operating system."""
    if platform.system() == 'Linux':
        return "firefox"
    elif platform.system() == 'Windows':
        return "chrome"
    else:
        raise EnvironmentError("Unsupported operating system.")

# INSTALL / UPDATE LIBS ROUTINES
def check_libraries_installed():
    """Check which libraries are missing."""
    missing_libraries = []
    for lib, module_name in required_libraries.items():
        if is_pip_installed() == False: 
            install_pip()
            update_pip()
        if module_name == "tkinter":
            try:
                import tkinter  # Special case for tkinter
            except ImportError:
                missing_libraries.append(lib)
            continue
        
        if importlib.util.find_spec(module_name) is None:
            missing_libraries.append(lib)
    return missing_libraries

def install_libraries(libraries):
    """Install the specified libraries using pip."""
    print("Installing required libraries. This may take a few minutes...")
    for lib in libraries:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
            print(f"{GREEN}Installed {lib}{RESET}")
        except subprocess.CalledProcessError:
            print(f"{RED}Failed to install {lib}. Please try running this script with administrator privileges.{RESET}")
            sys.exit(1)

def get_terminal_name():
    # Check for PowerShell specific environment variables
    if os.getenv('PSExecutionPolicy'):
        return "PowerShell"
    #
    #Check for Command Prompt specific environment variables
    if os.getenv('PROMPT') and os.getenv('COMSPEC'):
        return "Command Prompt"

    # Check for Windows Terminal running CMD
    if os.getenv('WT_SESSION'):
        if 'cmd' in os.getenv('WT_SESSION').lower():
            return "Command Prompt (Windows Terminal)"
        elif 'powershell' in os.getenv('WT_SESSION').lower():
            return "PowerShell (Windows Terminal)"

    # Check for Windows Console Host (cmd)
    if 'conhost.exe' in os.path.basename(sys.executable).lower():
        return "Command Prompt"

    # Fallback for generic Windows terminals
    if sys.platform == "win32":
        return "Unknown Windows Terminal"

    # Check for common Unix terminals
    term_env = os.getenv('TERM')
    if term_env:
        return term_env

    # Final fallback
    return "Unknown Terminal"

def is_pip_installed():
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def install_pip():
    print(f"{RED}pip is not installed{RESET}. {GREEN}Installing pip...{RESET}")
    terminal_name = get_terminal_name()
    if terminal_name in ["Command Prompt", "Windows Terminal"]:
        try:
            subprocess.run(["powershell", "-Command", 
                "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'"], 
                check=True)
            subprocess.check_call([sys.executable, 'get-pip.py'])
            os.remove('get-pip.py')
            print(f"{GREEN}pip has been successfully installed.{RESET}")
        except subprocess.CalledProcessError as e:
            print(f"{RED}Failed to install pip. Error: {e}. Please install it manually.{RESET}")
            sys.exit(1)
    else:
        try:
            subprocess.check_call([sys.executable, '-m', 'ensurepip'])
            print("{GREEN}pip has been successfully installed.{RESET}")
        except subprocess.CalledProcessError as e:
            print(f"{RED}Failed to install pip. Error: {e}. Please install it manually.{RESET}")
            sys.exit(1)

def update_pip():
    print("Updating pip to the latest version...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
        print("pip has been successfully updated.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to update pip. Error: {e}. Please update it manually.")
        sys.exit(1)
# END OF INSTALL / UPDATE LIBS ROUTINES



# RUN ROUTINE            
def main():
    print(f"System: {check_sys()}")
    # update_pip()
    # Check for missing libraries
    missing_libraries = check_libraries_installed()

    if missing_libraries:
        print(f"Missing libraries: {RED}{', '.join(missing_libraries)}{RESET}")
        
        response = input("Do you want to install them now? (y/n) (default is Y, Press Enter): ").strip().lower()
        
        # Set default response to 'y' if input is empty
        if response == '' or response == 'y':
            install_libraries(missing_libraries)
        elif response == 'n':
            print("Cannot run the program without required libraries. Exiting.")
            sys.exit(1)
        else:
            print("Invalid input. Please enter 'y' or 'n'.")
            sys.exit(1)
    else:
        print(f"{GREEN}All required libraries are already installed.{RESET}")
    
    # Only import after checking and potentially installing libraries (I can remove this later, TODO)
    import tkinter as tk
    from LPS import LPSSearchApp
    root = tk.Tk()  # Create the main application window
    app = LPSSearchApp(root)  # Initialize the LPS application
    app.start() # start creating logs
    current_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_dir, 'YAS.png')
    from tkinter import PhotoImage
    icon = PhotoImage(file=icon_path)
    root.iconphoto(False, icon)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    def check_stop_event():
        if app.stop_event.is_set():
            root.quit()
        else:
            root.after(1000, check_stop_event)   # 1000ms check

    root.after(1000, check_stop_event)
    root.mainloop()

def on_closing():
    print("\tClosing the application...")
    #pid = os.getpid()
    #os.kill(pid, signal.SIGINT)
    sys.exit(0)  # Close the terminal as well


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")
        print("If the problem persists, please contact support --> (Your boyfriend!)")
        sys.exit(-1)
