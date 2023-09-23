import datetime
import re
import webbrowser

from selenium import webdriver  # version 4.2.0
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

import time
import pytz
import threading

import os

import sqlite3

import email
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# CURR_SCRIPT_PATH = os.path.dirname(sys.executable)
# CURR_SCRIPT_PATH = ''

FF_DRIVER_PATH = 'geckodriver.exe'
FF_PATH = r'C:\Program Files\Mozilla Firefox\firefox.exe'
DB_PATH = 'flights.db'
logFile = open('log.txt', 'w')

driver = None


def read_flights_db():
    global flights
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM flights')
        conn.commit()
        flights_ = cursor.fetchall()
        conn.close()

        for flight in flights_:
            flights.append({
                'link': flight[0],
                'search_link': flight[1],
                'line': flight[2],
                'dep_date': flight[3],
                'return_date': flight[4],
                'dep_airline_code': flight[5],
                'return_airline_code': flight[6],
                'curr_price': flight[7],
                'target_price': flight[8],
                'old_price': flight[9],
                'status': flight[10],
                'class': flight[11]
            })
        return True

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False


def insert_flight_db(flight):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO flights VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (
                       flight['link'], flight['search_link'], flight['line'], flight['dep_date'], flight['return_date'],
                       flight['dep_airline_code'], flight['return_airline_code'], flight['curr_price'],
                       flight['target_price'], flight['old_price'], flight['status'], flight['class']))

        for email, send_link in flight['emails'].items():
            cursor.execute('INSERT INTO flights_emails VALUES (?, ?, ?)', (flight['link'], email, send_link))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False


def delete_flight_db(link):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM flights WHERE link=?', (link,))
        cursor.execute('DELETE FROM flights_emails WHERE flight_id=?', (link,))
        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False


def update_flight_db(flight):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE flights SET curr_price=?, old_price=?, status=? WHERE link=?',
                       (flight['curr_price'], flight['old_price'], flight['status'], flight['link']))
        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False


def insert_email_db(email_):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO emails VALUES (?)', (email_,))
        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False


def delete_email_db(email_):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM emails WHERE email=?', (email_,))
        cursor.execute('DELETE FROM flights_emails WHERE email=?', (email_,))
        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False


def get_all_emails():
    all_emails = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM emails')
        conn.commit()
        emails = cursor.fetchall()
        conn.close()

        for email_ in emails:
            all_emails.append(email_[0])
        return all_emails

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False


def get_emails_for_flight(flight):
    emails = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM flights_emails WHERE flight_id=?', (flight['link'],))
        conn.commit()
        emails_ = cursor.fetchall()
        conn.close()

        for email_ in emails_:
            emails[email_[1]] = email_[2]
        return emails

    except Exception as e:
        print(str(e))
        logFile.write(str(e))
        return False

############################################################################################################


def is_valid_flight_url(url, search=True):
    if search:
        return url.startswith('https://almatar.com/en/flights/list') or url.startswith(
            'https://almatar.com/ar/flights/list')
    else:
        return url.startswith('https://almatar.com/en/flights/traveller-details/') or url.startswith(
            'https://almatar.com/ar/flights/traveller-details/')


def get_html(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'price')))
    except Exception as e:
        print('Error: cannot get flights from this link: ' + url, datetime.datetime.now().strftime(' AT %H:%M'), '\n')
        logFile.write(str(e) + ' LINK: ' + url + datetime.datetime.now().strftime(' AT %H:%M') + '\n')
        # print(str(e), ' LINK: ' + url, datetime.datetime.now().strftime(' AT %H:%M'), '\n')
        return None  # no flights found
    # while there are new flights loaded keep scrolling to the bottom of the page to load all flights
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    html = driver.page_source

    return html


def get_date_str_format(soup):
    date1 = soup.select_one('.first .date').text.strip()
    date2 = soup.select_one('.second .date').text.strip()
    loc1 = soup.select_one('.first .location').text.strip()
    loc2 = soup.select_one('.second .location').text.strip()
    # date_str = takeoff date , takeoff location & landing date , landing location
    date_str = date1 + ', ' + loc1 + ' & ' + date2 + ', ' + loc2
    return date_str


def get_flight_info(driver, flight_url):
    if is_valid_flight_url(flight_url, False):
        response = get_html(driver, flight_url)
        if not response:
            return None

        cards = driver.find_elements(By.CSS_SELECTOR, '.card-container')
        more_details_links = driver.find_elements(By.CSS_SELECTOR, '.more-details-link')
        for i in range(len(cards)):  # click on more details button for each flight
            more_details_links[i].click()
            time.sleep(1)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        line = soup.select('h6')[0].text.strip()
        price = soup.select_one('#total-price').text.strip()
        price = int(price.replace('SAR', '').replace(' ', ''))
        dep_date_str = get_date_str_format(soup.select('.card-container')[0])
        dep_airline_code = soup.select('.logo-code')[0].text.strip()

        # if it's roundTrip flight
        if len(cards) == 2:
            ret_date_str = get_date_str_format(soup.select('.card-container')[1])
            ret_airline_code = soup.select('.logo-code')[1].text.strip()
            return {'line': line, 'price': price, 'dep_date': dep_date_str, 'dep_airline_code': dep_airline_code,
                    'return_date': ret_date_str, 'return_airline_code': ret_airline_code}

        return {'line': line, 'price': price, 'dep_date': dep_date_str, 'dep_airline_code': dep_airline_code,
                'return_date': 'None', 'return_airline_code': 'None'}

    else:
        return None


def get_curr_price_and_index(driver, soup, flight):
    try:
        # for each group if the airline code matched for the dep and return flights click on get more details button,
        # then if the details is matched for the dep and return with the flight, get the price
        is_round_trip = driver.current_url.find('connection=RoundTrip') != -1
        groups = soup.select('.main-card-container')
        group_index = -1

        d = 0  # d is the index of the more details button
        inc = 2 if is_round_trip else 1  # inc is the increment of the index of the more details button
        more_details_links = driver.find_elements(By.CSS_SELECTOR, '.more-details-link')
        for i in range(len(groups)):
            if is_round_trip:
                if groups[i].select('.logo-code')[0].text.strip() == flight['dep_airline_code'] and \
                        groups[i].select('.logo-code')[1].text.strip() == flight['return_airline_code']:

                    group_index = i
                    more_details_links[d].click()
                    time.sleep(1)
                    more_details_links[d + 1].click()
                    time.sleep(1)

                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    groups[i] = soup.select('.main-card-container')[i]

                    dep_date_str = get_date_str_format(groups[i].select('.card-container')[0])
                    ret_date_str = get_date_str_format(groups[i].select('.card-container')[1])

                    if dep_date_str == flight['dep_date'] and ret_date_str == flight['return_date']:
                        price = groups[i].select_one('.price').text.strip()
                        price = int(price.replace('SAR', '').replace(' ', ''))
                        return price, group_index

            else:
                if groups[i].select('.logo-code')[0].text.strip() == flight['dep_airline_code']:
                    group_index = i
                    more_details_links[d].click()
                    time.sleep(1)

                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    groups[i] = soup.select('.main-card-container')[i]

                    dep_date_str = get_date_str_format(groups[i].select('.card-container')[0])

                    if dep_date_str == flight['dep_date']:
                        price = groups[i].select_one('.price').text.strip()
                        price = int(price.replace('SAR', '').replace(' ', ''))
                        return price, group_index

            d += inc

        return 0, group_index

    except Exception as e:
        print(str(e), flight, datetime.datetime.now().strftime('FROM get_curr_price() AT %H:%M'), '\n')
        logFile.write(
            str(e) + datetime.datetime.now().strftime(' FROM get_curr_price() AT %H:%M') + '\n link: ' + flight[
                'search_link'] + '\n')
        return 0, -1


def send_email(flight):
    print('\n########' * 10, '\nTARGET PRICE REACHED: \n', flight, datetime.datetime.now().strftime(' AT %H:%M'),
          '\n########' * 10)
    try:
        emails_for_flight = get_emails_for_flight(flight)
        for email_to, send_link in emails_for_flight.items():
            # Create a text/plain message
            msg = MIMEMultipart("alternative")

            # HTML-formatted content
            html_content = f"""
                <html>
                <body>
                    <p><strong>Line: {flight['line']} </strong> </p>
                    <p>Departure Date: {flight['dep_date']}</p>
                    <p>Return Date: {flight['return_date']}</p>
                    <p>Departure Airline Code: {flight['dep_airline_code']}</p>
                    <p>Return Airline Code: {flight['return_airline_code']}</p>
                    <p>Flight Class: {flight['class']}</p>
                    <p><strong>Price Changed from <span style="color:red;">{flight['old_price']}</span> to 
                    <span style="color:red;">{flight['curr_price']}</span> </strong></p>
                """
            if send_link:
                html_content += "<p><strong>Search Link:</strong> {flight['search_link']}</p>"

            html_content += "</body></html>"

            # Attach HTML content to the message
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            msg['Subject'] = 'PRICE ALERT FOR FLIGHT'
            msg['From'] = email_from
            msg['To'] = email_to

            with smtplib.SMTP_SSL('smtp.zoho.com', 465) as server:
                server.login(email_from, email_password)
                server.send_message(msg)
                print('Email sent to: ', email_to)

        return True

    except Exception as e:
        print(str(e))
        logFile.write(str(e) + datetime.datetime.now().strftime(' FROM send_email() AT %H:%M') + '\n')
        return False


def get_times(flight):
    # Create a timezone object for GMT+3 (Saudi Arabia)
    saudi_arabia_tz = pytz.timezone('Asia/Riyadh')
    # Convert the current time to GMT+3 (Saudi Arabia) time
    current_time = datetime.datetime.now(pytz.utc).astimezone(saudi_arabia_tz)
    # Convert the flight time to GMT+3 (Saudi Arabia) time
    flight_time = datetime.datetime.strptime(str(flight['dep_date']).split(',')[0], '%A %d %b %Y at %H:%M %p')
    flight_time = saudi_arabia_tz.localize(flight_time)

    return current_time, flight_time


def update_flights():
    global driver
    # init firefox driver with headless option

    options = webdriver.FirefoxOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    driver = webdriver.Firefox(executable_path=FF_DRIVER_PATH, firefox_binary=FF_PATH, options=options)

    while True:
        for flight in flights:
            try:
                current_time, flight_time = get_times(flight)
                # if the flight date is passed, delete it
                if flight_time <= current_time:
                    delete_flight_db(flight['link'])
                    flights.remove(flight)
                    update_flight_table()
                    print('FLIGHT DELETED: ', flight, datetime.datetime.now().strftime(' AT %H:%M'), '\n')
                    continue

                search_html = get_html(driver, flight['search_link'])
                if not search_html:
                    continue
                soup = BeautifulSoup(search_html, 'html.parser')
                # Get the current price of the flight
                price_index = get_curr_price_and_index(driver, soup, flight)
                curr_price = price_index[0]
                group_index = price_index[1]
                if not curr_price:
                    print('No price found for: ', flight, datetime.datetime.now().strftime(' AT %H:%M'), '\n')
                    continue
                if curr_price != flight['curr_price']:  # if the price has changed
                    flight['old_price'] = flight['curr_price']
                    flight['curr_price'] = curr_price
                    flight['status'] = 'Price Changed'
                    # if flight['curr_price'] <= flight['target_price']:  # if the target price is
                    # flight['status'] = 'Target Price Reached'
                    send_email(flight)

                    update_flight_db(flight)
                    update_flight_table()
                    print('FLIGHT UPDATED: ', flight, datetime.datetime.now().strftime(' AT %H:%M'), '\n')

                    # take a screenshot of the group element
                    group = driver.find_elements(By.CSS_SELECTOR, '.main-card-container')[group_index]
                    group.screenshot(f'./screenshots/{flight["dep_airline_code"]}.png')

                else:
                    print('price is the same: ', flight, datetime.datetime.now().strftime(' AT %H:%M'), '\n')
            except Exception as e:
                print(str(e), datetime.datetime.now().strftime('AT %H:%M'), '\n')
                continue

        update_flight_table()
        time.sleep(60)  # check every minute


# Function to start the update_flights thread
def start_update_thread():
    update_thread = threading.Thread(target=update_flights)
    update_thread.daemon = True  # Set the thread as a daemon so it terminates when the main application is closed
    update_thread.start()


# Function to handle the Add Flight button click
def add_flight():
    search_link = search_entry.get()
    flight_link = link_entry.get()
    target_price = price_entry.get()
    # Get the selected emails with their checkboxes
    selected_emails_dict = {}
    for i, var in enumerate(email_var):
        if var.get() == 1:
            selected_emails_dict[sample_emails[i]] = 1 if send_link_var[i].get() == 1 else 0

    # Check if the link has already been added
    for flight in flights:
        if flight['link'] == flight_link:
            messagebox.showerror('Invalid Input', 'This link has already been added')
            return

    # Validate input fields
    if not is_valid_flight_url(search_link) or not is_valid_flight_url(flight_link, False):
        messagebox.showerror('Invalid Input', 'Please enter valid links')
        return

    try:
        target_price = int(target_price)
    except ValueError:
        messagebox.showerror('Invalid Input', 'Please enter a valid price')
        return

    try:
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        driver = webdriver.Firefox(executable_path=FF_DRIVER_PATH, firefox_binary=FF_PATH, options=options)

        flight_info = get_flight_info(driver, flight_link)
        if not flight_info:
            messagebox.showerror('Invalid Input', 'Cannot get flight details from this link')
            return

        flight_class = search_link.split('class=')[1].split('&')[0]  # get the flight class from the search link

        # Store the flight details (you can modify this part to save the data to a file or database)
        flight = {'link': flight_link, 'search_link': search_link, 'line': flight_info['line'],
                  'dep_date': flight_info['dep_date'],
                  'return_date': flight_info['return_date'], 'dep_airline_code': flight_info['dep_airline_code'],
                  'return_airline_code': flight_info['return_airline_code'], 'curr_price': flight_info['price'],
                  'target_price': target_price, 'old_price': flight_info['price'], 'status': 'Active',
                  'emails': selected_emails_dict, 'class': flight_class}

        flights.append(flight)
        insert_flight_db(flight)

        # Clear input fields
        link_entry.delete(0, tk.END)
        price_entry.delete(0, tk.END)

        # Update the flight table
        update_flight_table()

        # Show success message
        messagebox.showinfo('Success', 'Flight added successfully!')

    except Exception as e:
        print(str(e))
        messagebox.showerror('Invalid Input', 'Cannot get flight details from this link' + str(e))
        return


# Function to handle the Delete button click
def delete_flight():
    selection = flight_table.focus()
    if selection:
        index = flight_table.item(selection, 'text')
        # Remove the flight from the list
        delete_flight_db(flights[int(index)]['link'])
        flights.pop(int(index))
        # Update the flight table
        update_flight_table()


# Function to update the flight table
def update_flight_table():
    # Clear the existing table
    flight_table.delete(*flight_table.get_children())

    # Add flights to the table
    for index, flight in enumerate(flights):
        search_link = flight['search_link']
        open_text = 'open link'
        line = flight['line']
        dep_date = flight['dep_date'].split(',')[0]
        return_date = flight['return_date'].split(',')[0]
        dep_code = flight['dep_airline_code']
        return_code = flight['return_airline_code']
        curr_price = flight['curr_price']
        target_price = flight['target_price']
        status = flight['status']
        flight_table.insert('', tk.END, text=index, values=(search_link, open_text, line, dep_date, return_date,
                                                            dep_code, return_code, curr_price, target_price, status))


def double_click_link(event):
    selected_item = flight_table.focus()
    link = flight_table.item(selected_item, 'values')[0]

    # Copy the link to the clipboard
    root.clipboard_clear()
    root.clipboard_append(link)
    root.update()

    # Open the link in the default web browser
    webbrowser.open(link)
    # os.system(f'start {link}')


def is_valid_email(email):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False
    return True


def add_email():
    email_ = email_entry.get()
    if not is_valid_email(email_):
        messagebox.showerror('Invalid Input', 'Please enter a valid email')
        return

    if email in email_to_list:
        messagebox.showerror('Invalid Input', 'This email has already been added')
        return

    # Add the email to the database
    insert_email_db(email_)
    email_to_list.append(email_)

    # Clear the input field
    email_entry.delete(0, tk.END)

    # Show success message
    messagebox.showinfo('Success', 'Email added successfully!')

    # Update the emails listbox
    update_emails_listbox()


def delete_email():
    # delete email from the listbox
    selection = emails_listbox.curselection()
    if selection:
        email_to_list.remove(emails_listbox.get(selection))
        delete_email_db(emails_listbox.get(selection))
        update_emails_listbox()


def update_emails_listbox():
    # Clear the existing list
    emails_listbox.delete(0, tk.END)

    # Add emails to the list
    for email_ in email_to_list:
        emails_listbox.insert(tk.END, email_)


############################################################################################################


# Create the main application window
root = tk.Tk()
root.title('Flight Manager')
root.configure(bg='#BDBDBD')

# Configure main tab style
style = ttk.Style()
style.theme_create('custom', parent='clam', settings={
    'TNotebook.Tab': {
        'configure': {
            'padding': [30, 10],  # Increase padding for the tabs
            'background': '#4CAF50',  # Set the background color of the tabs to green
            'font': ('Arial', 14, 'bold'),  # Set the font style of the tabs
            'foreground': 'white',  # Set the text color of the tabs to white
            'borderwidth': 0,  # Remove the default border
            'focuscolor': '#BDBDBD',  # Set the focus color of the tabs to green
            'focusthickness': 2,  # Increase the focus thickness for the tabs
            'lightcolor': '#BDBDBD',  # Set the light color for the tabs to grey
            'darkcolor': '#333333',  # Set the dark color for the tabs to black
            'relief': tk.SOLID,  # Set the relief style for the tabs to solid
        }
    }
})
style.configure('TNotebook', background='#BDBDBD')  # Set the background color of the tab control to grey
style.configure('TNotebook.Tab', background='#BDBDBD', relief=tk.SOLID)  # Set the background color of the tabs to grey

style.theme_use('custom')

# Create tabs
tab_control = ttk.Notebook(root)
add_flight_tab = tk.Frame(tab_control, bg='#BDBDBD')
my_flights_tab = tk.Frame(tab_control, bg='#BDBDBD')
emails_tab = tk.Frame(tab_control, bg='#BDBDBD')
tab_control.add(add_flight_tab, text='Add Flight')
tab_control.add(my_flights_tab, text='My Flights')
tab_control.add(emails_tab, text='Emails')
tab_control.pack(expand=True, fill='both')

# Add Flight tab
add_flight_frame = tk.Frame(add_flight_tab, bg='#BDBDBD')
add_flight_frame.pack(expand=True, padx=200, pady=100)

search_label = tk.Label(add_flight_frame, text='Search Link:', font=('Arial', 14), bg='#BDBDBD', fg='black')
search_label.pack()
search_entry = tk.Entry(add_flight_frame, font=('Arial', 12), width=30)
search_entry.pack(pady=5)

link_label = tk.Label(add_flight_frame, text='Flight Link:', font=('Arial', 14), bg='#BDBDBD', fg='black')
link_label.pack()
link_entry = tk.Entry(add_flight_frame, font=('Arial', 12), width=30)
link_entry.pack(pady=5)

price_label = tk.Label(add_flight_frame, text='Target Price:', font=('Arial', 14), bg='#BDBDBD', fg='black')
price_label.pack()
price_entry = tk.Entry(add_flight_frame, font=('Arial', 12), width=30)
price_entry.pack(pady=5)


sample_emails = get_all_emails()

# Create a frame for emails with a scrollbar
email_frame = tk.Frame(add_flight_frame, bg='#BDBDBD')
email_frame.pack(expand=True, padx=5, pady=30, fill=tk.BOTH)

# Create a canvas to hold the emails frame
email_canvas = tk.Canvas(email_frame, bg='#BDBDBD')
email_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add a scrollbar to the canvas
scrollbar = ttk.Scrollbar(email_frame, orient=tk.VERTICAL, command=email_canvas.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Configure the canvas to use the scrollbar
email_canvas.configure(yscrollcommand=scrollbar.set)
email_canvas.bind('<Configure>', lambda e: email_canvas.configure(scrollregion=email_canvas.bbox('all')))
email_canvas.bind_all('<MouseWheel>', lambda e: email_canvas.yview_scroll(-1 * int(e.delta / 120), 'units'))

# Create another frame to hold the emails and checkboxes
email_inner_frame = tk.Frame(email_canvas, bg='#BDBDBD')
email_canvas.create_window((0, 0), window=email_inner_frame, anchor='nw')

# Sample variable to store the checkbox states
email_var = []
send_link_var = []
for _ in sample_emails:
    email_var.append(tk.IntVar())
    send_link_var.append(tk.IntVar())

# Create the emails list with checkboxes and labels
for i, email in enumerate(sample_emails):
    email_row_frame = tk.Frame(email_inner_frame, bg='#BDBDBD')
    email_row_frame.pack(fill=tk.X, padx=5, pady=2)

    email_checkbox = tk.Checkbutton(email_row_frame, variable=email_var[i], bg='#BDBDBD')
    email_checkbox.pack(side=tk.LEFT)

    email_label = tk.Label(email_row_frame, text=email, font=('Arial', 12), bg='#BDBDBD', fg='black')
    email_label.pack(side=tk.LEFT, padx=5)

    send_link_checkbox = tk.Checkbutton(email_row_frame, variable=send_link_var[i], text='Send Link', bg='#BDBDBD',
                                        fg='black')
    send_link_checkbox.pack(side=tk.LEFT)


add_button = tk.Button(add_flight_frame, text='Add Flight', command=add_flight, font=('Arial', 12), bg='#4CAF50',
                       fg='white', relief=tk.RAISED, bd=0)
add_button.pack(pady=5)

# My Flights tab
my_flights_frame = tk.Frame(my_flights_tab, bg='#BDBDBD')
my_flights_frame.pack(expand=True, padx=40, pady=20)

table_frame = tk.Frame(my_flights_frame, bg='#BDBDBD')
table_frame.pack(fill=tk.BOTH, expand=True)

flight_table = ttk.Treeview(table_frame, columns=('searchLink', 'OpenText', 'Line', 'dDate', 'rDate', 'dCode', 'rCode',
                                                  'currPrice', 'tPrice', 'Status'), show='headings',
                            selectmode='browse')
flight_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

style.configure('Treeview.Heading', font=('Arial', 12, 'bold'), background='#333333', foreground='white')
style.configure('Treeview', font=('Arial', 12), background='#BDBDBD')
style.map('Treeview', background=[('selected', '#4CAF50')])

flight_table.heading('searchLink', text='Link')
flight_table.heading('Line', text='Airline')
flight_table.heading('dDate', text='Dep. Date')
flight_table.heading('rDate', text='Return Date')
flight_table.heading('dCode', text='Dep. Code')
flight_table.heading('rCode', text='Return Code')
flight_table.heading('currPrice', text='Curr Price')
flight_table.heading('tPrice', text='Target Price')
flight_table.heading('Status', text='Status')

flight_table.column('searchLink', width=0, stretch=False)  # Hide the first column
flight_table.column('OpenText', width=100, anchor='center')
flight_table.column('Line', width=150, anchor='center')
flight_table.column('dDate', width=270, anchor='center')
flight_table.column('rDate', width=270, anchor='center')
flight_table.column('dCode', width=100, anchor='center')
flight_table.column('rCode', width=100, anchor='center')
flight_table.column('currPrice', width=100, anchor='center')
flight_table.column('tPrice', width=100, anchor='center')
flight_table.column('Status', width=150, anchor='center')

# Add a vertical scrollbar embedded within the flight table
scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=flight_table.yview)
flight_table.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
# Bind the double-click event to the treeview
flight_table.bind("<Double-Button-1>", double_click_link)

# Delete button
delete_button = tk.Button(my_flights_frame, text='Delete', command=delete_flight, font=('Arial', 12), bg='#FF3B30',
                          fg='white', relief=tk.RAISED, bd=0)
delete_button.pack(side=tk.BOTTOM, pady=10)

# Emails tab
emails_frame = tk.Frame(emails_tab, bg='#BDBDBD')
emails_frame.pack(expand=True, padx=200, pady=20)

email_label = tk.Label(emails_frame, text='Email:', font=('Arial', 14), bg='#BDBDBD', fg='black')
email_label.pack()
email_entry = tk.Entry(emails_frame, font=('Arial', 12), width=30)
email_entry.pack(pady=5)

add_email_button = tk.Button(emails_frame, text='Add Email', command=add_email, font=('Arial', 12), bg='#4CAF50',
                             fg='white', relief=tk.RAISED, bd=0)
add_email_button.pack(pady=15)

emails_listbox = tk.Listbox(emails_frame, font=('Arial', 12), width=30, height=10)
emails_listbox.pack(pady=5)

delete_email_button = tk.Button(emails_frame, text='Delete Email', command=delete_email, font=('Arial', 12),
                                bg='#FF3B30', fg='white', relief=tk.RAISED, bd=0)
delete_email_button.pack(pady=15)


############################################################################################################


try:
    # Initialize flights list
    flights = []
    read_flights_db()
    update_flight_table()

    #######################################################################
    email_from = ''
    email_password = ''
    #######################################################################

    email_to_list = get_all_emails()
    update_emails_listbox()

    # Call the start_update_thread function to start the updates in a separate thread
    start_update_thread()

    # Start the application
    root.mainloop()

    driver.quit()

except Exception as e:
    print(e)

