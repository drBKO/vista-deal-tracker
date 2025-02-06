# vista_deal_tracker.py
import requests
from bs4 import BeautifulSoup
import time
import logging
import boto3  # AWS library for interacting with S3

# Set up logging to help debug if something goes wrong
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

base_url = "https://vistaauction.com/Browse/C26985692/Electronics"

def parse_item(item):
    """Exactly the same as your original version - no changes needed!"""
    try:
        name = item.find("h2", class_="title").find("a").text.strip()

        try:
            price_text = item.find("span", class_="awe-rt-CurrentPrice").text.strip()
            current_price = float(price_text.replace('$', '').replace(',', ''))
        except Exception as e:
            logging.warning(f"Failed to extract price: {e}")
            return None

        condition = "N/A"
        msrp = None
        subtitle_text = ""

        try:
            subtitle_element = item.find("h3", class_="subtitle").find("a")
            subtitle_text = subtitle_element.text.strip() if subtitle_element else ""
            
            parts = subtitle_text.split(" - ")
            
            if "MSRP:" in subtitle_text:
                msrp_str = parts[0].split("MSRP: $")[1].split()[0]
                msrp = float(msrp_str.replace(',', ''))
            
            condition_part = parts[1] if len(parts) >= 2 else subtitle_text
            condition = condition_part.split(" - ")[0].strip()
            
        except Exception as e:
            logging.warning(f"Failed to parse subtitle: {e}")

        if not msrp or current_price <= 0 or msrp <= 0:
            return None

        discount = ((msrp - current_price) / msrp) * 100
        
        if not (60 <= discount < 100):
            return None

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
    """Modified to RETURN HTML instead of saving to file"""
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

    html += """
    </table>
    </body>
    </html>
    """
    return html

def scan_pages():
    """Same as your original version - no changes needed!"""
    all_items = []
    for page in range(1, 6):
        try:
            url = f"{base_url}?page={page}"
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
            items = soup.find_all("div", class_="panel panel-default hasQuickbid clearfix listing")
            all_items.extend([parse_item(i) for i in items])
        except Exception as e:
            logging.error(f"Error scanning page {page}: {e}")
    
    return [i for i in all_items if i is not None]

# This is the NEW AWS-specific part that replaces your original main()
def lambda_handler(event, context):
    """
    This function will be called by AWS Lambda every time it runs
    """
    try:
        logging.info("Starting deal scan...")
        deals = scan_pages()
        
        logging.info(f"Found {len(deals)} valid deals")
        html_content = generate_html(deals)
        
        # Upload to AWS S3 bucket
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket='vista-deal-tracker',  # Must match your S3 bucket name
            Key='index.html',
            Body=html_content,
            ContentType='text/html'
        )
        
        logging.info("Successfully updated website!")
        return {
            'statusCode': 200,
            'body': 'Website updated successfully'
        }
        
    except Exception as e:
        logging.error(f"Critical error: {str(e)}")
        return {
            'statusCode': 500,
            'body': 'Error updating website'
        }

# For local testing (optional)
if __name__ == "__main__":
    # Test the lambda handler locally
    lambda_handler(None, None)
