import logging
import requests
import winreg
import os
import platform
import subprocess
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

logger = logging.getLogger(__name__)

# Cache drivers for efficiency reasons
driver_cache = {"chrome": None, "firefox": None}

def is_firefox_installed():
    """Check if Firefox is installed on the system (Windows and Linux)."""
    # Define paths for Windows
    firefox_paths_windows = [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
    ]
    
    # Define paths for Linux
    firefox_paths_linux = [
        "/usr/bin/firefox",
        "/usr/local/bin/firefox"
    ]
    
    # Check if Firefox executable exists in the standard installation paths for Windows
    if platform.system() == "Windows":
        for path in firefox_paths_windows:
            if os.path.exists(path):
                return True

    elif platform.system() == "Linux":
        # Check if Firefox executable exists in the standard installation paths for Linux
        for path in firefox_paths_linux:
            if os.path.exists(path):
                return True
        
        # Optionally, check if Firefox is available in the PATH
        try:
            subprocess.run(["firefox", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    return False

def is_chrome_installed():
    """Check if Google Chrome is installed on the system (Windows and Linux)."""
    # Define paths for Windows
    chrome_paths_windows = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\{username}\AppData\Local\Google\Chrome\Application\chrome.exe"  # User-specific path
    ]
    
    # Define paths for Linux
    chrome_paths_linux = [
        "/usr/bin/google-chrome",
        "/opt/google/chrome/chrome"
    ]
    
    # Check if Chrome executable exists in the standard installation paths for Windows
    if platform.system() == "Windows":  # Windows
        for path in chrome_paths_windows:
            # Replace {username} with the actual username dynamically
            user_specific_path = path.replace("{username}", os.getlogin())
            if os.path.exists(user_specific_path):
                return True
        
        # Check the registry for Chrome installation on Windows
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as key:
                subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(subkeys):
                    subkey_name = winreg.EnumKey(key, i)
                    try:
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            if "Google Chrome" in display_name:
                                return True
                    except FileNotFoundError:
                        continue
        except Exception as e:
            print(f"An error occurred while accessing the registry: {e}")
            return False

    elif platform.system() == "Linux":  # Linux
        # Check if Chrome executable exists in the standard installation paths for Linux
        for path in chrome_paths_linux:
            if os.path.exists(path):
                return True
        
        # Optionally, check the symbolic link (common in many distributions)
        if os.path.exists("/usr/bin/google-chrome-stable"):
            return True

    return False

def get_driver(browser):
    """GET or INIT the Selenium WebDriver."""
    global driver_cache
    if driver_cache[browser] is None:
        if browser == "chrome":
            if not is_chrome_installed():
                raise EnvironmentError("Google Chrome is not installed. Please install Google Chrome to use this driver.")
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            driver_cache["chrome"] = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        elif browser == "firefox":
            if not is_firefox_installed():
                raise EnvironmentError("Firefox is not installed. Please install Firefox to use this driver.")
            options = webdriver.FirefoxOptions()
            options.add_argument("--headless")
            driver_cache["firefox"] = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
    return driver_cache[browser]

def search_ebay(query, result_queue, stop_event, browser="chrome"):
    query = requests.utils.quote(query)
    url = f"https://www.ebay.com/sch/i.html?_from=R40&_nkw={query}&_sacat=0"
    try:
        driver = get_driver(browser)
        driver.get(url)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.find_all("li", class_="s-item")
        for item in items:
            if stop_event.is_set():  # Check if the stop event is set
                logger.info("Search stopped.")
                return  # Exit the function if the stop event is set
            try:
                title = item.find("span", {"role": "heading"}).text.strip()
                if title == "Shop on eBay": continue
                price = item.find("span", class_="s-item__price").text.strip()
                link = item.find("a", class_="s-item__link")["href"]

                # Attempt to fetch image URL
                img_url = "Image Not Available"
                if link:
                    driver.get(link)
                    try:
                        wait = WebDriverWait(driver, 0.1)  # Reduced wait time
                        img_elem = wait.until(EC.presence_of_element_located((By.XPATH, "//img[@data-zoom-src]")))
                        img_url = img_elem.get_attribute("data-zoom-src")
                    except TimeoutException:
                        img_url = "Image Not Available"  # Fallback if the image is not found quickly

                result_queue.put(("eBay", title, price, img_url, link))
            except Exception as e:
                logger.error(f"Error processing eBay item: {e}")
    except Exception as e:
        logger.error(f"Error fetching eBay results: {e}")
    finally:
        # Do not quit the driver here, as it is cached for reuse
        pass