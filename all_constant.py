import requests
from bs4 import BeautifulSoup
import time
import logging
import webbrowser
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

base_url = "https://vistaauction.com/Browse/C26985692/Electronics"
FILENAME = "live_deals.html"  # Single persistent filename

def parse_item(item):
    """Parses individual item elements to extract details"""
    try:
        # Extract name
        name = item.find("h2", class_="title").find("a").text.strip()

        # Extract price
        try:
            price_text = item.find("span", class_="awe-rt-CurrentPrice").text.strip()
            current_price = float(price_text.replace('$', '').replace(',', ''))
        except Exception as e:
            logging.warning(f"Failed to extract price: {e}")
            return None

        # Initialize values
        condition = "N/A"
        msrp = None
        subtitle_text = ""

        # Extract subtitle text
        try:
            subtitle_element = item.find("h3", class_="subtitle").find("a")
            subtitle_text = subtitle_element.text.strip() if subtitle_element else ""
            
            parts = subtitle_text.split(" - ")
            
            # Extract MSRP
            if "MSRP:" in subtitle_text:
                msrp_str = parts[0].split("MSRP: $")[1].split()[0]
                msrp = float(msrp_str.replace(',', ''))
            
            # Extract condition
            condition_part = parts[1] if len(parts) >= 2 else subtitle_text
            condition = condition_part.split(" - ")[0].strip()
            
        except Exception as e:
            logging.warning(f"Failed to parse subtitle: {e}")

        # Skip items without MSRP or invalid pricing
        if not msrp or current_price <= 0 or msrp <= 0:
            return None

        # Calculate discount percentage
        discount = ((msrp - current_price) / msrp) * 100
        
        # Filter for 60-99.99% discounts
        if not (60 <= discount < 100):
            return None

        # Extract listing link
        try:
            listing_link = item.find("h2", class_="title").find("a")["href"]
            if not listing_link.startswith("http"):
                listing_link = f"https://vistaauction.com{listing_link}"
        except Exception as e:
            logging.warning(f"Failed to extract listing link: {e}")
            return None

        return {
            "name": name,
            "price": current_price,
            "condition": condition,
            "msrp": msrp,
            "discount": discount,
            "listing_link": listing_link
        }
    except Exception as e:
        logging.error(f"Error parsing item: {e}")
        return None

def generate_html(filtered_items):
    """Generates auto-refreshing HTML with latest deals"""
    # Properly indented HTML construction
    html = f"""
    <html>
    <head>
        <meta http-equiv="refresh" content="5">
        <style>
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-family: Arial, sans-serif;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #4CAF50;
                color: white;
            }}
            tr:hover {{background-color: #f5f5f5;}}
            .timestamp {{ 
                color: #666;
                font-size: 0.9em;
                padding: 10px;
            }}
        </style>
    </head>
    <body>
    <h1>Live Deal Tracker 🔄</h1>
    <div class="timestamp">Last updated: {time.strftime("%Y-%m-%d %H:%M:%S")}</div>
    <table>
        <tr>
            <th>Name</th>
            <th>Condition</th>
            <th>Price</th>
            <th>MSRP</th>
            <th>Discount</th>
            <th>Link</th>
        </tr>
    """

    # Properly indented table rows
    for item in filtered_items:
        html += f"""
        <tr>
            <td>{item['name'][:70]}{'...' if len(item['name']) >70 else ''}</td>
            <td>{item['condition']}</td>
            <td>${item['price']:.2f}</td>
            <td>${item['msrp']:.2f}</td>
            <td style="color: {'green' if item['discount'] >=80 else 'orange'}">
                {item['discount']:.1f}%
            </td>
            <td><a href="{item['listing_link']}" target="_blank">View</a></td>
        </tr>
        """

    # Properly indented closing tags
    html += """
    </table>
    </body>
    </html>
    """
    return html

def scan_pages():
    """Scans first 5 pages continuously"""
    all_items = []
    for page in range(1, 6):  # Only pages 1-5
        try:
            url = f"{base_url}?page={page}"
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            items = soup.find_all("div", class_="panel panel-default hasQuickbid clearfix listing")
            all_items.extend([parse_item(i) for i in items])
        except Exception as e:
            logging.error(f"Error scanning page {page}: {e}")
    
    # Filter valid items and remove duplicates
    return [i for i in all_items if i is not None]

def update_display():
    """Updates the HTML file and keeps browser open"""
    deals = scan_pages()
    html = generate_html(deals)
    
    # Write to same file every time
    with open(FILENAME, "w", encoding="utf-8") as f:
        f.write(html)
    
    # Only open browser once
    if not os.path.isfile(FILENAME + ".lock"):
        webbrowser.open(f"file://{os.path.abspath(FILENAME)}")
        open(FILENAME + ".lock", "w").close()  # Create lock file

def main():
    # Initial setup
    if os.path.exists(FILENAME):
        os.remove(FILENAME)
    
    # Continuous scanning
    while True:
        try:
            update_display()
            logging.info("Updated deals display")
            time.sleep(5)  # 5 second interval
        except KeyboardInterrupt:
            logging.info("Stopping tracker...")
            if os.path.exists(FILENAME + ".lock"):
                os.remove(FILENAME + ".lock")
            break

if __name__ == "__main__":
    main()