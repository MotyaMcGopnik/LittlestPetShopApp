import argparse
import logging
import os
import platform
import sys
from logging.handlers import QueueHandler, QueueListener
import threading
import queue    
import tkinter as tk
from tkinter import ttk
import requests
from io import BytesIO
from PIL import Image, ImageTk
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

# Configure logging
parser = argparse.ArgumentParser(description='LPS Pet Search Application V1.0')
parser.add_argument('-d', action='store_true', help='Enable basic debug logging')
parser.add_argument('-a', action='store_true', help='Enable advanced debug logging')
parser.add_argument('--browser', choices=['chrome', 'firefox'], help='Specify the browser to use (default is determined by OS)')
args = parser.parse_args()

# Determine default browser based on the operating system
def get_default_browser():
    """Return the default browser based on the operating system."""
    if platform.system() == 'Linux':
        return "firefox"
    elif platform.system() == 'Windows':
        return "chrome"
    else:
        raise EnvironmentError("Unsupported operating system.")

# Set default browser if not specified by user
if args.browser is None:
    args.browser = get_default_browser()

if args.d and args.a:
    print("ADVANCED DEBUG MODE")
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
elif args.d:
    print("DEBUG MODE")
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')
else:
    print("\tSTARTING LPS SEARCH APP!")
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(asctime)s - %(message)s')

logger = logging.getLogger(__name__)

class LPSSearchApp:
    def __init__(self, master):
        self.master = master
        master.title("LPS Pet Search")
        master.geometry("800x600")

        # Queue for safely passing results between threads and the GUI
        self.log_queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.search_thread = None
        # Handle window closing
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Layout setup
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=0)
        master.rowconfigure(1, weight=1)

        self.search_frame = ttk.Frame(master, padding="10")
        self.search_frame.grid(row=0, column=0, sticky="nw", padx=10, pady=10)

        self.search_label = ttk.Label(self.search_frame, text="Enter LPS Number or LPS Name:")
        self.search_label.grid(row=0, column=0, padx=(0, 10))

        self.search_entry = ttk.Entry(self.search_frame, width=30)
        self.search_entry.grid(row=0, column=1)
        self.search_entry.bind("<Return>", self.search_pets)
        
        # Clear button
        self.clear_button = ttk.Button(self.search_frame, text="Clear", command=self.clear_search)
        self.clear_button.grid(row=0, column=2, padx=(10, 0))

        # Scrollable area
        self.canvas = tk.Canvas(master)
        self.canvas.configure(background='#f6d7da')
        self.canvas.grid(row=1, column=0, sticky="nsew")
        
        self.scrollbar = ttk.Scrollbar(master, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.grid(row=1, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Enable mouse wheel scrolling anywhere within the canvas
        self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

        # Enable click and drag scrolling
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)

        # Start processing results from the queue
        self.master.after(100, self.process_queue)
    
    def setup_logging(self):
        self.log_queue = queue.Queue(-1)
        queue_handler = QueueHandler(self.log_queue)
        self.handler = logging.StreamHandler()
        self.listener = QueueListener(self.log_queue, self.handler)

        root_logger = logging.getLogger()
        root_logger.addHandler(queue_handler)
        root_logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(levelname)s - %(message)s')
        self.handler.setFormatter(formatter)

        # Start the listener in a separate thread
        self.listener.start()
        
    def process_logs(self):
        """Process log messages from the queue."""
        if not self.master.winfo_exists():
            return  # Exit if the main window has been destroyed

        try:
            while True:
                try:
                    # Attempt to get multiple records in bursts
                    records = []
                    while True:
                        record = self.log_queue.get_nowait()
                        records.append(record)
                except queue.Empty:
                    break  # Exit the loop if no more records are available

                # Process all retrieved records
                for record in records:
                    logger = logging.getLogger(record.name)
                    logger.handle(record)

        except Exception as e:
            logger.error(f"Error processing logs: {e}")

        # Schedule the next log processing check
        self.master.after(100, self.process_logs)
        
    def start(self):
        # Call this method after creating the instance
        self.master.after(100, self.process_logs)  
        
    def clear_search(self):
        # Just restart the app, I am too lazy...
        logger.info("Restarting application...APPEARS IT CLEARED!")
        os.execv(sys.executable, ['python'] + sys.argv)
    
    def stop_search(self):
        """Stop the ongoing search."""
        self.stop_event.set()
        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.join(timeout=2)  # Wait up to 2 seconds for the thread to finish
        logger.info("Search stopped.")

    def on_closing(self):
        logger.info("Closing application...")
        self.stop_search()
        
        # Wait for the search thread to finish
        if self.search_thread and self.search_thread.is_alive():
            logger.info("Waiting for search thread to finish...")
            self.search_thread.join(timeout=5)  # Wait up to 5 seconds
            if self.search_thread.is_alive():
                logger.warning("Search thread did not finish in time.")
        
        # Clear the result queue
        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Application shutdown complete.")
        self.listener.stop()
        self.master.destroy()
        sys.exit(0)
    
    def on_mouse_wheel(self, event):
        """Scroll the canvas using the mouse wheel."""
        if event.delta > 0: 
            self.canvas.yview_scroll(-1, "units")  # Scroll up
        else: 
            self.canvas.yview_scroll(1, "units")   # Scroll down

    def on_drag_start(self, event):
        """Start the drag event for scrolling."""
        self.drag_start_y = event.y

    def on_drag_motion(self, event):
        """Scroll the canvas while dragging."""
        delta_y = self.drag_start_y - event.y
        self.canvas.yview_scroll(delta_y // 10, "units")  # Adjust the scrolling speed
        self.drag_start_y = event.y    
    
    def search_pets(self, event=None):
         # Cancel any ongoing search
        self.stop_event.set()
        self.stop_event.clear()  # Reset for the new search
        query = self.search_entry.get().strip()
        
        if not query:
            logger.warning("Search query is empty.")
            return
        try:
            int(query)
            query = "LPS " + query
        except ValueError:
            logger.debug("QUERY IS NOT A NUMBER")
        
        logger.info(f"Searching for: {query}")

        # Clear previous results
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Launch thread for eBay search
        import ebay_scraper
        self.stop_event.clear()  # Reset the stop event before starting a new search
        self.search_thread = threading.Thread(target=ebay_scraper.search_ebay, args=(query, self.result_queue, self.stop_event, args.browser), daemon=True)
        self.search_thread.start()
    
    def search_thread_function(self, query):
        try:
            ebay_scraper.search_ebay(query, self.result_queue, self.stop_event, args.browser)
        except Exception as e:
            logger.error(f"Error in search thread: {e}")
        finally:
            # Signal that the search is complete
            self.result_queue.put(None)
            
    def process_queue(self):
        listing_cnt = 0
        try:
            while True:
                result = self.result_queue.get_nowait()
                if result is None:
                    # Search is complete
                    logger.info("Search completed.")
                    break
                source, title, price, img_url, link = result    # extract useful information into variables thru thread-queue result
                listing_cnt += 1
                logger.debug(f"Listing #{listing_cnt}\nSource: {source}\tTitle: {title}\tPrice: {price}\n\tImage URL: {img_url}\n\tLink: {link}")
                self.add_listing(source, title, price, img_url, link)
        except queue.Empty:
            pass
        finally:
            # Schedule the next queue check
            self.master.after(100, self.process_queue)

    def add_listing(self, source, title, price, img_url, link):
        # Define a style for the frame
        style = ttk.Style()

        # Solid color for the main frame
        style.configure("Custom.TFrame",
                        background="#f6d7da",  # Solid color for the background
                        relief="flat",          # No borders or relief effect
                        padding=0)              # No internal padding

        # Solid color for labels
        style.configure("Custom.TLabel",
                        background="#f6d7da",   # Solid color for the background
                        font=("Helvetica", 10), # Set default font for labels
                        anchor="w")             # Align text to the left

        # Define the darker rectangle (border) surrounding the listing
        outer_frame = tk.Frame(
            self.scrollable_frame,
            bg="#c0a1a6",            # Darker pink background for the rectangle
            highlightbackground="#c0a1a6",  # Same as bg for uniformity
            highlightthickness=3     # Visible border thickness
        )
        outer_frame.pack(fill=tk.X, pady=1)  # Y space between listings ONLY

        # Create the inner frame inside the outer rectangle
        frame = ttk.Frame(outer_frame, style="Custom.TFrame")
        frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)  # No additional padding


        # Load and display the image
        try:
            if img_url and img_url != "Image Not Available":
                response = requests.get(img_url, timeout=5)  # Fetch the image from the URL
                response.raise_for_status()
                img_data = Image.open(BytesIO(response.content))
                img_data.thumbnail((100, 100), Image.LANCZOS)  # Resize to thumbnail size
                photo_image = ImageTk.PhotoImage(img_data)
            else:
                # Use a placeholder if the image is not available
                photo_image = ImageTk.PhotoImage(Image.new("RGB", (100, 100), color="grey"))
        except Exception as e:
            logger.error(f"Error loading image from {img_url}: {e}")
            photo_image = ImageTk.PhotoImage(Image.new("RGB", (100, 100), color="grey"))
        
        # Label for the image
        img_label = ttk.Label(frame, image=photo_image, style="Custom.TLabel")
        img_label.image = photo_image  # Keep a reference to avoid garbage collection
        img_label.pack(side=tk.LEFT, padx=(0, 10))  # Place image with minimal spacing
        
        # Add text and buttons next to the image
        details_frame = ttk.Frame(frame, style="Custom.TFrame")
        details_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(details_frame, text=f"From: {source.capitalize()}.com", style="Custom.TLabel").pack(anchor="w")
        ttk.Label(details_frame, text=title, wraplength=400, style="Custom.TLabel").pack(anchor="w")
        ttk.Label(details_frame, text=price, font=("Helvetica", 12), style="Custom.TLabel").pack(anchor="w")
        
        def open_link():
            import webbrowser
            webbrowser.open(link)
        
        # Create a canvas to hold the button's rectangle (border)
        canvas = tk.Canvas(details_frame, bg="#f6d7da", highlightthickness=0)
        canvas.pack(anchor="w")
        
        # Configure button properties
        border_color = "#c0a1a6"
        border_width = 6
        
        # Create the button and measure its size
        link_button = tk.Button(canvas, text="View Listing", command=open_link, bg="white", fg="#6D98C2", relief="flat")
        link_button.update_idletasks()  # Ensure geometry is updated before measuring
        
        # Get the button's actual size
        button_width = link_button.winfo_reqwidth()
        button_height = link_button.winfo_reqheight()
        
        # Adjust canvas size to match the button with the border
        canvas.config(width=button_width + border_width * 2, height=button_height + border_width * 2)
        
        # Create the rectangle (border) dynamically based on button size
        rect = canvas.create_rectangle(
            border_width, border_width, 
            button_width + border_width, button_height + border_width, 
            outline=border_color, width=border_width
        )
        
        # Place the button centered on the canvas
        canvas.create_window(
            border_width + button_width // 2,
            border_width + button_height // 2,
            window=link_button,
            anchor="center"
        )
        
        # Update the scrollable area to include the new listing
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))